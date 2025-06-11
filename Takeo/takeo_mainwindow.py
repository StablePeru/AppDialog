# Takeo/takeo_mainwindow.py
import sys
import os
import pandas as pd 
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QGroupBox, QFileDialog, QMessageBox,
    QScrollArea, QSizePolicy, QSpacerItem, QTextEdit, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressDialog
)
from PyQt6.QtCore import Qt, pyqtSlot, QSettings # Añadido QSettings
from PyQt6.QtGui import QIcon, QIntValidator, QFont, QCloseEvent # Añadido QCloseEvent

from script_optimizer_logic import ScriptOptimizerLogic

# Constantes para QSettings
ORGANIZATION_NAME = "MiEmpresa" # Cambia esto
APPLICATION_NAME = "TakeoScriptOptimizer"

class ProblemReportDialog(QDialog):
    def __init__(self, problems_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reporte de Intervenciones Problemáticas")
        self.setGeometry(200, 200, 800, 400)
        
        layout = QVBoxLayout(self)
        
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(7) 
        self.table_widget.setHorizontalHeaderLabels(["Fila Excel", "Escena", "Personaje", "IN", "OUT", "Tipo Problema", "Detalle"])
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents) 
        
        self.table_widget.setRowCount(len(problems_list))
        for row_idx, problem in enumerate(problems_list):
            self.table_widget.setItem(row_idx, 0, QTableWidgetItem(str(problem.get("ROW_INDEX_EXCEL", "N/A"))))
            self.table_widget.setItem(row_idx, 1, QTableWidgetItem(problem.get("SCENE", "N/A")))
            self.table_widget.setItem(row_idx, 2, QTableWidgetItem(problem.get("PERSONAJE", "N/A")))
            self.table_widget.setItem(row_idx, 3, QTableWidgetItem(problem.get("IN", "N/A")))
            self.table_widget.setItem(row_idx, 4, QTableWidgetItem(problem.get("OUT", "N/A")))
            self.table_widget.setItem(row_idx, 5, QTableWidgetItem(problem.get("PROBLEMA_TIPO", "N/A")))
            self.table_widget.setItem(row_idx, 6, QTableWidgetItem(problem.get("DETALLE", "N/A")))

        layout.addWidget(self.table_widget)
        
        save_button = QPushButton("Guardar Reporte Completo en Excel")
        save_button.clicked.connect(lambda: self.parent().save_problem_report_to_file(problems_list)) 
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)


class TakeoMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.optimizer_logic = ScriptOptimizerLogic()
        self.characters_checkboxes = {} 
        self.current_script_path = None
        self.problematic_interventions_cache = [] 
        self.last_used_directory = os.path.expanduser("~") # Default al home del usuario

        self.init_ui()
        self.load_settings() # Cargar configuración al inicio

    def init_ui(self):
        self.setWindowTitle(f"Optimizador de Takes para Guiones v1.3 (PyQt6) - {APPLICATION_NAME}") # Version bump
        self.setGeometry(100, 100, 850, 750) 

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10) 
        main_layout.setContentsMargins(10, 10, 10, 10) 

        load_layout = QHBoxLayout()
        self.load_button = QPushButton(" Cargar Guion (Excel)")
        self.load_button.setMinimumHeight(30)
        self.load_button.clicked.connect(self.handle_load_script)
        self.loaded_script_label = QLabel("Ningún guion cargado.")
        self.loaded_script_label.setStyleSheet("font-style: italic;")
        load_layout.addWidget(self.load_button)
        load_layout.addWidget(self.loaded_script_label, 1) 
        main_layout.addLayout(load_layout)

        config_groupbox = QGroupBox("Configuración de Takes")
        config_groupbox.setStyleSheet("QGroupBox { font-weight: bold; }")
        config_layout = QFormLayout(config_groupbox)
        config_layout.setSpacing(8)
        
        default_font = QFont()
        default_font.setPointSize(10)
        config_groupbox.setFont(default_font)

        validator = QIntValidator(1, 9999) 

        # Los valores iniciales se establecen aquí, pero load_settings() los sobrescribirá si hay guardados
        self.max_duration_edit = QLineEdit(str(self.optimizer_logic.max_duration))
        self.max_duration_edit.setValidator(validator)
        self.max_duration_edit.setToolTip("Duración máxima en segundos que puede tener un take.")
        config_layout.addRow("Duración máxima por take (segundos):", self.max_duration_edit)

        self.max_lines_take_edit = QLineEdit(str(self.optimizer_logic.max_lines_per_take))
        self.max_lines_take_edit.setValidator(validator)
        self.max_lines_take_edit.setToolTip("Número máximo de líneas de diálogo que puede contener un take.")
        config_layout.addRow("Máximo de líneas por take:", self.max_lines_take_edit)
        
        self.max_consecutive_edit = QLineEdit(str(self.optimizer_logic.max_consecutive_lines_per_character))
        self.max_consecutive_edit.setValidator(validator)
        self.max_consecutive_edit.setToolTip("Máximo de líneas seguidas que un mismo personaje puede tener dentro de un take.")
        config_layout.addRow("Máx. líneas consecutivas (mismo personaje en take):", self.max_consecutive_edit)

        self.max_chars_line_edit = QLineEdit(str(self.optimizer_logic.max_chars_per_line))
        self.max_chars_line_edit.setValidator(validator)
        self.max_chars_line_edit.setToolTip("Máximo de caracteres efectivos por línea de diálogo (paréntesis cuentan como 1).")
        config_layout.addRow("Máximo de caracteres por línea (diálogo):", self.max_chars_line_edit)
        
        self.frame_rate_edit = QLineEdit(str(getattr(self.optimizer_logic, 'frame_rate', 25)))
        self.frame_rate_edit.setValidator(validator) 
        self.frame_rate_edit.setToolTip("Frame rate (FPS) para interpretar tiempos con frames (e.g., HH:MM:SS:FF).")
        config_layout.addRow("Frame Rate (FPS):", self.frame_rate_edit)
        
        main_layout.addWidget(config_groupbox)

        characters_groupbox = QGroupBox("Selección de Personajes")
        characters_groupbox.setStyleSheet("QGroupBox { font-weight: bold; }")
        characters_groupbox.setFont(default_font)
        characters_main_layout = QVBoxLayout(characters_groupbox)

        self.characters_scroll_area = QScrollArea()
        self.characters_scroll_area.setWidgetResizable(True)
        self.characters_scroll_area.setMinimumHeight(200) 
        characters_scroll_content_widget = QWidget()
        self.characters_grid_layout = QGridLayout(characters_scroll_content_widget)
        self.characters_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.characters_scroll_area.setWidget(characters_scroll_content_widget)
        characters_main_layout.addWidget(self.characters_scroll_area)
        
        char_buttons_layout = QHBoxLayout()
        select_all_chars_btn = QPushButton("Seleccionar Todos")
        deselect_all_chars_btn = QPushButton("Deseleccionar Todos")
        select_all_chars_btn.clicked.connect(lambda: self.toggle_all_characters(True))
        deselect_all_chars_btn.clicked.connect(lambda: self.toggle_all_characters(False))
        char_buttons_layout.addWidget(select_all_chars_btn)
        char_buttons_layout.addWidget(deselect_all_chars_btn)
        char_buttons_layout.addStretch()
        characters_main_layout.addLayout(char_buttons_layout)

        main_layout.addWidget(characters_groupbox)
        main_layout.setStretchFactor(characters_groupbox, 1)

        action_layout = QHBoxLayout()
        action_layout.addStretch() 
        self.process_button = QPushButton(" Procesar Guion")
        self.process_button.setMinimumHeight(35)
        self.process_button.setStyleSheet("QPushButton { font-size: 11pt; font-weight: bold; }")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.handle_process_script)
        action_layout.addWidget(self.process_button)
        main_layout.addLayout(action_layout)

        self.statusBar().showMessage("Listo. Cargue un guion para comenzar.")
        self.show()

    def load_settings(self):
        settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
        
        self.max_duration_edit.setText(settings.value("max_duration", self.optimizer_logic.max_duration, type=str))
        self.max_lines_take_edit.setText(settings.value("max_lines_per_take", self.optimizer_logic.max_lines_per_take, type=str))
        self.max_consecutive_edit.setText(settings.value("max_consecutive_lines_per_character", self.optimizer_logic.max_consecutive_lines_per_character, type=str))
        self.max_chars_line_edit.setText(settings.value("max_chars_per_line", self.optimizer_logic.max_chars_per_line, type=str))
        self.frame_rate_edit.setText(settings.value("frame_rate", getattr(self.optimizer_logic, 'frame_rate', 25), type=str))
        
        self.last_used_directory = settings.value("last_used_directory", os.path.expanduser("~"), type=str)
        # Asegurarse que el directorio existe, si no, volver al home
        if not os.path.isdir(self.last_used_directory):
            self.last_used_directory = os.path.expanduser("~")

        # Restaurar la geometría de la ventana
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry) # QByteArray

        self.statusBar().showMessage("Configuración cargada.")


    def save_settings(self):
        settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
        
        settings.setValue("max_duration", self.max_duration_edit.text())
        settings.setValue("max_lines_per_take", self.max_lines_take_edit.text())
        settings.setValue("max_consecutive_lines_per_character", self.max_consecutive_edit.text())
        settings.setValue("max_chars_per_line", self.max_chars_line_edit.text())
        settings.setValue("frame_rate", self.frame_rate_edit.text())
        
        settings.setValue("last_used_directory", self.last_used_directory)
        settings.setValue("geometry", self.saveGeometry()) # QByteArray

        self.statusBar().showMessage("Configuración guardada.")

    def closeEvent(self, event: QCloseEvent):
        """Sobrescribir para guardar la configuración al cerrar."""
        self.save_settings()
        event.accept()


    def _get_current_config_from_ui(self):
        return {
            'max_duration': self.max_duration_edit.text(),
            'max_lines_per_take': self.max_lines_take_edit.text(),
            'max_consecutive_lines_per_character': self.max_consecutive_edit.text(),
            'max_chars_per_line': self.max_chars_line_edit.text(),
            'frame_rate': self.frame_rate_edit.text(), 
        }

    @pyqtSlot()
    def handle_load_script(self):
        self.statusBar().showMessage("Abriendo diálogo para cargar guion...")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo Excel del guion", 
            self.last_used_directory, # Usar el último directorio guardado
            "Excel files (*.xlsx *.xls)"
        )

        if not file_path:
            self.statusBar().showMessage("Carga cancelada por el usuario.")
            return

        self.current_script_path = file_path
        self.last_used_directory = os.path.dirname(file_path) # Actualizar último directorio
        self.loaded_script_label.setText(f"Guion: {os.path.basename(file_path)}")
        self.statusBar().showMessage(f"Cargando '{os.path.basename(file_path)}'...")
        QApplication.processEvents() 

        progress_dialog = QProgressDialog("Cargando guion...", "Cancelar", 0, 0, self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0) 
        progress_dialog.setValue(0) 
        progress_dialog.show()
        QApplication.processEvents()

        try:
            current_config = self._get_current_config_from_ui()
            self.optimizer_logic.set_configuration(current_config) 

            characters, time_msg, problematic_interv, line_count = self.optimizer_logic.load_script_data(file_path)
            
            progress_dialog.close() 

            self.problematic_interventions_cache = problematic_interv 
            
            QMessageBox.information(self, "Formato de Tiempo Detectado", time_msg)
            
            self.populate_character_checkboxes(characters)
            self.process_button.setEnabled(True)
            self.statusBar().showMessage(f"Guion cargado: {line_count} líneas. {len(characters)} personajes. Listo para procesar.")

            if self.problematic_interventions_cache:
                QMessageBox.warning(self, "Intervenciones Problemáticas",
                                    f"Se encontraron {len(self.problematic_interventions_cache)} intervenciones individuales "
                                    f"que podrían no cumplir las normas o tener errores de formato.\n"
                                    "Puede ver el detalle y guardarlo desde un diálogo que se abrirá.")
                self.show_problematic_interventions_dialog(self.problematic_interventions_cache)

        except Exception as e:
            if progress_dialog.isVisible():
                progress_dialog.close()
            QMessageBox.critical(self, "Error al Cargar Guion", str(e))
            self.process_button.setEnabled(False)
            self.loaded_script_label.setText("Error al cargar. Intente de nuevo.")
            self.statusBar().showMessage(f"Error al cargar guion: {e}")
            self.clear_character_checkboxes() 
        finally:
            if progress_dialog.isVisible(): 
                progress_dialog.close()


    def populate_character_checkboxes(self, characters):
        self.clear_character_checkboxes()
        num_cols = 3 
        for i, char_name in enumerate(characters):
            checkbox = QCheckBox(char_name)
            checkbox.setChecked(True) 
            self.characters_checkboxes[char_name] = checkbox
            row = i // num_cols
            col = i % num_cols
            self.characters_grid_layout.addWidget(checkbox, row, col)
        
        if characters:
             self.characters_grid_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding),
                                            (len(characters) -1) // num_cols + 1, 0, 1, num_cols)


    def clear_character_checkboxes(self):
        for i in reversed(range(self.characters_grid_layout.count())): 
            widget_item = self.characters_grid_layout.itemAt(i)
            if widget_item:
                widget = widget_item.widget()
                if widget:
                    widget.deleteLater() 
                else: 
                    self.characters_grid_layout.removeItem(widget_item)
        self.characters_checkboxes.clear()

    def toggle_all_characters(self, checked_state):
        if not self.characters_checkboxes:
            QMessageBox.information(self, "Información", "No hay personajes cargados para seleccionar/deseleccionar.")
            return
        for checkbox in self.characters_checkboxes.values():
            checkbox.setChecked(checked_state)

    def get_selected_characters_from_ui(self):
        return [name for name, cb in self.characters_checkboxes.items() if cb.isChecked()]

    def show_problematic_interventions_dialog(self, problems_list):
        dialog = ProblemReportDialog(problems_list, self)
        dialog.exec() 

    def save_problem_report_to_file(self, problems_list): 
        if not problems_list: return

        suggested_name = "reporte_intervenciones_problematicas.xlsx"
        if self.current_script_path:
            base, _ = os.path.splitext(os.path.basename(self.current_script_path))
            suggested_name = f"{base}_reporte_problemas.xlsx"
        
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Reporte de Problemas", 
            os.path.join(self.last_used_directory, suggested_name), # Usar último directorio
            "Excel Files (*.xlsx)"
        )
        
        if not save_path:
            self.statusBar().showMessage("Guardado de reporte de problemas cancelado.")
            return
        
        self.last_used_directory = os.path.dirname(save_path) # Actualizar último directorio
        try:
            df_report = pd.DataFrame(problems_list)
            df_report.to_excel(save_path, index=False)
            QMessageBox.information(self, "Reporte Guardado", f"Reporte de problemas guardado en:\n{save_path}")
            self.statusBar().showMessage(f"Reporte de problemas guardado en {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error al Guardar Reporte", f"No se pudo guardar el reporte: {str(e)}")
            self.statusBar().showMessage(f"Error al guardar reporte de problemas: {e}")

    @pyqtSlot()
    def handle_process_script(self):
        self.statusBar().showMessage("Iniciando procesamiento del guion...")
        self.process_button.setEnabled(False)
        QApplication.processEvents()

        selected_chars = self.get_selected_characters_from_ui()
        if not selected_chars:
            QMessageBox.warning(self, "Selección Necesaria", "Debe seleccionar al menos un personaje para procesar.")
            self.process_button.setEnabled(True)
            self.statusBar().showMessage("Seleccione personajes y vuelva a intentarlo.")
            return

        progress_dialog = QProgressDialog("Procesando guion...", "Cancelar", 0, 0, self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0) 
        progress_dialog.setValue(0) 
        progress_dialog.show()
        QApplication.processEvents()

        try:
            current_config = self._get_current_config_from_ui()
            self.optimizer_logic.set_configuration(current_config) 

            detail_df, summary_df, stats = self.optimizer_logic.process_script_logic(selected_chars)
            
            progress_dialog.close() 

            self.statusBar().showMessage("Procesamiento completado. Seleccione dónde guardar los resultados...")
            save_dir = QFileDialog.getExistingDirectory(self, "Seleccionar directorio para guardar resultados",
                                                        self.last_used_directory) # Usar último directorio
            if not save_dir:
                QMessageBox.information(self, "Guardado Cancelado", "El proceso de optimización se completó, pero el guardado de resultados fue cancelado.")
                self.statusBar().showMessage("Resultados no guardados (cancelado por usuario).")
                self.process_button.setEnabled(True)
                return

            self.last_used_directory = save_dir # Actualizar último directorio

            base_name = "resultados"
            if self.current_script_path:
                base_name, _ = os.path.splitext(os.path.basename(self.current_script_path))

            detail_path = os.path.join(save_dir, f"{base_name}_detalle_takes.xlsx")
            summary_path = os.path.join(save_dir, f"{base_name}_resumen_takes.xlsx")
            
            empty_detail_msg = ""
            if not detail_df.empty:
                detail_df.to_excel(detail_path, index=False)
            else:
                empty_detail_msg = "\n- No se generaron datos para el detalle de takes."

            empty_summary_msg = ""
            if not summary_df.empty:
                summary_df.to_excel(summary_path, index=False)
            else:
                empty_summary_msg = "\n- No se generaron datos para el resumen de takes."

            success_msg = (
                f"Proceso completado con éxito.\n\n"
                f"Total de takes únicos generados: {stats['total_takes']}\n"
                f"Suma total de apariciones en takes: {stats['sum_takes_char_appearances']}\n"
                f"{empty_detail_msg}{empty_summary_msg}\n\n"
                f"Archivos guardados en el directorio:\n{save_dir}"
            )
            QMessageBox.information(self, "Proceso Completado", success_msg)
            self.statusBar().showMessage(f"Proceso completado. Resultados guardados en {save_dir}")

        except Exception as e:
            if progress_dialog.isVisible():
                progress_dialog.close()
            QMessageBox.critical(self, "Error Durante el Procesamiento", str(e))
            self.statusBar().showMessage(f"Error durante el procesamiento: {e}")
        finally:
            if progress_dialog.isVisible(): 
                progress_dialog.close()
            self.process_button.setEnabled(True)