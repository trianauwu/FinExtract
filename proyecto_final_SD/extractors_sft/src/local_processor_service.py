import pika
import json
import pandas as pd
from pathlib import Path
import sys
import os
import traceback
import datetime
import time

current_file_path = Path(__file__).resolve()
src_dir = current_file_path.parent
project_root = src_dir.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from extractor_polakof import extract_polakof
from extractor_tata import extract_tata
from extractor_macro_res import extract_res_macro
from extractor_macro_ops import extract_ops_macro
from extractor_bowerey import extract_bowerey
from extractor_GDU import extract_GDU
from extractor_ussel_res import extract_res_ussel
from extractor_ussel_ops import extract_ops_ussel

from transformer import transform
from excel_generator import to_excel
from validator import validate_excel
from logger import log_event

from prometheus_client import Counter, Histogram, Gauge, generate_latest, start_http_server

RABBITMQ_HOST = 'localhost'
RABBITMQ_QUEUE_NAME = 'pdf_processing_queue'
RABBITMQ_STATUS_QUEUE_NAME = 'system_status_queue'

LOCAL_PROCESSOR_PROMETHEUS_METRICS_PORT = 8001
start_http_server(LOCAL_PROCESSOR_PROMETHEUS_METRICS_PORT)
print(f"Servidor de métricas de Prometheus para Local Processor iniciado en el puerto: {LOCAL_PROCESSOR_PROMETHEUS_METRICS_PORT}")

LOCAL_PROCESSOR_PDF_PROCESSED_TOTAL = Counter(
    'local_processor_pdf_processed_total',
    'Total number of PDFs processed by the local processor service.',
    ['extractor', 'status']
)

LOCAL_PROCESSOR_PROCESSING_DURATION_SECONDS = Histogram(
    'local_processor_pdf_processing_duration_seconds',
    'Duration of PDF processing by the local processor service in seconds.',
    ['extractor']
)

EXTRACTOR_FUNCTIONS = {
    "extract_polakof": extract_polakof,
    "extract_tata": extract_tata,
    "extract_ops_macro": extract_ops_macro,
    "extract_res_ussel": extract_res_ussel,
    "extract_ops_ussel": extract_ops_ussel,
    "extract_bowerey": extract_bowerey,
    "extract_GDU": extract_GDU,
    "extract_res_macro": extract_res_macro,
}

def publish_status_event(event_type: str, pdf_path: str, extractor_name: str = None, error_message: str = None, generated_file_path: str = None):
    try:
        event_payload = {
            "type": event_type,
            "pdf_path": pdf_path,
            "extractor_name": extractor_name,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if error_message:
            event_payload['error_message'] = error_message
        if generated_file_path:
            event_payload['generated_file_path'] = generated_file_path

        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_STATUS_QUEUE_NAME, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=RABBITMQ_STATUS_QUEUE_NAME,
            body=json.dumps(event_payload)
        )
        connection.close()
        print(f"DEBUG Local Processor: Publicado evento '{event_type}' para PDF: {pdf_path}. Generado: {generated_file_path or 'N/A'}")
    except Exception as e:
        log_event(f"ERROR: No se pudo publicar evento de estado desde el servicio local a la cola '{RABBITMQ_STATUS_QUEUE_NAME}': {e}")


