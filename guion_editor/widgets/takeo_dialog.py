# guion_editor/widgets/takeo_dialog.py
import os
import pandas as pd
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QSpinBox, QDialogButtonBox,
    QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QMessageBox,
    QFileDialog, QAbstractItemView, QGroupBox, QComboBox, QLabel, QApplication,
    QProgressDialog
)
from PyQt6.QtCore import Qt, QThread
from guion_editor.utils.takeo_optimizer_logic import TakeoWorker, TakeoOptimizerLogic # Importamos el Worker
from guion_editor.widgets.export_selection_dialog import ExportSelectionDialog

def load_takeo_stylesheet() -> str:
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        css_path = os.path.join(current_dir, '..', 'styles', 'takeo_styles.css')
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.warning(f"No se pudo cargar takeo_styles.css: {e}")
        return ""

class TakeoDialog(QDialog):
    def __init__(self, table_window, get_icon_func=None, parent=None):
        super().__init__(parent)
        self.table_window = table_window
        self.get_icon = get_icon_func
        self.setWindowTitle("Optimizador de Takes (Takeo)")
        self.setMinimumSize(600, 500)
        self.setObjectName("TakeoDialog")
        
        # Atributos para el manejo del hilo
        self.thread: QThread | None = None
        self.worker: TakeoWorker | None = None
        
        stylesheet = load_takeo_stylesheet()
        if stylesheet:
            self.setStyleSheet(stylesheet)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        config_group = QGroupBox("Reglas de Takeo")
        form_layout = QFormLayout(config_group)
        
        self.dialogue_source_combo = QComboBox()
        self.dialogue_source_combo.addItems(["EUSKERA", "DIÁLOGO"])
        form_layout.addRow("Columna de diálogo a optimizar:", self.dialogue_source_combo)

        self.duration_spin = QSpinBox(); self.duration_spin.setRange(1, 999); self.duration_spin.setValue(30)
        form_layout.addRow("Duración máxima por take (segundos):", self.duration_spin)
        self.max_lines_spin = QSpinBox(); self.max_lines_spin.setRange(1, 100); self.max_lines_spin.setValue(10)
        form_layout.addRow("Máximo de líneas por take:", self.max_lines_spin)
        self.max_consecutive_spin = QSpinBox(); self.max_consecutive_spin.setRange(1, 100); self.max_consecutive_spin.setValue(5)
        form_layout.addRow("Máx. líneas consecutivas (mismo personaje):", self.max_consecutive_spin)
        self.max_chars_spin = QSpinBox(); self.max_chars_spin.setRange(10, 200); self.max_chars_spin.setValue(60)
        form_layout.addRow("Máx. caracteres por línea (diálogo):", self.max_chars_spin)
        self.silence_spin = QSpinBox(); self.silence_spin.setRange(0, 999); self.silence_spin.setValue(10)
        form_layout.addRow("Máx. silencio entre intervenciones (segundos):", self.silence_spin)
        layout.addWidget(config_group)

        char_group = QGroupBox("Personajes a Incluir en la Optimización")
        char_layout = QVBoxLayout(char_group)
        char_buttons_layout = QHBoxLayout()
        select_all_btn = QPushButton("Seleccionar Todos"); select_all_btn.clicked.connect(self.select_all_characters)
        deselect_all_btn = QPushButton("Deseleccionar Todos"); deselect_all_btn.clicked.connect(self.deselect_all_characters)
        char_buttons_layout.addWidget(select_all_btn); char_buttons_layout.addWidget(deselect_all_btn); char_buttons_layout.addStretch()
        char_layout.addLayout(char_buttons_layout)
        self.char_list_widget = QListWidget(); self.char_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.populate_character_list()
        char_layout.addWidget(self.char_list_widget)
        layout.addWidget(char_group)

        self.button_box = QDialogButtonBox()
        self.run_button = self.button_box.addButton("Optimizar y Guardar...", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.run_button.clicked.connect(self.run_optimization)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.button_box)

    def populate_character_list(self):
        characters = self.table_window.get_character_names_from_model()
        for char in characters:
            item = QListWidgetItem(char); item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked); self.char_list_widget.addItem(item)

    def select_all_characters(self):
        for i in range(self.char_list_widget.count()): self.char_list_widget.item(i).setCheckState(Qt.CheckState.Checked)

    def deselect_all_characters(self):
        for i in range(self.char_list_widget.count()): self.char_list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)

    def get_selected_characters(self):
        return [self.char_list_widget.item(i).text() for i in range(self.char_list_widget.count()) if self.char_list_widget.item(i).checkState() == Qt.CheckState.Checked]

    def run_optimization(self):
        if self.thread and self.thread.isRunning():
            logging.warning("Intento de iniciar optimización mientras una ya está en curso.")
            return

        config = {'max_duration': self.duration_spin.value(), 'max_lines_per_take': self.max_lines_spin.value(), 'max_consecutive_lines_per_character': self.max_consecutive_spin.value(), 'max_chars_per_line': self.max_chars_spin.value(), 'max_silence_between_interventions': self.silence_spin.value()}
        selected_chars = self.get_selected_characters()
        if not selected_chars: 
            QMessageBox.warning(self, "Sin Selección", "Debe seleccionar al menos un personaje.")
            return
            
        current_df = self.table_window.pandas_model.dataframe()
        dialogue_col = self.dialogue_source_combo.currentText()
        
        # --- LÓGICA DE HILOS ---
        self.thread = QThread()
        self.worker = TakeoWorker(config, current_df.copy(), selected_chars, dialogue_col)
        self.worker.moveToThread(self.thread)
        
        # Conectar señales del worker a los slots de este diálogo
        self.worker.finished.connect(self._on_optimization_finished)
        self.worker.error.connect(self._on_optimization_error)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        
        # Iniciar el hilo
        self.thread.start()
        
        # Proporcionar feedback al usuario
        self.run_button.setEnabled(False)
        self.run_button.setText("Procesando...")
        self.setCursor(Qt.CursorShape.WaitCursor)
        
    def _on_optimization_finished(self, detail_df, summary_df, failures_df, problematic_report, takes_generated):
        """Este método se ejecuta en el hilo principal cuando el worker termina."""
        logging.info("Recepción de resultados del worker de Takeo.")
        self.unsetCursor()
        self.run_button.setEnabled(True)
        self.run_button.setText("Optimizar y Guardar...")
        
        self.save_results(detail_df, summary_df, failures_df, problematic_report, takes_generated)
        self.accept()

    def _on_optimization_error(self, error_string):
        """Este método se ejecuta si el worker emite una señal de error."""
        self.unsetCursor()
        self.run_button.setEnabled(True)
        self.run_button.setText("Optimizar y Guardar...")
        QMessageBox.critical(self, "Error en la Optimización", f"Ocurrió un error durante el proceso:\n{error_string}")
        self.reject()

    def save_results(self, detail_df, summary_df, failures_df, problematic_report, takes_generated):
        reports_available = {
            "detail": not detail_df.empty, 
            "summary": not summary_df.empty, 
            "failures": not failures_df.empty, 
            "problems": bool(problematic_report)
        }
        if not any(reports_available.values()):
            QMessageBox.information(self, "Proceso Completado", "La optimización finalizó, pero no se generaron resultados para exportar."); return

        export_dialog = ExportSelectionDialog(reports_available, self);
        if not export_dialog.exec(): return

        choices = export_dialog.get_choices()
        if not choices or not any(choices.values()):
            QMessageBox.information(self, "Sin Selección", "No se ha seleccionado ningún archivo para exportar."); return

        save_dir = QFileDialog.getExistingDirectory(self, "Seleccionar Directorio para Guardar Informes")
        if not save_dir: return

        saved_files = []
        try:
            if choices["detail"] and reports_available["detail"]:
                path = os.path.join(save_dir, "detalle_takes_optimizado.xlsx"); detail_df.to_excel(path, index=False); saved_files.append(os.path.basename(path))
            if choices["summary"] and reports_available["summary"]:
                path = os.path.join(save_dir, "resumen_takes_optimizado.xlsx"); summary_df.to_excel(path, index=False); saved_files.append(os.path.basename(path))
            if choices["failures"] and reports_available["failures"]:
                path = os.path.join(save_dir, "reporte_fallos_de_agrupacion.xlsx"); failures_df.to_excel(path, index=False); saved_files.append(os.path.basename(path))
            if choices["problems"] and reports_available["problems"]:
                prob_df = pd.DataFrame(problematic_report); path = os.path.join(save_dir, "reporte_intervenciones_problematicas.xlsx"); prob_df.to_excel(path, index=False); saved_files.append(os.path.basename(path))

            if not saved_files:
                QMessageBox.information(self, "Sin Resultados", "No se guardó ningún archivo según su selección."); return
            
            sum_val = summary_df.iloc[-1]["TAKES (apariciones)"] if reports_available["summary"] else "N/A"
            files_str = "\n - ".join(saved_files)
            QMessageBox.information(self, "Proceso Completado", f"Optimización finalizada.\n\nTakes únicos generados: {takes_generated}\nSuma de apariciones: {sum_val}\n\nArchivos guardados en '{os.path.basename(save_dir)}':\n - {files_str}")
        except Exception as e:
            logging.error("No se pudieron guardar los informes de Takeo.", exc_info=True)
            QMessageBox.critical(self, "Error al Guardar", f"No se pudieron guardar los informes: {e}")
            
    def closeEvent(self, event):
        """Asegurarse de que el hilo se cierre correctamente si se cierra la ventana."""
        if self.thread and self.thread.isRunning():
            logging.info("Cerrando diálogo de Takeo, intentando detener el hilo...")
            self.thread.quit()
            self.thread.wait(500) # Esperar hasta 500ms a que el hilo termine limpiamente
        super().closeEvent(event)