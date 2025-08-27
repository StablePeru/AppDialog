# main_window.py

import os
import sys
import subprocess

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QFileDialog, QMessageBox, QSpacerItem,
    QSizePolicy, QFrame, QListWidget, QListWidgetItem # QTextEdit ya no es necesario
)
from PySide6.QtCore import Qt, QThread, Slot, QUrl, QTimer, QMetaObject
from PySide6.QtGui import QIcon, QDropEvent, QDragEnterEvent

# Importar configuraciones y worker principal
from config import HEADER_DEFAULTS, ICON_PATH
# Ya no importamos PREVIEW_LINES
from conversion_worker import ConversionWorker # Ya no importamos PreviewWorker

class MainWindow(QWidget):
    """Ventana principal sin previsualización."""

    def __init__(self):
        super().__init__()
        self.file_list = []
        self.current_conversion_index = -1
        self.active_worker = None
        self.active_thread = None
        # self.preview_worker = None # Eliminado
        # self.preview_thread = None # Eliminado
        self._cancel_requested = False
        # self.preview_debounce_timer = QTimer(self) # Eliminado
        # self.preview_debounce_timer.setSingleShot(True) # Eliminado
        # self.preview_debounce_timer.setInterval(300) # Eliminado
        # self.preview_debounce_timer.timeout.connect(self._trigger_preview_generation) # Eliminado
        self.initUI()
        self.load_app_icon()
        self.setAcceptDrops(True)

    def initUI(self):
        self.setWindowTitle("Conversor Excel a TXT Pro (Lotes)")
        # Ajustar tamaño si es necesario ahora que no hay preview
        self.setGeometry(150, 150, 750, 680)
        self.setMinimumSize(650, 550)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- Layout Superior AHORA SOLO CONTIENE LA LISTA ---
        list_v_layout = QVBoxLayout() # Layout vertical para la lista y sus botones
        list_v_layout.setSpacing(8)

        lbl_select_file = QLabel("1. Archivos a Procesar (Arrastra aquí)")
        lbl_select_file.setObjectName("sectionHeader")
        list_v_layout.addWidget(lbl_select_file)

        self.file_list_widget = QListWidget()
        self.file_list_widget.setObjectName("fileList")
        self.file_list_widget.setAlternatingRowColors(False)
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        # self.file_list_widget.itemSelectionChanged.connect(...) # Eliminada conexión

        # Hacer que la lista ocupe más espacio vertical
        list_v_layout.addWidget(self.file_list_widget, 1) # Stretch factor > 0

        list_buttons_h_layout = QHBoxLayout()
        btn_add_files = QPushButton("Añadir Archivo(s)..."); btn_add_files.clicked.connect(self.add_files)
        btn_remove_selected = QPushButton("Quitar Seleccionado(s)"); btn_remove_selected.clicked.connect(self.remove_selected_files)
        btn_clear_list = QPushButton("Limpiar Lista"); btn_clear_list.clicked.connect(self.clear_file_list)
        list_buttons_h_layout.addWidget(btn_add_files); list_buttons_h_layout.addWidget(btn_remove_selected); list_buttons_h_layout.addStretch(); list_buttons_h_layout.addWidget(btn_clear_list)
        list_v_layout.addLayout(list_buttons_h_layout)

        # Añadir directamente el layout de la lista al layout principal
        main_layout.addLayout(list_v_layout, 1) # Stretch factor > 0

        # --- 2. Sección Información Cabecera (sin cambios estructurales) ---
        lbl_header_info = QLabel("2. Información de Cabecera (Opcional)")
        lbl_header_info.setObjectName("sectionHeader")
        main_layout.addWidget(lbl_header_info)
        header_section_frame = QFrame()
        header_layout = QFormLayout(header_section_frame); header_layout.setContentsMargins(5, 5, 5, 5); header_layout.setHorizontalSpacing(15); header_layout.setVerticalSpacing(12)
        self.title_entry = QLineEdit(HEADER_DEFAULTS["Título"]); self.chapter_entry = QLineEdit(HEADER_DEFAULTS["Capítulo"]); self.translator_entry = QLineEdit(HEADER_DEFAULTS["Traductor"]); self.takeo_entry = QLineEdit(HEADER_DEFAULTS["Takeo"])
        header_layout.addRow("Título:", self.title_entry); header_layout.addRow("Capítulo:", self.chapter_entry); header_layout.addRow("Traductor:", self.translator_entry); header_layout.addRow("Takeo:", self.takeo_entry)
        main_layout.addWidget(header_section_frame)

        # --- Espaciador Flexible (sin cambios) ---
        main_layout.addSpacerItem(QSpacerItem(20, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # --- 3. Botones de Acción (sin cambios) ---
        action_layout = QHBoxLayout(); action_layout.setSpacing(15); action_layout.addStretch()
        self.cancel_button = QPushButton("Cancelar Lote"); self.cancel_button.setObjectName("cancelButton"); self.cancel_button.clicked.connect(self.request_batch_cancel); self.cancel_button.setEnabled(False); self.cancel_button.setMinimumSize(120, 35)
        action_layout.addWidget(self.cancel_button)
        self.convert_button = QPushButton("Convertir Archivos"); self.convert_button.setObjectName("convertButton"); self.convert_button.setEnabled(False); self.convert_button.clicked.connect(self.start_batch_conversion); self.convert_button.setMinimumSize(180, 45)
        action_layout.addWidget(self.convert_button); action_layout.addStretch(); main_layout.addLayout(action_layout)

        # --- 4. Progreso y Estado (sin cambios) ---
        line_sep = QFrame(); line_sep.setFrameShape(QFrame.Shape.HLine); line_sep.setFrameShadow(QFrame.Shadow.Sunken); main_layout.addWidget(line_sep)
        status_layout = QVBoxLayout(); status_layout.setSpacing(5)
        progress_text_layout = QHBoxLayout()
        self.global_status_label = QLabel("Listo."); self.global_status_label.setObjectName("statusLabel"); self.global_status_label.setWordWrap(True)
        self.detailed_status_label = QLabel(""); self.detailed_status_label.setObjectName("statusLabel"); self.detailed_status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        progress_text_layout.addWidget(self.global_status_label, 1); progress_text_layout.addWidget(self.detailed_status_label)
        status_layout.addLayout(progress_text_layout)
        self.progress_bar = QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0); self.progress_bar.setTextVisible(False); self.progress_bar.setEnabled(False)
        status_layout.addWidget(self.progress_bar); main_layout.addLayout(status_layout)


    # --- Drag and Drop (sin cambios) ---
    def dragEnterEvent(self, event: QDragEnterEvent): # ... (idéntico) ...
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.isLocalFile() and url.toLocalFile().lower().endswith('.xlsx') for url in urls): event.acceptProposedAction()
            else: event.ignore()
        else: event.ignore()
    def dropEvent(self, event: QDropEvent): # ... (idéntico) ...
        urls = event.mimeData().urls(); added_files = []
        for url in urls:
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if file_path.lower().endswith('.xlsx') and file_path not in self.file_list:
                    added_files.append(file_path); self.file_list.append(file_path)
                    item = QListWidgetItem(os.path.basename(file_path)); item.setData(Qt.ItemDataRole.UserRole, file_path); item.setToolTip(file_path)
                    self.file_list_widget.addItem(item)
        if added_files: self.update_ui_state(); print(f"Archivos añadidos por Drag&Drop: {len(added_files)}")
        event.acceptProposedAction()

    # --- Lógica de manejo de lista ---
    @Slot()
    def add_files(self): # ... (idéntico) ...
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Archivos Excel", "", "Archivos Excel (*.xlsx);;Todos (*.*)")
        added_count = 0
        if files:
            for file_path in files:
                if file_path not in self.file_list:
                    self.file_list.append(file_path); item = QListWidgetItem(os.path.basename(file_path)); item.setData(Qt.ItemDataRole.UserRole, file_path); item.setToolTip(file_path)
                    self.file_list_widget.addItem(item); added_count += 1
            if added_count > 0: self.update_ui_state()
    @Slot()
    def remove_selected_files(self): # ... (idéntico, ya no llama a clear_preview) ...
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items: return
        for item in selected_items:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path in self.file_list: self.file_list.remove(file_path)
            self.file_list_widget.takeItem(self.file_list_widget.row(item))
        self.update_ui_state()
    @Slot()
    def clear_file_list(self): # ... (idéntico, ya no llama a clear_preview) ...
        self.file_list.clear(); self.file_list_widget.clear()
        self.update_ui_state()

    # --- Lógica de Previsualización ELIMINADA ---
    # @Slot()
    # def on_list_selection_changed_debounce(self): ...
    # @Slot()
    # def _trigger_preview_generation(self): ...
    # def generate_preview(self, file_path): ...
    # @Slot(str)
    # def show_preview(self, preview_content): ...
    # def clear_preview(self): ...

    # --- Lógica de Conversión por Lotes (sin cambios) ---
    def _get_header_data(self): # ... (idéntico) ...
        return { "Título": self.title_entry.text().strip() or HEADER_DEFAULTS["Título"], "Capítulo": self.chapter_entry.text().strip() or HEADER_DEFAULTS["Capítulo"], "Traductor": self.translator_entry.text().strip() or HEADER_DEFAULTS["Traductor"], "Takeo": self.takeo_entry.text().strip() or HEADER_DEFAULTS["Takeo"] }
    @Slot()
    def start_batch_conversion(self): # ... (idéntico) ...
        if not self.file_list: QMessageBox.warning(self, "Lista Vacía", "Añade archivos a la lista antes de convertir."); return
        self._cancel_requested = False; self.current_conversion_index = 0
        self.set_ui_for_conversion(True); self.start_next_conversion()
    def start_next_conversion(self): # ... (idéntico) ...
        if self._cancel_requested: self.batch_finished(cancelled=True); return
        if self.current_conversion_index >= len(self.file_list): self.batch_finished(cancelled=False); return
        file_path = self.file_list[self.current_conversion_index]
        total_files = len(self.file_list)
        self.global_status_label.setText(f"Procesando Archivo {self.current_conversion_index + 1}/{total_files}...")
        self.detailed_status_label.setText(f"Iniciando: {os.path.basename(file_path)}")
        list_item = self.file_list_widget.item(self.current_conversion_index);
        if list_item: self.file_list_widget.setCurrentItem(list_item)
        header_data = self._get_header_data(); output_directory = os.path.dirname(file_path)
        self.active_thread = QThread(self); self.active_worker = ConversionWorker(file_path, output_directory, header_data); self.active_worker.moveToThread(self.active_thread)
        self.active_worker.progress_update.connect(self.update_global_status); self.active_worker.detailed_progress.connect(self.update_detailed_status); self.active_worker.progress_value.connect(self.update_progress)
        self.active_worker.finished.connect(self.single_conversion_finished)
        self.active_thread.started.connect(self.active_worker.run); self.active_thread.finished.connect(self.active_worker.deleteLater); self.active_thread.finished.connect(self.active_thread.deleteLater)
        self.active_thread.start()
    @Slot(bool, str, str)
    def single_conversion_finished(self, success, message_or_path, original_path): # ... (idéntico) ...
        calling_thread = self.sender().thread()
        if calling_thread == self.active_thread: self.active_thread = None; self.active_worker = None
        else: print("Warning: Señal finished recibida de un hilo/worker inesperado.")
        if not success and "Cancelado" not in message_or_path: QMessageBox.warning(self, "Error en Archivo", f"Ocurrió un error al procesar:\n{os.path.basename(original_path)}\n\n{message_or_path}\n\nContinuando con el siguiente...")
        elif "Cancelado" in message_or_path : self._cancel_requested = True
        self.current_conversion_index += 1; QTimer.singleShot(50, self.start_next_conversion)
    def batch_finished(self, cancelled=False): # ... (idéntico) ...
        print(f"Proceso por lotes finalizado. Cancelado: {cancelled}"); self.set_ui_for_conversion(False); self.progress_bar.setValue(0)
        if cancelled: self.global_status_label.setText("Proceso cancelado por el usuario."); self.detailed_status_label.setText("")
        else: self.global_status_label.setText(f"Proceso completado. {len(self.file_list)} archivo(s) procesado(s)."); self.detailed_status_label.setText("¡Éxito!"); QMessageBox.information(self, "Lote Completado", f"Se procesaron {len(self.file_list)} archivo(s).")
        self.current_conversion_index = -1; self._cancel_requested = False; self.active_thread = None; self.active_worker = None
    @Slot()
    def request_batch_cancel(self): # ... (idéntico) ...
        if self.active_thread and self.active_thread.isRunning():
            print("Solicitando cancelación del lote..."); self._cancel_requested = True
            self.global_status_label.setText("Cancelando proceso..."); self.detailed_status_label.setText("Esperando finalización del archivo actual...")
            self.cancel_button.setEnabled(False)
            if self.active_worker and hasattr(self.active_worker, 'request_cancel'): QMetaObject.invokeMethod(self.active_worker, "request_cancel", Qt.ConnectionType.QueuedConnection)
        else: print("No hay conversión activa para cancelar.")

    # --- Slots de Actualización de UI (sin cambios) ---
    @Slot(str)
    def update_global_status(self, message): # ... (idéntico) ...
        total_files = len(self.file_list); current_file_num = self.current_conversion_index + 1
        if 0 <= self.current_conversion_index < total_files: prefix = f"Archivo {current_file_num}/{total_files}: "; self.global_status_label.setText(prefix + message)
        else: self.global_status_label.setText(message)
    @Slot(str)
    def update_detailed_status(self, message): self.detailed_status_label.setText(message) # ... (idéntico) ...
    @Slot(int)
    def update_progress(self, value): # ... (idéntico) ...
        if value < 0:
             if self.progress_bar.maximum() != 0: self.progress_bar.setRange(0, 0)
             self.progress_bar.setValue(-1); self.progress_bar.setEnabled(True)
        else:
            if self.progress_bar.maximum() == 0: self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value); self.progress_bar.setEnabled(True)

    # --- Otros Métodos ---
    def set_ui_for_conversion(self, converting): # ... (idéntico, ya no deshabilita preview) ...
        enabled = not converting
        self.file_list_widget.setEnabled(enabled)
        for btn in self.findChildren(QPushButton):
             if btn.objectName() not in ["convertButton", "cancelButton"]: btn.setEnabled(enabled)
        self.title_entry.setEnabled(enabled); self.chapter_entry.setEnabled(enabled); self.translator_entry.setEnabled(enabled); self.takeo_entry.setEnabled(enabled)
        self.convert_button.setEnabled(enabled and self.file_list_widget.count() > 0); self.cancel_button.setEnabled(converting)
        self.progress_bar.setEnabled(converting);
        if not converting: self.progress_bar.setValue(0)
    def update_ui_state(self): # ... (idéntico, ya no llama a clear_preview) ...
        has_files = self.file_list_widget.count() > 0
        is_converting = self.active_thread is not None and self.active_thread.isRunning()
        self.convert_button.setEnabled(has_files and not is_converting)
        # if not has_files: self.clear_preview() # Ya no es necesario

    def load_app_icon(self): # ... (idéntico) ...
        if os.path.exists(ICON_PATH): self.setWindowIcon(QIcon(ICON_PATH))
        else: print(f"Warning: Icono no encontrado '{ICON_PATH}'")
    def open_output_location(self, file_path): # ... (idéntico) ...
        try:
            output_dir = os.path.dirname(file_path)
            if sys.platform == 'win32': os.startfile(output_dir)
            elif sys.platform == 'darwin': subprocess.Popen(['open', output_dir])
            else: subprocess.Popen(['xdg-open', output_dir])
        except Exception as e: print(f"No se pudo abrir la carpeta: {e}"); QMessageBox.warning(self, "Abrir Carpeta", f"No se pudo abrir:\n{output_dir}")

    def closeEvent(self, event): # ... (Modificado para quitar referencia a preview_thread) ...
        if self.active_thread and self.active_thread.isRunning():
            reply = QMessageBox.question(self,'Conversión en progreso',"La conversión aún está en curso.\n¿Seguro que quieres salir?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self._cancel_requested = True
                if self.active_worker and hasattr(self.active_worker, 'request_cancel'):
                    QMetaObject.invokeMethod(self.active_worker, "request_cancel", Qt.ConnectionType.QueuedConnection)
                self.active_thread.quit()
                if not self.active_thread.wait(500): print("Warning: Hilo de conversión activo no terminó limpiamente al cerrar.")
                event.accept()
            else: event.ignore()
        # Ya no necesitamos comprobar preview_thread
        else:
            event.accept()