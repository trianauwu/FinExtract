import json
import os
import sys
from pathlib import Path
import requests
import pandas as pd
import pika
import datetime
import time

from prometheus_client import Counter, Gauge, Histogram, generate_latest, start_http_server

from extractor_polakof import extract_polakof
from extractor_tata import extract_tata
from extractor_macro_ops import extract_ops_macro
from extractor_macro_res import extract_res_macro
from extractor_bowerey import extract_bowerey
from extractor_ussel_res import extract_res_ussel
from extractor_ussel_ops import extract_ops_ussel
from extractor_GDU import extract_GDU

from transformer import transform
from excel_generator import to_excel
from validator import validate_excel
from logger import log_event

MAIN_PY_DIR = Path(__file__).resolve().parent
EXTRACTORS_SFT_ROOT_LOCAL = MAIN_PY_DIR.parent

def resource_path(relative_path):
    return str(EXTRACTORS_SFT_ROOT_LOCAL / relative_path)

API_HENDERSON_URL = "http://localhost:5000/extract/henderson"
RABBITMQ_HOST = 'localhost'
RABBITMQ_QUEUE_NAME = 'pdf_processing_queue'
RABBITMQ_STATUS_QUEUE_NAME = 'system_status_queue'

MAIN_PDF_ENQUEUED_TOTAL = Counter(
    'main_pdf_enqueued_total',
    'Total number of PDFs enqueued for asynchronous processing.'
)

MAIN_PDF_PROCESSED_TOTAL = Counter(
    'main_pdf_processed_total',
    'Total number of PDFs processed by the main service (completed or error).',
    ['extractor', 'status']
)

MAIN_PROCESSING_DURATION_SECONDS = Histogram(
    'main_pdf_processing_duration_seconds',
    'Duration of processing a single PDF file by the main service.',
    ['extractor']
)

PROMETHEUS_METRICS_PORT = 8000
start_http_server(PROMETHEUS_METRICS_PORT)
print(f"Servidor de métricas de Prometheus iniciado en el puerto: {PROMETHEUS_METRICS_PORT}")


def load_config() -> dict:
    config_file = resource_path(os.path.join("config", "config.json"))
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        log_event("Configuración cargada correctamente.")
        return config
    except Exception as e:
        log_event(f"Error cargando configuración: {e}")
        return {}

def call_henderson_microservice(pdf_path: Path) -> pd.DataFrame:
    try:
        log_event(f"Intentando conectar con el microservicio de Henderson en: {API_HENDERSON_URL}")
        with open(pdf_path, 'rb') as f:
            files = {'pdf_file': (pdf_path.name, f.read(), 'application/pdf')}
            data = {'pdf_original_path': str(pdf_path.resolve())}

            response = requests.post(API_HENDERSON_URL, files=files, data=data, timeout=60)

        response.raise_for_status()

        data = response.json()
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            df = pd.DataFrame(data)
            log_event("Datos recibidos y convertidos a DataFrame exitosamente del microservicio Henderson.")
            return df
        else:
            raise ValueError(f"Respuesta inesperada del microservicio: {data}")

    except requests.exceptions.ConnectionError as e:
        log_event(f"ERROR: No se pudo conectar con el microservicio de Henderson. Asegúrate de que esté corriendo en {API_HENDERSON_URL}. Error: {e}")
        raise ConnectionError(f"No se pudo conectar con el microservicio de Henderson. Asegúrate de que esté corriendo. Error: {e}")
    except requests.exceptions.Timeout:
        log_event(f"ERROR: El microservicio de Henderson tardó demasiado en responder ({API_HENDERSON_URL}).")
        raise TimeoutError("El microservicio de Henderson no respondió a tiempo.")
    except requests.exceptions.RequestException as e:
        log_event(f"ERROR: Error en la solicitud al microservicio de Henderson: {e}. Respuesta: {getattr(e.response, 'text', 'No response body')}")
        raise Exception(f"Error en la solicitud al microservicio de Henderson: {e}")
    except json.JSONDecodeError as e:
        log_event(f"ERROR: Error al decodificar JSON de la respuesta del microservicio: {e}. Respuesta: {response.text if 'response' in locals() else 'N/A'}")
        raise ValueError(f"Error al decodificar JSON de la respuesta del microservicio: {e}. Respuesta: {response.text if 'response' in locals() else 'N/A'}")
    except Exception as e:
        log_event(f"ERROR: Error general al interactuar con el microservicio de Henderson: {e}")
        raise Exception(f"Error general al interactuar con el microservicio de Henderson: {e}")

def publish_message(message_body: dict):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_QUEUE_NAME, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=RABBITMQ_QUEUE_NAME,
            body=json.dumps(message_body),
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )
        log_event(f"Mensaje publicado a la cola para: {message_body.get('pdf_path')}")
        MAIN_PDF_ENQUEUED_TOTAL.inc()
        connection.close()
    except Exception as e:
        log_event(f"ERROR al publicar mensaje en la cola de procesamiento: {e}")
        raise

