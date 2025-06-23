## Proyecto de Automatización de Extracción de Datos desde PDFs Financieros ##

Este proyecto tiene como objetivo automatizar la extracción y estructuración de datos clave provenientes de archivos PDF generados por diferentes cadenas comerciales. En particular, se busca estandarizar los números de documento (facturas, resguardos) y los montos asociados, independientemente del formato o proveedor original, para facilitar su integración con procesos contables y de control financiero internos.

A la fecha, el sistema desarrollado permite:

- Procesamiento automático de archivos PDF depositados en una carpeta de entrada (`/data`), sin requerir intervención manual.  
- Extracción precisa de información estructurada:  
  - Números de factura o referencia (estandarizados con prefijos `A-00`, `A-0`, `B-` según longitud y contenido).  
  - Montos asociados, con soporte para formato europeo (`1.234,56`) y valores negativos.  
- Conversión de montos a formato local:  
  - Eliminación de separador de miles.  
  - Reemplazo del punto decimal por coma.  
  - Conservación del signo negativo.  
- Tratamiento específico por cadena comercial, mediante extractores dedicados para:  
  - Ta-Ta (resguardos electrónicos)  
  - Macromercado (órdenes de pago y resguardos)  
  - Polakof  
  - Henderson  
  - Bowerey  
  - Ussel

- En el caso de resguardos de Macromercado, se aplica una regla de negocio específica: si el número de documento no comienza con "A1", se toma el valor de la columna "Importe Base" y se multiplica por `1.22`. El ajuste se informa explícitamente en una columna adicional (`Ajustado = "Sí"`).  
- Generación de archivos Excel individuales por cada PDF procesado, depositados automáticamente en una carpeta de salida (`/output`).  
- Validaciones internas para descartar documentos vacíos o sin datos relevantes, evitando archivos incorrectos o sin valor contable.

# Arquitectura del Sistema #

El sistema fue diseñado en Python 3.11, con una arquitectura modular y extensible. A continuación se resume su estructura:

sft_cadenas/
│
├── data/                   # PDFs de entrada  
├── output/                 # Excels generados  
│
├── main.py                 # Script principal  
├── transformer.py          # Lógica de estandarización de datos  
├── excel_generator.py      # Exportación a Excel  
│
├── extractor_henderson.py  
├── extractor_polakof.py  
├── extractor_tata.py  
├── extractor_macro_ops.py  
├── extractor_macro_res.py  
├── extractor_bowerey.py  
└── extractor_ussel_res.py

Cada extractor fue diseñado para adaptarse a la estructura específica de los documentos emitidos por la cadena correspondiente.

-- Estado Actual --

El sistema está funcionando correctamente con los formatos actualmente utilizados por:

| Cadena Comercial | Tipo de Documento | Estado       |
|------------------|--------------------|--------------|
| Henderson         | Orden de Pago       | Implementado |
| Polakof           | Orden de Pago       | Implementado |
| Ta-Ta             | Resguardo           | Implementado |
| Macromercado      | Orden de Pago       | Implementado |
| Macromercado      | Resguardo           | Implementado |
| Bowerey           | Resguardo           | Implementado |
| USSEL             | Resguardo           | Implementado |

El sistema ha sido validado con múltiples ejemplos reales por cadena.

-- Requerimientos Técnicos --

El entorno de desarrollo incluye:

- Python 3.11  
- Librerías:  
  - pandas  
  - pdfplumber  
  - re (expresiones regulares)  
- Visual Studio Code (se recomienda contar con la extensión Excel Viewer para facilitar la validación de salidas generadas)

-- Próximos Pasos --

1. Incorporación de validaciones inteligentes:  
   - Módulo de control de calidad para detectar y reportar incongruencias sin descartar filas.  
2. Consolidación de múltiples PDFs en un único Excel, con hoja por proveedor o resumen agregado.  
3. Interfaz de usuario (UI) simple para operadores no técnicos (posiblemente en Python + Tkinter o PySimpleGUI).  
4. Empaquetado como ejecutable (.exe) para facilitar su distribución y ejecución fuera del entorno de desarrollo.  
5. Implementación de tests unitarios para verificar la consistencia entre extractores y garantizar compatibilidad futura.  

Nota: actualmente se emplean íconos en la salida por consola (como símbolos de advertencia o confirmación) para facilitar la legibilidad del flujo de procesamiento durante pruebas. Estos pueden ser retirados fácilmente si se requiere en ambientes productivos.

Puede probarse el programa ejecutando el archivo `main.py`. Los PDFs deben colocarse en la carpeta `data/` y los Excel generados se ubicarán automáticamente en `output/`.

Funciones logger:
- python src/logger.py --date "2025-04-10" --end-date "2025-04-10"
- python src/logger.py --keyword "procesando"

Usar batch_processor:
- python src/batch_processor.py --input "data" --output "output"
