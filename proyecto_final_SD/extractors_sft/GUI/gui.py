import sys
import os
from pathlib import Path
import subprocess
import io
import contextlib
from typing import List, Any, Optional
import traceback

import pika
import json
import time
import datetime

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
src_dir = project_root / "src"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTextEdit, QLabel, QProgressBar, QListWidget, QListWidgetItem,
    QFrame, QStatusBar, QMessageBox, QSizePolicy, QTabWidget, QSpacerItem
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSize
from PyQt5.QtGui import QFont, QPixmap, QDragEnterEvent, QDragLeaveEvent, QDropEvent

from main import procesar_archivos, load_config, resource_path

APP_TITLE = "GRUPO CEPAS INTL. - Procesador de Archivos PDF v2.0"
HEADER_TITLE_TEXT = "Procesador de Archivos PDF"
HEADER_SUBTITLE_TEXT = "Automatización de procesamiento de PDFs y generación de reportes."
DRAG_DROP_LABEL_TEXT = "Arrastra y suelta archivos PDF aquí"
SELECTED_FILES_HEADER_TEXT = "Archivos PDF Seleccionados"
SELECT_PDFS_BTN_TEXT = "Seleccionar PDFs"
PROCESS_FILES_BTN_TEXT = "Procesar Archivos"
CLEAR_SELECTION_BTN_TEXT = "Limpiar Selección"
LOG_TAB_TEXT = "Registro de Actividad"
GENERATED_FILES_TAB_TEXT = "Archivos Generados"
OPEN_OUTPUT_DIR_BTN_TEXT = "Abrir Carpeta de Salida"
CLEAR_GENERATED_LIST_BTN_TEXT = "Limpiar Lista (Generados)"
STATUS_APP_READY = "Aplicación lista."
STATUS_PDFS_SELECTED = "PDFs seleccionados, listos para procesar."
STATUS_SELECTION_CLEARED = "Selección de PDFs limpiada."
STATUS_SELECTION_CANCELLED = "Selección de archivos cancelada."
STATUS_PROCESSING_STARTED = "Iniciando procesamiento..."
STATUS_PROCESSING_COMPLETE = "Procesamiento completo."
STATUS_PROCESSING_ERROR = "Error durante el procesamiento. Revisa el registro."
MSG_WARN_NO_PDFS = "Por favor, seleccione o arrastre archivos PDF para procesar."
MSG_ERR_OPEN_FOLDER_TITLE = "Error al abrir carpeta"
MSG_ERR_OPEN_FILE_TITLE = "Error al abrir archivo"
MSG_WARN_FILE_NOT_FOUND_TITLE = "Archivo no encontrado"
MSG_PROCESSING_ONGOING_EXIT_TITLE = "Procesamiento en Curso"
MSG_PROCESSING_ONGOING_EXIT_TEXT = ("El procesamiento de archivos aún está en curso. "
                                   "¿Está seguro de que desea salir?")
MSG_ERR_CREATE_OUTPUT_DIR_TITLE = "Error de Directorio"
MSG_ERR_CREATE_OUTPUT_DIR_TEXT = ("No se pudo crear el directorio de salida en:\n{0}\n\n"
                                  "Verifica los permisos o crea el directorio manualmente.\n"
                                  "Error: {1}")

PRIMARY_COLOR = "#3A7BD5"
PRIMARY_HOVER_COLOR = "#2F68B8"
PRIMARY_PRESSED_COLOR = "#26528F"
SECONDARY_BUTTON_COLOR = "#6A737D"
SECONDARY_BUTTON_HOVER_COLOR = "#586069"
SECONDARY_BUTTON_PRESSED_COLOR = "#4A525A"
DANGER_COLOR = "#D73A49"
DANGER_HOVER_COLOR = "#CB2431"
DANGER_PRESSED_COLOR = "#B5202B"
BACKGROUND_COLOR = "#F0F2F5"
CONTENT_BACKGROUND_COLOR = "#FFFFFF"
TEXT_PRIMARY_COLOR = "#1F2937"
TEXT_SECONDARY_COLOR = "#4B5563"
BORDER_COLOR = "#D1D5DB"
INPUT_BORDER_FOCUS_COLOR = PRIMARY_COLOR
PROGRESS_BAR_BACKGROUND_COLOR = "#E5E7EB"
DRAG_DROP_BORDER_COLOR = "#9CA3AF"
GENERAL_BORDER_RADIUS = "6px"
SLIM_BORDER_RADIUS = "4px"