def publish_status_event(event_type: str, pdf_path: str, extractor_name: str = None, error_message: str = None):
    try:
        event_payload = {
            "type": event_type,
            "pdf_path": pdf_path,
            "extractor_name": extractor_name,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if error_message:
            event_payload['error_message'] = error_message

        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=RABBITMQ_STATUS_QUEUE_NAME, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=RABBITMQ_STATUS_QUEUE_NAME,
            body=json.dumps(event_payload)
        )
        connection.close()
    except Exception as e:
        log_event(f"ERROR: No se pudo publicar evento de estado a la cola '{RABBITMQ_STATUS_QUEUE_NAME}': {e}")


def get_extractor_for(pdf_path: Path, config: dict):
    import pdfplumber
    text_content = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:2]:
                ptext = page.extract_text()
                if ptext:
                    text_content += ptext.lower() + " "
    except Exception as e:
        log_event(f"Error extrayendo texto de {pdf_path.name} para detección: {e}")
        return call_henderson_microservice

    mapping = {
        "extract_GDU": extract_GDU,
        "extract_ops_ussel": extract_ops_ussel,
        "extract_res_ussel": extract_res_ussel,
        "extract_res_macro": extract_res_macro,
        "extract_ops_macro": extract_ops_macro,
        "extract_polakof": extract_polakof,
        "extract_tata": extract_tata,
        "extract_bowerey": extract_bowerey,
        "extract_henderson": call_henderson_microservice
    }

    for rule in config.get("rules", []):
        keywords = rule.get("keywords", [])
        require_all = rule.get("all", True)
        if not keywords: continue
        condition = all(k.lower() in text_content for k in keywords) if require_all else any(k.lower() in text_content for k in keywords)
        if condition:
            extractor_name = rule.get("extractor")
            if extractor_name in mapping:
                return mapping[extractor_name]

    return call_henderson_microservice

def process_file(pdf_path: Path, output_folder: Path, config: dict):
    extractor_func = None
    extractor_name = 'unknown_extractor_error'
    pdf_path_normalized = str(pdf_path.resolve())

    start_time = time.time()

    try:
        extractor_func = get_extractor_for(pdf_path, config)
        extractor_name = extractor_func.__name__

        log_event(f"Procesando archivo: {pdf_path.name}")
        log_event(f"Extractor determinado: {extractor_name}")

        if extractor_name == "call_henderson_microservice":
            log_event(f"Iniciando procesamiento SÍNCRONO para Henderson: {pdf_path.name}")
            publish_status_event("pdf_processing_started", pdf_path_normalized, extractor_name)

            df = extractor_func(pdf_path)

            if extractor_name != "extract_GDU" and any("Monto" in col for col in df.columns):
                df = transform(df)

            if df.empty or df["Referencia"].isna().all():
                mensaje = f"{pdf_path.name}: sin datos válidos para generar Excel (Henderson), se omitirá."
                print(mensaje)
                log_event(mensaje)
                publish_status_event("pdf_processing_completed", pdf_path_normalized, extractor_name)
                MAIN_PDF_PROCESSED_TOTAL.labels(extractor=extractor_name, status='completed').inc()
                return False

            output_file = output_folder / f"{pdf_path.stem}_output.xlsx"
            to_excel(df, str(output_file))
            log_event(f"Excel generado: {output_file.name}")

            validate_excel(output_file, pdf_path.name)
            log_event(f"Validación generada: {output_file.stem}_validation.txt")
            print(f"{pdf_path.stem}_output.xlsx generado.")

            publish_status_event("pdf_processing_completed", pdf_path_normalized, extractor_name)
            MAIN_PDF_PROCESSED_TOTAL.labels(extractor=extractor_name, status='completed').inc()
            return True

        else:
            log_event(f"Encolando procesamiento ASÍNCRONO para: {pdf_path.name} con {extractor_name}")
            publish_status_event("pdf_processing_started", pdf_path_normalized, extractor_name)

            message_payload = {
                "pdf_path": pdf_path_normalized,
                "extractor_name": extractor_name,
            }
            publish_message(message_payload)
            print(f"{pdf_path.name} encolado para procesamiento.")
            return True

    except Exception as e:
        error_msg = f"Error procesando {pdf_path.name}: {e}"
        print(error_msg)
        log_event(error_msg)
        publish_status_event("pdf_processing_error", pdf_path_normalized, extractor_name, str(e))
        MAIN_PDF_PROCESSED_TOTAL.labels(extractor=extractor_name, status='error').inc()
        return False
    finally:
        duration = time.time() - start_time
        MAIN_PROCESSING_DURATION_SECONDS.labels(extractor=extractor_name).observe(duration)


def procesar_archivos(pdf_paths: list[Path], output_dir: Path, config: dict) -> int:
    procesados = 0
    for pdf in pdf_paths:
        print(f"Procesando {pdf.name}...")
        if process_file(pdf, output_dir, config):
            procesados += 1
    return procesados

if __name__ == '__main__':
    pass