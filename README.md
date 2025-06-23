# 📊 FinExtract – Sistema de Procesamiento de Documentos PDF

**Autor:** [Tu Nombre/Alias]
**Contacto:** [Tu Email o Perfil de LinkedIn/GitHub]
**Versión:** 2.0 (Local-First)

## ✨ Visión General del Proyecto

FinExtract es una robusta aplicación de escritorio diseñada para automatizar la extracción, transformación, validación y reporte de datos financieros de documentos PDF de diversos proveedores. Su objetivo principal es optimizar la gestión de datos, reducir la carga de trabajo manual y garantizar la precisión en el procesamiento de información crítica para Grupo Cepas.

### 🚀 Características Principales

* **Extracción Multi-Proveedor:** Soporte para extracción de datos de PDFs de Henderson, Polakof, Tata, Macro, Ussel, Bowerey y GDU.
* **Procesamiento Híbrido:**
    * **Síncrono:** Comunicación directa vía API REST con el microservicio Henderson para resultados inmediatos.
    * **Asíncrono:** Utilización de colas RabbitMQ para procesar otros tipos de documentos en segundo plano, garantizando escalabilidad y robustez.
* **Transformación y Validación de Datos:** Módulos dedicados para limpiar, estandarizar y validar la información extraída, asegurando la calidad de los datos.
* **Generación de Reportes:** Creación automática de archivos Excel (.xlsx) y reportes de validación (.txt) con los datos procesados.
* **Interfaz Gráfica de Usuario (GUI):** Aplicación de escritorio intuitiva para la selección de archivos, visualización de logs y gestión de archivos generados.
* **Monitoreo de Operaciones:** Exposición de métricas de rendimiento a través de Prometheus para una supervisión detallada de la aplicación y sus componentes.
* **Notificaciones de Estado:** Actualizaciones en tiempo real sobre el progreso y el estado de los procesos de extracción y generación de archivos.

## 📦 Arquitectura del Sistema (Ejecución Local)

El proyecto FinExtract está compuesto por varios módulos interconectados, diseñados para ejecutarse localmente en tu sistema operativo Windows:

* **`gui.py`:** La interfaz gráfica principal (frontend) para la interacción del usuario.
* **`main.py`:** El controlador central que orquesta el flujo de procesamiento, detecta el tipo de extractor y decide si el procesamiento es síncrono o asíncrono. También expone métricas de Prometheus.
* **Microservicio Henderson (`app_h.py`):** Un servidor Flask ligero que maneja la lógica de extracción específica para documentos Henderson, ofreciendo una API REST. Expone métricas de Prometheus.
* **`local_processor_service.py`:** Un worker (consumidor de RabbitMQ) que procesa de forma asíncrona los documentos para extractores que no son Henderson. Expone métricas de Prometheus.
* **Módulos de `src/`:** Incluye la lógica de extractores individuales, transformadores, generadores de Excel, validadores y el sistema de logging.
* **RabbitMQ:** Un broker de mensajes utilizado para la comunicación asíncrona entre `main.py` y `local_processor_service.py`, así como para eventos de estado.
* **Prometheus:** Un sistema de monitoreo y alerta que recolecta métricas de todos los componentes Python.
* **Grafana:** Una plataforma de visualización que se conecta a Prometheus para crear dashboards interactivos con las métricas del sistema.

### Estructura de Carpetas
