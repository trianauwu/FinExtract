# FinExtract – Sistema de Procesamiento de Documentos PDF

**Autores:** Marina Ramos, Mikela Scotti, Arturo Cornes, Erika Puhl y Triana Correa 

## Visión General del Proyecto

FinExtract es una robusta aplicación de escritorio diseñada para automatizar la extracción, transformación, validación y reporte de datos financieros de documentos PDF de diversos proveedores. Su objetivo principal es optimizar la gestión de datos, reducir la carga de trabajo manual y garantizar la precisión en el procesamiento de información crítica para Grupo Cepas.

### Características Principales

* **Extracción Multi-Proveedor:** Soporte para extracción de datos de PDFs de Henderson, Polakof, Tata, Macro, Ussel, Bowerey y GDU.
* **Procesamiento Híbrido:**
    * **Síncrono:** Comunicación directa vía API REST con el microservicio Henderson para resultados inmediatos.
    * **Asíncrono:** Utilización de colas RabbitMQ para procesar otros tipos de documentos en segundo plano, garantizando escalabilidad y robustez.
* **Transformación y Validación de Datos:** Módulos dedicados para limpiar, estandarizar y validar la información extraída, asegurando la calidad de los datos.
* **Generación de Reportes:** Creación automática de archivos Excel (.xlsx) y reportes de validación (.txt) con los datos procesados.
* **Interfaz Gráfica de Usuario (GUI):** Aplicación de escritorio intuitiva para la selección de archivos, visualización de logs y gestión de archivos generados.
* **Monitoreo de Operaciones:** Exposición de métricas de rendimiento a través de Prometheus para una supervisión detallada de la aplicación y sus componentes.
* **Notificaciones de Estado:** Actualizaciones en tiempo real sobre el progreso y el estado de los procesos de extracción y generación de archivos.

## Arquitectura del Sistema (Ejecución Local)

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
```FinExtract/
├── henderson_microservice/       # Microservicio Flask para Henderson
│   ├── app_h.py                  # Lógica del servidor Flask
│   └── requirements.txt          # Dependencias de Python para Henderson
├── extractors_sft/               # Módulo principal de Extractores SFT
│   ├── GUI/                      # Archivos de la interfaz gráfica (gui.py, logo_cepas.png)
│   │   └── gui.py
│   ├── config/                   # Archivos de configuración (config.json)
│   │   └── config.json
│   ├── data/                     # Carpeta para colocar PDFs de entrada (¡crear si no existe!)
│   ├── output/                   # Carpeta donde se guardarán los Excels y validaciones (¡crear si no existe!)
│   ├── src/                      # Código fuente de los extractores, transformadores, etc.
│   │   ├── main.py               # Orquestador principal y encolador
│   │   ├── local_processor_service.py # Consumidor de RabbitMQ para procesamiento asíncrono
│   │   ├── extractor_polakof.py
│   │   ├── ... (otros extractores)
│   │   └── (otros módulos: transformer.py, excel_generator.py, validator.py, logger.py)
│   └── requirements.txt          # Dependencias de Python para extractores SFT y GUI
├── tools/                        # Herramientas y ejecutables externos
│   ├── prometheus/               # Ejecutable y configuración de Prometheus Server
│   │   ├── prometheus.exe
│   │   └── prometheus.yml        # Archivo de configuración de Prometheus
│   └── grafana/                  # Ejecutable de Grafana (si no se instaló como servicio)
│       └── bin/grafana.exe
└── .gitignore                    # Archivo para ignorar directorios y archivos en Git
```
## Guía de Configuración y Ejecución Local

Sigue estos pasos detallados para poner en marcha el proyecto FinExtract en tu máquina local.

### 1. Clonar el Repositorio

Abre tu terminal (PowerShell o CMD) y ejecuta:

```git clone [https://github.com/tu_usuario/FinExtract.git](https://github.com/tu_usuario/FinExtract.git)
cd FinExtract
```

2. Preparar las Carpetas de Datos y Salida
Dentro del directorio extractors_sft/, asegúrate de que existan las carpetas data/ y output/. Estas se usarán para los PDFs de entrada y los archivos de salida generados.

cd extractors_sft
mkdir data
mkdir output
cd .. # Volver a la raíz del proyecto