def process_message_callback(ch, method, properties, body):
    pdf_path_obj = None
    pdf_path_normalized_from_message = 'unknown_path'
    extractor_name = 'unknown'

    start_time = time.time()
    try:
        message = json.loads(body)
        pdf_path_str = message.get('pdf_path')
        extractor_name = message.get('extractor_name')

        if not all([pdf_path_str, extractor_name]):
            log_event(f"ERROR: Mensaje incompleto o mal formado recibido por el servicio local: {message}. Ignorando.")
            ch.basic_ack(method.delivery_tag)
            LOCAL_PROCESSOR_PDF_PROCESSED_TOTAL.labels(extractor=extractor_name or 'unknown', status='error').inc()
            return

        pdf_path_normalized_from_message = pdf_path_str
        pdf_path_obj = Path(pdf_path_str)

        output_folder_local = pdf_path_obj.parent.parent / "output"
        output_folder_local.mkdir(parents=True, exist_ok=True)

        log_event(f"Servicio Local - Consumiendo mensaje: Procesando '{pdf_path_obj.name}' con '{extractor_name}'")

        if extractor_name not in EXTRACTOR_FUNCTIONS:
            log_event(f"ERROR: Extractor '{extractor_name}' no encontrado en el mapeo local de este servicio. Ignorando mensaje para '{pdf_path_obj.name}'.")
            ch.basic_ack(method.delivery_tag)
            LOCAL_PROCESSOR_PDF_PROCESSED_TOTAL.labels(extractor=extractor_name, status='error').inc()
            return

        extractor_func = EXTRACTOR_FUNCTIONS[extractor_name]

        if not pdf_path_obj.exists():
            log_event(f"ADVERTENCIA: PDF no encontrado en la ruta especificada por el mensaje: '{pdf_path_obj}'. Marcando mensaje como procesado.")
            ch.basic_ack(method.delivery_tag)
            LOCAL_PROCESSOR_PDF_PROCESSED_TOTAL.labels(extractor=extractor_name, status='error').inc()
            return

        df = extractor_func(pdf_path_obj)

        if extractor_name != "extract_GDU" and any("Monto" in col for col in df.columns):
            df = transform(df)

        if df.empty or df["Referencia"].isna().all():
            log_event(f"{pdf_path_obj.name}: sin datos válidos para generar Excel (procesado por servicio local), se omitirá la generación de Excel y validación.")
            publish_status_event("pdf_processing_completed", pdf_path_normalized_from_message, extractor_name)
            LOCAL_PROCESSOR_PDF_PROCESSED_TOTAL.labels(extractor=extractor_name, status='completed_no_output').inc()
        else:
            output_excel_filename = f"{pdf_path_obj.stem}_output.xlsx"
            output_excel_path_local = output_folder_local / output_excel_filename
            to_excel(df, str(output_excel_path_local))
            log_event(f"Excel generado por Servicio Local: {output_excel_path_local.name}")

            publish_status_event(
                "file_generated",
                pdf_path_normalized_from_message,
                extractor_name,
                generated_file_path=str(output_excel_path_local.resolve())
            )

            validation_filename = f"{pdf_path_obj.stem}_validation.txt"
            validation_path_local = output_folder_local / validation_filename
            validate_excel(output_excel_path_local, pdf_path_obj.name)
            log_event(f"Validación generada por Servicio Local: {validation_path_local.stem}_validation.txt")

            if validation_path_local.exists():
                publish_status_event(
                    "file_generated",
                    pdf_path_normalized_from_message,
                    extractor_name,
                    generated_file_path=str(validation_path_local.resolve())
                )

            publish_status_event("pdf_processing_completed", pdf_path_normalized_from_message, extractor_name)
            LOCAL_PROCESSOR_PDF_PROCESSED_TOTAL.labels(extractor=extractor_name, status='completed').inc()

        ch.basic_ack(method.delivery_tag)
        log_event(f"Servicio Local - Procesamiento de '{pdf_path_obj.name}' completado exitosamente.")

    except Exception as e:
        error_message = str(e)
        log_event(f"ERROR CRÍTICO en el Servicio de Procesamiento Local para '{pdf_path_normalized_from_message}': {type(e).__name__} - {error_message}")
        log_event(traceback.format_exc())

        publish_status_event("pdf_processing_error", pdf_path_normalized_from_message, extractor_name, error_message)
        LOCAL_PROCESSOR_PDF_PROCESSED_TOTAL.labels(extractor=extractor_name, status='error').inc()

        ch.basic_nack(method.delivery_tag, requeue=True)
        log_event(f"Mensaje para '{pdf_path_normalized_from_message}' NO reconocido (error), será reencolado.")
    finally:
        duration = time.time() - start_time
        LOCAL_PROCESSOR_PROCESSING_DURATION_SECONDS.labels(extractor=extractor_name).observe(duration)


def start_consuming():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE_NAME, durable=True)

        log_event(f"Servicio de Procesamiento Local iniciado. Esperando mensajes en la cola '{RABBITMQ_QUEUE_NAME}'...")
        print(f"Servicio de Procesamiento Local iniciado. Esperando mensajes en la cola '{RABBITMQ_QUEUE_NAME}'...")

        channel.basic_consume(queue=RABBITMQ_QUEUE_NAME, on_message_callback=process_message_callback, auto_ack=False)
        channel.start_consuming()

    except pika.exceptions.AMQPConnectionError as e:
        log_event(f"ERROR CRÍTICO de conexión AMQP: Asegúrate de que RabbitMQ esté corriendo en '{RABBITMQ_HOST}'. Error: {e}")
        print(f"ERROR CRÍTICO de conexión AMQP: Asegúrate de que RabbitMQ esté corriendo en '{RABBITMQ_HOST}'. Error: {e}")
        sys.exit(1)
    except Exception as e:
        log_event(f"ERROR CRÍTICO al iniciar el consumo del servicio local: {e}")
        print(f"ERROR CRÍTICO al iniciar el consumo del servicio local: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_consuming()