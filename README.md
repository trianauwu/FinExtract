# FinExtract – Sistema de Procesamiento de Documentos 

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

```bash
git clone [https://github.com/tu_usuario/FinExtract.git](https://github.com/tu_usuario/FinExtract.git)
cd FinExtract
```
### 2. Preparar las Carpetas de Datos y Salida
Dentro del directorio extractors_sft/, asegúrate de que existan las carpetas data/ y output/. Estas se usarán para los PDFs de entrada y los archivos de salida generados.

### 3. Configurar Entornos Virtuales e Instalar Dependencias Python
Es altamente recomendado usar entornos virtuales para aislar las dependencias de cada módulo.

a. Para el Microservicio de Henderson (henderson_microservice)
#### 1. Navegar al directorio:

```cd henderson_microservice```

#### 2. Crear el entorno virtual:

```python -m venv venv```

#### 3. Activar el entorno virtual:

``` # En Windows (CMD/PowerShell):
.\venv\Scripts\activate.bat
```
#### 4. Instalar dependencias:

```pip install -r requirements.txt```

#### 5. Desactivar el entorno virtual:

```deactivate```

#### Volver a la raíz del proyecto:

```cd ..```

b. Para los Servicios de Extracción SFT (extractors_sft, incluyendo GUI/Main/Local Processor)
#### 1. Navegar al directorio:

```cd extractors_sft```

#### 2. Crear el entorno virtual:

```python -m venv venv```

#### 3. Activar el entorno virtual:

```# En Windows (CMD/PowerShell):
.\venv\Scripts\activate.bat
```

#### 4. Instalar dependencias:

```pip install -r requirements.txt```

#### 5. Desactivar el entorno virtual:

```deactivate```

#### 6. Volver a la raíz del proyecto:

```cd ..```

## 4. Instalar y Configurar Servicios Externos
### a. RabbitMQ
Necesitas un servidor RabbitMQ ejecutándose localmente.

#### Opción 1: Instalación Nativa (Recomendado para producción local)

Descarga e instala Erlang (requisito previo para RabbitMQ).
Descarga e instala RabbitMQ Server para Windows.
Asegúrate de que el servicio de RabbitMQ esté iniciado (puedes verificar en services.msc).
Habilita el plugin de gestión para la interfaz web y métricas (en una terminal de administrador, navega al directorio sbin de tu instalación de RabbitMQ y ejecuta rabbitmq-plugins enable rabbitmq_management).
Debería estar accesible en http://localhost:15672 (usuario/pass: guest/guest).

#### Opción 2: Usar Docker para RabbitMQ (Más Rápido para desarrollo)

Asegúrate de tener Docker Desktop instalado y funcionando.
Abre una terminal (PowerShell o CMD) y ejecuta:

```docker run -d --name finextract_rabbitmq -p 5672:5672 -p 15672:15672 -p 15692:15692 rabbitmq:3.12-management-alpine
```
Este contenedor se iniciará en segundo plano. Puedes verificar su estado con docker ps.

### b. Prometheus
Descarga el ejecutable de Prometheus Server para Windows:

Ve a https://prometheus.io/download/ y descarga la versión windows-amd64.zip.
Descomprime el contenido (incluyendo prometheus.exe y prometheus.yml de ejemplo) en la carpeta FinExtract/tools/prometheus/.
Configura FinExtract/tools/prometheus/prometheus.yml:

Abre el archivo prometheus.yml en esa carpeta y asegúrate de que contenga la configuración para raspar tus servicios locales:

```global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'rabbitmq'
    static_configs:
      - targets: ['localhost:15692']

  - job_name: 'henderson_microservice'
    static_configs:
      - targets: ['localhost:5000']
        labels:
          application: henderson

  - job_name: 'local_processor'
    static_configs:
      - targets: ['localhost:8001']
        labels:
          application: local_processor

  - job_name: 'main_service'
    static_configs:
      - targets: ['localhost:8000']
        labels:
          application: main
```
## c. Grafana
### Descarga el instalador de Grafana para Windows:
Ve a https://grafana.com/grafana/download/ y descarga el instalador .msi para Windows.

### Instala Grafana:
Ejecuta el instalador. Grafana se instalará como un Servicio de Windows.
Una vez instalado, asegúrate de que el servicio de Grafana esté iniciado a través del Administrador de Tareas (pestaña "Servicios") o la aplicación "Servicios" (services.msc).

### Configurar Prometheus como Fuente de Datos en Grafana (una vez en el navegador):
Abre http://localhost:3000 en tu navegador (usuario/contraseña por defecto: admin/admin - se pedirá cambiarla en el primer inicio de sesión).
Ve a "Connections" -> "Data sources" -> "Add new data source" y selecciona "Prometheus".
En el campo "URL", ingresa http://localhost:9090 (la dirección de tu Prometheus local).
Haz clic en "Save & test".

## 5. Ejecutar los Servicios del Proyecto FinExtract
Abre cuatro terminales separadas (CMD o PowerShell) para ejecutar cada componente Python y Prometheus. Grafana se ejecuta como un servicio de Windows.

### Terminal 1: Microservicio de Henderson (app_h.py)

```cd henderson_microservice
.\venv\Scripts\activate.bat
python app_h.py
```

### Terminal 2: Servicio de Procesamiento Local (local_processor_service.py)

```cd extractors_sft
.\venv\Scripts\activate.bat
python src\local_processor_service.py
```
### Terminal 3: Servidor Prometheus

```cd tools\prometheus
.\prometheus.exe --config.file=prometheus.yml
```
### Terminal 4: Aplicación GUI (gui.py)

```cd extractors_sft
.\venv\Scripts\activate.bat
python GUI\gui.py
```

### 6. Acceso a las Interfaces y Uso de la Aplicación

Con todos los servicios ejecutándose:

RabbitMQ Management: http://localhost:15672 (user: guest, pass: guest)
Prometheus UI: http://localhost:9090 (Verifica "Status" -> "Targets" para asegurar que todos tus servicios estén "UP").
Grafana UI: http://localhost:3000
Aplicación FinExtract GUI: Utiliza la ventana de la GUI para seleccionar y procesar tus PDFs. Observa los logs en las terminales para ver el flujo de trabajo.







`