SELECTED_ITEM_HIGHLIGHT_COLOR = "#DBEAFE"

DRAG_DROP_FRAME_STYLE_DEFAULT = f"""
    QFrame#dragDropFrame {{
        border: 2px dashed {DRAG_DROP_BORDER_COLOR};
        background-color: #F9FAFB;
        border-radius: {GENERAL_BORDER_RADIUS};
        padding: 25px;
    }}
    QFrame#dragDropFrame:hover {{
        border-color: {PRIMARY_COLOR};
        background-color: #EFF6FF;
    }}
"""
DRAG_DROP_FRAME_STYLE_ACTIVE = f"""
    QFrame#dragDropFrame {{
        border: 2px solid {PRIMARY_COLOR};
        background-color: #DBEAFE;
        border-radius: {GENERAL_BORDER_RADIUS};
        padding: 25px;
    }}
"""

class RabbitMQConsumerThread(QThread):
    file_generated_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self, rabbitmq_host: str, queue_name: str):
        super().__init__()
        self.rabbitmq_host = rabbitmq_host
        self.queue_name = queue_name
        self._running = True
        self.connection = None
        self.channel = None

    def run(self):
        while self._running:
            try:
                if self.connection is None or not self.connection.is_open:
                    self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.rabbitmq_host))
                    self.channel = self.connection.channel()
                    self.channel.queue_declare(queue=self.queue_name, durable=True)
                    self.log_signal.emit(f"GUI Consumer: Conectado a RabbitMQ. Escuchando '{self.queue_name}'...")

                def callback(ch, method, properties, body):
                    if not self._running:
                        ch.stop_consuming()
                        return

                    try:
                        event = json.loads(body)

                        if event.get("type") == "file_generated" and event.get("generated_file_path"):
                            generated_file_path = event["generated_file_path"]
                            self.file_generated_signal.emit(generated_file_path)
                            self.log_signal.emit(f"GUI Consumer: Archivo generado detectado: {Path(generated_file_path).name}")
                        ch.basic_ack(method.delivery_tag)
                    except Exception as e:
                        self.log_signal.emit(f"GUI Consumer ERROR en callback: {e}\n{traceback.format_exc()}")
                        ch.basic_nack(method.delivery_tag, requeue=True)

                if self.channel and self.channel.is_open:
                    self.channel.basic_consume(queue=self.queue_name, on_message_callback=callback, auto_ack=False)
                    self.channel.start_consuming()
                else:
                    self.log_signal.emit("GUI Consumer: Canal no disponible o cerrado, reintentando conexión...")
                    time.sleep(1)

            except pika.exceptions.AMQPConnectionError as e:
                self.log_signal.emit(f"GUI Consumer ERROR: No se pudo conectar a RabbitMQ: {e}. Reintentando en 5s...")
                self._close_connection()
                time.sleep(5)
            except Exception as e:
                self.log_signal.emit(f"GUI Consumer ERROR CRÍTICO: {e}\n{traceback.format_exc()}")
                self._close_connection()
                time.sleep(5)
        self.log_signal.emit("GUI Consumer: Hilo de consumo finalizado.")

    def stop(self):
        self.log_signal.emit("GUI Consumer: Solicitando detener hilo...")
        self._running = False
        if self.channel and self.channel.is_open:
            try:
                self.connection.add_callback_threadsafe(self.channel.stop_consuming)
            except Exception as e:
                self.log_signal.emit(f"GUI Consumer: Error al intentar detener consumo: {e}")
        self._close_connection()

    def _close_connection(self):
        if self.connection and self.connection.is_open:
            self.log_signal.emit("GUI Consumer: Cerrando conexión RabbitMQ...")
            try:
                self.connection.close()
            except Exception as e:
                self.log_signal.emit(f"GUI Consumer: Error al cerrar conexión: {e}")
            self.connection = None
            self.channel = None

