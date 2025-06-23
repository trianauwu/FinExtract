from flask import Flask, request, jsonify
import pandas as pd
import pdfplumber
import io
from pathlib import Path
import pika
import json
import datetime

from prometheus_client import Counter, Gauge, generate_latest, Histogram, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app = Flask(__name__)

RABBITMQ_HOST = 'localhost'
RABBITMQ_STATUS_QUEUE_NAME = 'system_status_queue'

HENDERSON_PDF_PROCESSING_TOTAL = Counter(
    'henderson_pdf_processing_total',
    'Número total de PDFs procesados por el microservicio Henderson.',
    ['status']
)

HENDERSON_PDF_COMPLETED_TOTAL = Counter(
    'henderson_pdf_completed_total',
    'Número total de PDFs procesados exitosamente por el microservicio Henderson.'
)

HENDERSON_PDF_ERROR_TOTAL = Counter(
    'henderson_pdf_error_total',
    'Número total de PDFs que resultaron en un error durante el procesamiento por el microservicio Henderson.'
)

HENDERSON_PROCESSING_DURATION_SECONDS = Histogram(
    'henderson_pdf_processing_duration_seconds',
    'Duración del procesamiento de PDF por el microservicio Henderson en segundos.'
)

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

def extract_henderson_logic(pdf_content_bytes: bytes) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(io.BytesIO(pdf_content_bytes)) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue

            for row in table[1:]:
                numero = (row[2] or "").strip()
                monto = (row[-1] or "").strip()

                if numero.isdigit() and monto:
                    try:
                        monto_float = float(monto.replace(",", ""))
                        rows.append({"Referencia": numero, "Monto": monto_float})
                    except ValueError:
                        continue
    return pd.DataFrame(rows)

def publish_status_event(event_type: str, pdf_path: str, extractor_name: str = "call_henderson_microservice", error_message: str = None):
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
        print(f"DEBUG Henderson: Publicado evento '{event_type}' para PDF: {pdf_path}")
    except Exception as e:
        print(f"ERROR: No se pudo publicar evento de estado desde el microservicio Henderson a la cola '{RABBITMQ_STATUS_QUEUE_NAME}': {e}")


@app.route('/extract/henderson', methods=['POST'])
def extract_henderson_api():
    if 'pdf_file' not in request.files:
        return jsonify({"error": "No se proporcionó archivo PDF"}), 400

    pdf_identifier_for_events = request.form.get('pdf_original_path')

    if not pdf_identifier_for_events:
        pdf_identifier_for_events = request.files['pdf_file'].filename
        print(f"ADVERTENCIA Henderson: pdf_original_path no recibido en la solicitud. Usando nombre de archivo: {pdf_identifier_for_events}")

    pdf_file = request.files['pdf_file']

    if pdf_file.filename == '':
        return jsonify({"error": "Nombre de archivo no válido"}), 400

    if pdf_file and pdf_file.filename.endswith('.pdf'):
        with HENDERSON_PROCESSING_DURATION_SECONDS.time():
            try:
                publish_status_event("pdf_processing_started", pdf_identifier_for_events, "call_henderson_microservice")

                df = extract_henderson_logic(pdf_file.read())

                HENDERSON_PDF_PROCESSING_TOTAL.labels(status='completed').inc()
                HENDERSON_PDF_COMPLETED_TOTAL.inc()

                publish_status_event("pdf_processing_completed", pdf_identifier_for_events, "call_henderson_microservice")
                return jsonify(df.to_dict(orient='records')), 200
            except Exception as e:
                error_msg = f"Error al procesar el PDF: {str(e)}"
                HENDERSON_PDF_PROCESSING_TOTAL.labels(status='error').inc()
                HENDERSON_PDF_ERROR_TOTAL.inc()

                publish_status_event("pdf_processing_error", pdf_identifier_for_events, "call_henderson_microservice", error_msg)
                return jsonify({"error": error_msg}), 500
    else:
        return jsonify({"error": "Tipo de archivo no soportado. Se esperaba un archivo PDF."}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)