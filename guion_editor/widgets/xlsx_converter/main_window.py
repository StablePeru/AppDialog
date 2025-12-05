# main_window.py

import os
import sys
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QFileDialog, QMessageBox, QSpacerItem,
    QSizePolicy, QFrame, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSlot, QTimer, QMetaObject
from PyQt6.QtGui import QIcon, QDropEvent, QDragEnterEvent

# --- CORRECCIÓN DE IMPORTS PARA SOPORTAR EJECUCIÓN DIRECTA Y MÓDULO ---
try:
    # Intento 1: Importación relativa (Funciona cuando se usa desde Takeo/App principal)
    from .config import HEADER_DEFAULTS, ICON_PATH
    from .conversion_worker import ConversionWorker
except ImportError:
    # Intento 2: Importación absoluta (Funciona cuando se lanza el conversor solo)
    from config import HEADER_DEFAULTS, ICON_PATH
    from conversion_worker import ConversionWorker
# -----------------------------------------------------------------------

class MainWindow(QWidget):
    """Ventana principal del conversor con campos para la cabecera."""

    def __init__(self):
        super().__init__()
        self.file_list = []
        self.current_conversion_index = -1
        self.active_worker = None
        self.active_thread = None
        self._cancel_requested = False
        self.initUI()
        self.setAcceptDrops(True)

    def initUI(self):
        self.setWindowTitle("Conversor Excel a TXT Pro (Formato Estudio)")
        self.setGeometry(150, 150, 600, 700)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- 1. Sección de Archivos ---
        list_v_layout = QVBoxLayout()
        list_v_layout.setSpacing(5)

        lbl_select_file = QLabel("1. Archivos Excel a Procesar (Arrastra aquí)")
        lbl_select_file.setStyleSheet("font-weight: bold; color: #E0E0E0;")
        list_v_layout.addWidget(lbl_select_file)

        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        list_v_layout.addWidget(self.file_list_widget)

        list_buttons_h_layout = QHBoxLayout()
        btn_add_files = QPushButton("Añadir...")
        btn_add_files.clicked.connect(self.add_files)
        btn_remove_selected = QPushButton("Quitar")
        btn_remove_selected.clicked.connect(self.remove_selected_files)
        btn_clear_list = QPushButton("Limpiar")
        btn_clear_list.clicked.connect(self.clear_file_list)
        list_buttons_h_layout.addWidget(btn_add_files)
        list_buttons_h_layout.addWidget(btn_remove_selected)
        list_buttons_h_layout.addStretch()
        list_buttons_h_layout.addWidget(btn_clear_list)
        list_v_layout.addLayout(list_buttons_h_layout)

        main_layout.addLayout(list_v_layout, 1)

        # --- 2. Sección de Datos de Cabecera ---
        lbl_header_info = QLabel("2. Datos de Cabecera (Para el TXT)")
        lbl_header_info.setStyleSheet("font-weight: bold; color: #E0E0E0; margin-top: 10px;")
        main_layout.addWidget(lbl_header_info)

        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #2D2D2D; border-radius: 6px; padding: 5px;")
        header_layout = QFormLayout(header_frame)
        header_layout.setSpacing(10)

        self.title_entry = QLineEdit()
        self.title_entry.setPlaceholderText(HEADER_DEFAULTS["Título"])
        
        self.chapter_entry = QLineEdit()
        self.chapter_entry.setPlaceholderText(HEADER_DEFAULTS["Capítulo"])
        
        self.translator_entry = QLineEdit()
        self.translator_entry.setPlaceholderText(HEADER_DEFAULTS["Traductor"])
        
        self.takeo_entry = QLineEdit()
        self.takeo_entry.setPlaceholderText(HEADER_DEFAULTS["Takeo"])

        header_layout.addRow("Título:", self.title_entry)
        header_layout.addRow("Capítulo:", self.chapter_entry)
        header_layout.addRow("Traductor:", self.translator_entry)
        header_layout.addRow("Takeo (Ajuste):", self.takeo_entry)
        
        main_layout.addWidget(header_frame)

        # --- 3. Botones de Acción ---
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.request_batch_cancel)
        self.cancel_button.setEnabled(False)
        action_layout.addWidget(self.cancel_button)
        
        self.convert_button = QPushButton("GENERAR TXT")
        self.convert_button.setStyleSheet("background-color: #0078D7; font-weight: bold; padding: 10px 20px;")
        self.convert_button.setEnabled(False)
        self.convert_button.clicked.connect(self.start_batch_conversion)
        action_layout.addWidget(self.convert_button)
        
        main_layout.addLayout(action_layout)

        # --- 4. Estado ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Listo.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

    # --- Getters ---
    def _get_header_data(self):
        """Recoge los datos del formulario."""
        return {
            "Título": self.title_entry.text().strip() or "S/T",
            "Capítulo": self.chapter_entry.text().strip() or "S/N",
            "Traductor": self.translator_entry.text().strip() or "S/N",
            "Takeo": self.takeo_entry.text().strip() or "S/N"
        }

    # --- Eventos (Drag & Drop, Botones) ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.xlsx') and file_path not in self.file_list:
                self.file_list.append(file_path)
                self.file_list_widget.addItem(os.path.basename(file_path))
        self.update_ui_state()

    @pyqtSlot()
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Excel", "", "Excel (*.xlsx)")
        if files:
            for f in files:
                if f not in self.file_list:
                    self.file_list.append(f)
                    self.file_list_widget.addItem(os.path.basename(f))
            self.update_ui_state()

    @pyqtSlot()
    def remove_selected_files(self):
        for item in self.file_list_widget.selectedItems():
            row = self.file_list_widget.row(item)
            self.file_list.pop(row)
            self.file_list_widget.takeItem(row)
        self.update_ui_state()

    @pyqtSlot()
    def clear_file_list(self):
        self.file_list.clear()
        self.file_list_widget.clear()
        self.update_ui_state()

    def update_ui_state(self):
        self.convert_button.setEnabled(len(self.file_list) > 0)

    # --- Lógica de Conversión ---
    @pyqtSlot()
    def start_batch_conversion(self):
        self._cancel_requested = False
        self.current_conversion_index = 0
        self.set_ui_busy(True)
        self.process_next_file()

    def process_next_file(self):
        if self._cancel_requested or self.current_conversion_index >= len(self.file_list):
            self.finish_batch()
            return

        file_path = self.file_list[self.current_conversion_index]
        output_dir = os.path.dirname(file_path)
        header_data = self._get_header_data()

        self.status_label.setText(f"Procesando: {os.path.basename(file_path)}...")
        self.progress_bar.setRange(0, 0) # Indeterminado

        self.active_thread = QThread()
        self.active_worker = ConversionWorker(file_path, output_dir, header_data)
        self.active_worker.moveToThread(self.active_thread)

        self.active_worker.finished.connect(self.on_file_finished)
        self.active_thread.started.connect(self.active_worker.run)
        
        self.active_thread.start()

    @pyqtSlot(bool, str, str)
    def on_file_finished(self, success, msg, path):
        self.active_thread.quit()
        self.active_thread.wait()
        
        if not success:
            QMessageBox.warning(self, "Error", f"Error en {os.path.basename(path)}:\n{msg}")
        
        self.current_conversion_index += 1
        QTimer.singleShot(100, self.process_next_file)

    def finish_batch(self):
        self.set_ui_busy(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText("Proceso finalizado.")
        if not self._cancel_requested:
            QMessageBox.information(self, "Completado", "Se han generado los archivos TXT.")

    @pyqtSlot()
    def request_batch_cancel(self):
        self._cancel_requested = True
        self.status_label.setText("Cancelando...")

    def set_ui_busy(self, busy):
        self.convert_button.setEnabled(not busy)
        self.file_list_widget.setEnabled(not busy)
        self.title_entry.setEnabled(not busy)
        self.chapter_entry.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)