class Worker(QThread):
    log_signal = pyqtSignal(str)
    done_signal = pyqtSignal(int, int, list)
    progress_signal = pyqtSignal(int)

    def __init__(self, pdf_paths: List[Path], output_dir: Path, config: Any):
        super().__init__()
        self.pdf_paths = pdf_paths
        self.output_dir = output_dir
        self.config = config

    def run(self):
        total_pdfs = len(self.pdf_paths)
        if total_pdfs == 0:
            self.progress_signal.emit(0)
            self.done_signal.emit(0, 0, [])
            return

        initial_files_in_output = set()
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            initial_files_in_output = {f.name for f in self.output_dir.iterdir() if f.is_file()}
        except OSError as e:
            self.log_signal.emit(f"Error Crítico: No se pudo acceder o crear el directorio de salida '{self.output_dir}': {e}")
            self.progress_signal.emit(100)
            self.done_signal.emit(0, total_pdfs, [])
            return

        log_buffer = io.StringIO()
        newly_generated_files: List[Path] = []
        log_output_from_main = ""

        try:
            self.log_signal.emit(f"Iniciando procesamiento de {total_pdfs} PDF(s)...")
            with contextlib.redirect_stdout(log_buffer):
                procesar_archivos(self.pdf_paths, self.output_dir, self.config)

            log_output_from_main = log_buffer.getvalue()
            if log_output_from_main:
                self.log_signal.emit(log_output_from_main.strip())

            current_files_in_output = {self.output_dir / f.name for f in self.output_dir.iterdir() if f.is_file()}
            for file_path in current_files_in_output:
                if file_path.name not in initial_files_in_output:
                    if file_path.suffix.lower() in ('.xlsx', '.txt'):
                        newly_generated_files.append(file_path)

            if not (self.config and self.config.get("simulated_config")):
                 self.progress_signal.emit(100)
        except Exception as e:
            self.log_signal.emit(f"ERROR CRÍTICO DURANTE EL PROCESAMIENTO: {type(e).__name__} - {e}")
            detailed_error_info = traceback.format_exc()
            self.log_signal.emit(detailed_error_info)
            log_output_before_crash = log_buffer.getvalue()
            if log_output_before_crash and not log_output_from_main:
                 self.log_signal.emit("Salida (antes del error):\n" + log_output_before_crash.strip())
        finally:
            if not (self.config and self.config.get("simulated_config")):
                self.progress_signal.emit(100)
            elif total_pdfs > 0 :
                 self.progress_signal.emit(100)
            self.done_signal.emit(len(newly_generated_files), total_pdfs, newly_generated_files)

class PDFProcessorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        if QApplication.instance():
            QApplication.instance().mainWin = self
        self.setWindowTitle(APP_TITLE)
        self.setGeometry(100, 100, 900, 750)
        try:
            self.config = load_config()
        except Exception as e:
            QMessageBox.critical(self, "Error de Configuración",
                                 f"No se pudo cargar la configuración: {e}\nLa aplicación podría no funcionar como se espera.")
            self.config = {"error_loading_config": True}
        # Asegura que output_dir apunte a la carpeta 'output' dentro de 'extractors_sft'
        self.output_dir = Path(__file__).resolve().parent.parent / "output"
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(self, MSG_ERR_CREATE_OUTPUT_DIR_TITLE,
                                 MSG_ERR_CREATE_OUTPUT_DIR_TEXT.format(self.output_dir.resolve(), e))
        self.pdf_paths: List[Path] = []
        self.worker_thread: Optional[Worker] = None
        self.processing_had_error = False
        self._apply_stylesheet()
        self._init_ui()
        self.setAcceptDrops(True)
        self.status_bar.showMessage(STATUS_APP_READY)

        RABBITMQ_HOST = 'localhost'
        RABBITMQ_STATUS_QUEUE_NAME = 'system_status_queue'
        self.consumer_thread = RabbitMQConsumerThread(RABBITMQ_HOST, RABBITMQ_STATUS_QUEUE_NAME)
        self.consumer_thread.file_generated_signal.connect(self._add_generated_file_to_list)
        self.consumer_thread.log_signal.connect(self.log)
        self.consumer_thread.start()

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {BACKGROUND_COLOR}; }}
            QWidget#centralWidget {{ padding: 15px; }}
            QLabel#headerTitle {{ font-size: 24px; font-weight: 600; color: {TEXT_PRIMARY_COLOR}; margin-bottom: 0px; }}
            QLabel#headerSubtitle {{ font-size: 14px; color: {TEXT_SECONDARY_COLOR}; margin-bottom: 15px; }}
            QLabel#sectionHeader {{ font-size: 13px; font-weight: 500; color: {TEXT_SECONDARY_COLOR}; margin-top: 10px; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.5px; }}
            QPushButton {{ background-color: {PRIMARY_COLOR}; color: white; border: none; padding: 9px 18px; border-radius: {GENERAL_BORDER_RADIUS}; font-size: 13px; font-weight: 500; }}
            QPushButton:hover {{ background-color: {PRIMARY_HOVER_COLOR}; }}
            QPushButton:pressed {{ background-color: {PRIMARY_PRESSED_COLOR}; }}
            QPushButton:disabled {{ background-color: #E5E7EB; color: #9CA3AF; }}
            QPushButton#secondaryButton {{ background-color: {SECONDARY_BUTTON_COLOR}; }}
            QPushButton#secondaryButton:hover {{ background-color: {SECONDARY_BUTTON_HOVER_COLOR}; }}
            QPushButton#secondaryButton:pressed {{ background-color: {SECONDARY_BUTTON_PRESSED_COLOR}; }}
            QPushButton#dangerButton {{ background-color: {DANGER_COLOR}; }}
            QPushButton#dangerButton:hover {{ background-color: {DANGER_HOVER_COLOR}; }}
            QPushButton#dangerButton:pressed {{ background-color: {DANGER_PRESSED_COLOR}; }} QListWidget, QTextEdit {{ background-color: {CONTENT_BACKGROUND_COLOR}; color: {TEXT_PRIMARY_COLOR}; border: 1px solid {BORDER_COLOR}; border-radius: {GENERAL_BORDER_RADIUS}; padding: 8px; font-size: 13px; }}
            QListWidget::item {{ padding: 6px 8px; }}
            QListWidget::item:hover {{ background-color: #EFF6FF; }}
            QListWidget::item:selected {{ background-color: {SELECTED_ITEM_HIGHLIGHT_COLOR}; color: {PRIMARY_COLOR}; }} QProgressBar {{ border: 1px solid {BORDER_COLOR}; border-radius: {SLIM_BORDER_RADIUS}; height: 10px; text-align: center; background-color: {PROGRESS_BAR_BACKGROUND_COLOR}; color: transparent; }}
            QProgressBar::chunk {{ background-color: {PRIMARY_COLOR}; border-radius: {SLIM_BORDER_RADIUS}; }}
            QTabWidget::pane {{ border-top: 1px solid {BORDER_COLOR}; margin-top: 0px; }}
            QTabBar::tab {{ background: {BACKGROUND_COLOR}; border: 1px solid {BORDER_COLOR}; padding: 8px 15px; margin-right: 2px; border-top-left-radius: {SLIM_BORDER_RADIUS}; border-top-right-radius: {SLIM_BORDER_RADIUS}; color: {TEXT_SECONDARY_COLOR}; }}
            QTabBar::tab:selected {{ background: {CONTENT_BACKGROUND_COLOR}; border-bottom-color: {CONTENT_BACKGROUND_COLOR}; color: {TEXT_PRIMARY_COLOR}; }}
            QTabBar::tab:hover {{ background: #E5E7EB; }}
            QFrame#inputFrame {{ background-color: {CONTENT_BACKGROUND_COLOR}; border-radius: {GENERAL_BORDER_RADIUS}; border: 1px solid {BORDER_COLOR}; }}
            QStatusBar {{ background-color: {BACKGROUND_COLOR}; color: {TEXT_SECONDARY_COLOR}; font-size: 12px; padding: 5px 12px; border-top: 1px solid {BORDER_COLOR}; }}
        """)

    def _init_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        self._setup_header_section(main_layout)
        self._setup_input_section(main_layout)
        self._setup_progress_section(main_layout)
        self._setup_output_tabs_section(main_layout)
        self._setup_status_bar()
        self.drag_drop_frame.setStyleSheet(DRAG_DROP_FRAME_STYLE_DEFAULT)
        self._update_process_button_state()

    def _setup_header_section(self, parent_layout: QVBoxLayout) -> None:
        header_layout = QHBoxLayout()
        self.logo_label = QLabel()
        logo_path = resource_path(os.path.join("GUI", "logo_cepas.png"))
        if os.path.exists(logo_path):
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                self.logo_label.setPixmap(pixmap.scaledToHeight(50, Qt.SmoothTransformation))
        else:
            self.log(f"ADVERTENCIA: Logo no encontrado en la ruta esperada: {logo_path}")
            self.logo_label.setText("LOGO")
            self.logo_label.setFixedSize(100,50)
            self.logo_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.logo_label, 0, Qt.AlignLeft | Qt.AlignTop)
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.title_label = QLabel(HEADER_TITLE_TEXT)
        self.title_label.setObjectName("headerTitle")
        title_vbox.addWidget(self.title_label)
        self.subtitle_label = QLabel(HEADER_SUBTITLE_TEXT)
        self.subtitle_label.setObjectName("headerSubtitle")
        title_vbox.addWidget(self.subtitle_label)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch(1)
        parent_layout.addLayout(header_layout)

    def _setup_input_section(self, parent_layout: QVBoxLayout) -> None:
        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_section_layout = QVBoxLayout(input_frame)
        input_section_layout.setContentsMargins(12,12,12,12)
        input_section_layout.setSpacing(10)
        self.drag_drop_frame = QFrame()
        self.drag_drop_frame.setObjectName("dragDropFrame")
        self.drag_drop_frame.setAcceptDrops(True)
        drag_drop_layout = QVBoxLayout(self.drag_drop_frame)
        drag_drop_layout.setAlignment(Qt.AlignCenter)
        self.drag_drop_label = QLabel(DRAG_DROP_LABEL_TEXT)
        self.drag_drop_label.setAlignment(Qt.AlignCenter)
        self.drag_drop_label.setWordWrap(False)
        drag_drop_layout.addWidget(self.drag_drop_label)
        input_section_layout.addWidget(self.drag_drop_frame)
        self.btn_select_pdfs = QPushButton(SELECT_PDFS_BTN_TEXT)
        self.btn_select_pdfs.clicked.connect(self.select_pdfs)
        select_button_layout = QHBoxLayout()
        select_button_layout.addStretch()
        select_button_layout.addWidget(self.btn_select_pdfs)
        select_button_layout.addStretch()
        input_section_layout.addLayout(select_button_layout)
        selected_files_label = QLabel(SELECTED_FILES_HEADER_TEXT)
        selected_files_label.setObjectName("sectionHeader")
        input_section_layout.addWidget(selected_files_label)
        self.selected_pdf_list = QListWidget()
        self.selected_pdf_list.setFixedHeight(120)
        input_section_layout.addWidget(self.selected_pdf_list)
        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.setSpacing(10)
        self.btn_clear_selection = QPushButton(CLEAR_SELECTION_BTN_TEXT)
        self.btn_clear_selection.setObjectName("secondaryButton")
        self.btn_clear_selection.clicked.connect(self.clear_selected_pdfs)
        action_buttons_layout.addWidget(self.btn_clear_selection)
        action_buttons_layout.addStretch(1)
        self.btn_process_files = QPushButton(PROCESS_FILES_BTN_TEXT)
        self.btn_process_files.clicked.connect(self.start_processing)
        action_buttons_layout.addWidget(self.btn_process_files)
        input_section_layout.addLayout(action_buttons_layout)
        parent_layout.addWidget(input_frame)

    def _setup_progress_section(self, parent_layout: QVBoxLayout) -> None:
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        parent_layout.addWidget(self.progress_bar)

    def _setup_output_tabs_section(self, parent_layout: QVBoxLayout) -> None:
        self.tab_widget = QTabWidget()
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 2, 0, 0)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Menlo", 10) if sys.platform == "darwin" else QFont("Consolas", 10))
        self.log_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_output.setMinimumHeight(150)
        log_layout.addWidget(self.log_output, stretch=1)
        self.tab_widget.addTab(log_widget, LOG_TAB_TEXT)
        generated_files_widget = QWidget()
        generated_files_layout = QVBoxLayout(generated_files_widget)
        generated_files_layout.setContentsMargins(0, 2, 0, 0)
        self.generated_files_list = QListWidget()
        self.generated_files_list.itemDoubleClicked.connect(self.open_generated_file_item)
        self.generated_files_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.generated_files_list.setMinimumHeight(150)
        generated_files_layout.addWidget(self.generated_files_list, stretch=1)
        output_buttons_layout = QHBoxLayout()
        output_buttons_layout.setSpacing(10)
        self.btn_clear_generated_list = QPushButton(CLEAR_GENERATED_LIST_BTN_TEXT)
        self.btn_clear_generated_list.setObjectName("dangerButton")
        self.btn_clear_generated_list.clicked.connect(self.clear_generated_files_display_list)
        output_buttons_layout.addWidget(self.btn_clear_generated_list)
        output_buttons_layout.addStretch(1)
        self.btn_open_output_dir = QPushButton(OPEN_OUTPUT_DIR_BTN_TEXT)
        self.btn_open_output_dir.setObjectName("secondaryButton")
        self.btn_open_output_dir.clicked.connect(self.open_output_directory)
        output_buttons_layout.addWidget(self.btn_open_output_dir)
        generated_files_layout.addLayout(output_buttons_layout)
        self.tab_widget.addTab(generated_files_widget, GENERATED_FILES_TAB_TEXT)
        parent_layout.addWidget(self.tab_widget, stretch=1)

    def _setup_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _update_process_button_state(self) -> None:
        has_pdfs = bool(self.pdf_paths)
        is_processing = self.worker_thread and self.worker_thread.isRunning()
        self.btn_process_files.setEnabled(has_pdfs and not is_processing)
        self.btn_clear_selection.setEnabled(has_pdfs and not is_processing)
        self.selected_pdf_list.setEnabled(not is_processing)
        self.btn_select_pdfs.setEnabled(not is_processing)

    def _update_generated_files_buttons_state(self) -> None:
        has_generated = self.generated_files_list.count() > 0
        is_processing = self.worker_thread and self.worker_thread.isRunning()
        self.btn_clear_generated_list.setEnabled(has_generated and not is_processing)
        self.btn_open_output_dir.setEnabled((self.output_dir.exists() and any(f.is_file() for f in self.output_dir.iterdir())) and not is_processing)


    def _add_pdfs_to_selection(self, new_pdf_paths: List[Path]) -> None:
        current_paths_in_list_widget = {self.selected_pdf_list.item(i).data(Qt.UserRole) for i in range(self.selected_pdf_list.count())}
        added_count = 0
        for pdf_path in new_pdf_paths:
            if pdf_path not in current_paths_in_list_widget:
                item = QListWidgetItem(f"{pdf_path.name} ({pdf_path.parent.name})")
                item.setData(Qt.UserRole, pdf_path)
                item.setToolTip(str(pdf_path))
                self.selected_pdf_list.addItem(item)
                self.pdf_paths.append(pdf_path)
                added_count +=1
        if added_count > 0 :
             self.log(f"Añadidos {added_count} archivos PDF a la selección. Total: {len(self.pdf_paths)}")
        self.status_bar.showMessage(STATUS_PDFS_SELECTED)
        self._update_process_button_state()

    def select_pdfs(self) -> None:
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Archivos PDF", "",
                                                "Archivos PDF (*.pdf);;Todos los archivos (*)", options=options)
        if files:
            self._add_pdfs_to_selection([Path(f) for f in files])
        else:
            self.log("Selección de archivos cancelada.")
            self.status_bar.showMessage(STATUS_SELECTION_CANCELLED)

    def clear_selected_pdfs(self) -> None:
        self.selected_pdf_list.clear()
        self.pdf_paths.clear()
        self.log("Selección de PDFs limpiada.")
        self.status_bar.showMessage(STATUS_SELECTION_CLEARED)
        self._update_process_button_state()
        self.progress_bar.setValue(0)

    def start_processing(self) -> None:
        if not self.pdf_paths:
            QMessageBox.warning(self, "Advertencia", MSG_WARN_NO_PDFS)
            return
        self.processing_had_error = False
        self.log_output.clear()
        self.generated_files_list.clear()
        self._update_process_button_state()
        self._update_generated_files_buttons_state()
        self.update_progress(0)
        self.status_bar.showMessage(STATUS_PROCESSING_STARTED)
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(self, MSG_ERR_CREATE_OUTPUT_DIR_TITLE,
                                 MSG_ERR_CREATE_OUTPUT_DIR_TEXT.format(self.output_dir.resolve(), e))
            self.processing_finished_ui_update(0, len(self.pdf_paths), [])
            self.status_bar.showMessage(STATUS_PROCESSING_ERROR)
            self.processing_had_error = True
            self._update_process_button_state()
            self._update_generated_files_buttons_state()
            return
        self.log(f"Archivos de salida se guardarán en: {self.output_dir.resolve()}")
        self.worker_thread = Worker(list(self.pdf_paths), self.output_dir, self.config)
        self.worker_thread.log_signal.connect(self.handle_worker_log)
        self.worker_thread.progress_signal.connect(self.update_progress)
        self.worker_thread.done_signal.connect(self.processing_finished_ui_update)
        self.worker_thread.start()

    def update_progress(self, value: int) -> None:
        self.progress_bar.setValue(value)

    def log(self, message: str) -> None:
        if hasattr(self, 'log_output') and self.log_output:
             self.log_output.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message.strip()}")
             self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
        else:
            print(f"LOG (log_output no listo): {message.strip()}")

    def handle_worker_log(self, message: str) -> None:
        self.log(message)
        if "ERROR CRÍTICO" in message.upper() or "ERROR:" in message.upper():
            self.processing_had_error = True

    def processing_finished_ui_update(self, processed_file_count_from_worker: int, total_pdfs_processed: int, generated_file_paths: List[Path]) -> None:
        self.log(f"\nProcesamiento finalizado.")
        actual_generated_count = len(generated_file_paths)
        if total_pdfs_processed > 0 :
            if self.processing_had_error :
                 self.log(f"Se intentaron procesar {total_pdfs_processed} PDF(s) pero ocurrieron errores.")
            else:
                self.log(f"{actual_generated_count} archivo(s) generado(s) (Henderson) de {total_pdfs_processed} PDF(s) procesado(s) por el proceso principal.")
        if generated_file_paths:
            for file_path_obj in generated_file_paths:
                item = QListWidgetItem(file_path_obj.name)
                item.setData(Qt.UserRole, file_path_obj)
                item.setToolTip(str(file_path_obj))
                self.generated_files_list.addItem(item)
        elif total_pdfs_processed > 0 and not self.processing_had_error:
            self.log("El proceso principal no generó nuevos archivos directamente en esta ejecución (posiblemente encolados).")
        self.worker_thread = None
        self._update_process_button_state()
        self._update_generated_files_buttons_state()
        if self.processing_had_error:
            self.status_bar.showMessage(STATUS_PROCESSING_ERROR)
        else:
            self.status_bar.showMessage(STATUS_PROCESSING_COMPLETE)

    def _add_generated_file_to_list(self, file_path_str: str) -> None:
        file_path_obj = Path(file_path_str)
        current_generated_paths = {self.generated_files_list.item(i).data(Qt.UserRole) for i in range(self.generated_files_list.count())}
        if file_path_obj not in current_generated_paths:
            item = QListWidgetItem(file_path_obj.name)
            item.setData(Qt.UserRole, file_path_obj)
            item.setToolTip(str(file_path_obj))
            self.generated_files_list.addItem(item)
            self.generated_files_list.sortItems()
            self._update_generated_files_buttons_state()

    def open_output_directory(self) -> None:
        path_str = str(self.output_dir.resolve())
        try:
            if sys.platform == "win32":
                os.startfile(path_str)
            elif sys.platform == "darwin":
                subprocess.run(["open", path_str], check=True)
            else:
                subprocess.run(["xdg-open", path_str], check=True)
        except Exception as e:
            QMessageBox.critical(self, MSG_ERR_OPEN_FOLDER_TITLE, f"No se pudo abrir la carpeta: {e}")
            self.log(f"ERROR al abrir carpeta '{path_str}': {e}")

    def open_generated_file_item(self, item: QListWidgetItem) -> None:
        file_path_obj = item.data(Qt.UserRole)
        if isinstance(file_path_obj, Path) and file_path_obj.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(file_path_obj))
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(file_path_obj)], check=True)
                else:
                    subprocess.run(["xdg-open", str(file_path_obj)], check=True)
            except Exception as e:
                QMessageBox.critical(self, MSG_ERR_OPEN_FILE_TITLE, f"No se pudo abrir '{file_path_obj.name}': {e}")
                self.log(f"ERROR al abrir archivo '{file_path_obj.name}': {e}")
        elif isinstance(file_path_obj, Path):
            QMessageBox.warning(self, MSG_WARN_FILE_NOT_FOUND_TITLE, f"'{file_path_obj.name}' no existe: {file_path_obj}")
            self.log(f"ADVERTENCIA: Archivo no encontrado: {file_path_obj.name} (Ruta: {file_path_obj})")
        else:
            self.log(f"ERROR: Item de lista no contiene ruta Path válida: {item.text()}")

    def clear_generated_files_display_list(self) -> None:
        self.generated_files_list.clear()
        self.log("Lista de archivos generados (visualización) limpiada.")
        self._update_generated_files_buttons_state()

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            all_pdfs_valid = True
            for url in mime_data.urls():
                if not url.isLocalFile() or Path(url.toLocalFile()).suffix.lower() != '.pdf':
                    all_pdfs_valid = False
                    break
            if all_pdfs_valid:
                event.acceptProposedAction()
                if hasattr(self, 'drag_drop_frame'):
                    self.drag_drop_frame.setStyleSheet(DRAG_DROP_FRAME_STYLE_ACTIVE)
                return
        event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        if hasattr(self, 'drag_drop_frame'):
            self.drag_drop_frame.setStyleSheet(DRAG_DROP_FRAME_STYLE_DEFAULT)
        event.accept()

    def dropEvent(self, event: QDropEvent):
        if hasattr(self, 'drag_drop_frame'):
            self.drag_drop_frame.setStyleSheet(DRAG_DROP_FRAME_STYLE_DEFAULT)
        pdf_paths_from_drop: List[Path] = []
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    local_file = Path(url.toLocalFile())
                    if local_file.suffix.lower() == '.pdf':
                        pdf_paths_from_drop.append(local_file)
        if pdf_paths_from_drop:
            self._add_pdfs_to_selection(pdf_paths_from_drop)
            event.acceptProposedAction()
        else:
            event.ignore()

    def closeEvent(self, event: Any) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            reply = QMessageBox.question(self, MSG_PROCESSING_ONGOING_EXIT_TITLE, MSG_PROCESSING_ONGOING_EXIT_TEXT,
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                if self.consumer_thread and self.consumer_thread.isRunning():
                    self.log("Cerrando hilo consumidor de RabbitMQ...")
                    self.consumer_thread.stop()
                    self.consumer_thread.wait(5000)
                    if self.consumer_thread.isRunning():
                        self.log("ADVERTENCIA: El hilo consumidor no se detuvo a tiempo.")
                event.accept()
            else:
                event.ignore()
        else:
            if self.consumer_thread and self.consumer_thread.isRunning():
                self.log("Cerrando hilo consumidor de RabbitMQ...")
                self.consumer_thread.stop()
                self.consumer_thread.wait(5000)
                if self.consumer_thread.isRunning():
                    self.log("ADVERTENCIA: El hilo consumidor no se detuvo a tiempo.")
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        if sys.platform == "darwin":
            app.setFont(QFont("SF Pro Text", 10))
        else:
            app.setFont(QFont("Roboto", 10))
    except Exception as e:
        print(f"Advertencia: No se pudieron establecer las fuentes preferidas ({e}). Usando fuente del sistema.")
    window = PDFProcessorMainWindow()
    window.show()
    sys.exit(app.exec_())