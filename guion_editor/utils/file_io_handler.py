# guion_editor/utils/file_io_handler.py
from __future__ import annotations
import os
from typing import TYPE_CHECKING

import pandas as pd
from PyQt6.QtWidgets import QFileDialog, QDialog, QMessageBox, QApplication, QProgressDialog
from PyQt6.QtCore import Qt

from .. import constants as C
from ..widgets.excel_mapping_dialog import ExcelMappingDialog

# Evita la importación circular, solo para type hints
if TYPE_CHECKING:
    from ..widgets.table_window import TableWindow

class FileIOHandler:
    """
    Gestiona todas las operaciones de carga y guardado de archivos para TableWindow.
    """
    def __init__(self, table_window: 'TableWindow'):
        # Guardamos una referencia a la TableWindow para poder acceder a sus
        # propiedades (como guion_manager) y métodos (como _post_load_script_actions).
        self.tw = table_window

    def load_docx(self):
        """Abre el diálogo para cargar un archivo DOCX."""
        file_name, _ = QFileDialog.getOpenFileName(self.tw, "Abrir Guion DOCX", "", "Documentos Word (*.docx)")
        if file_name:
            self._load_docx_path(file_name)

    def _load_docx_path(self, file_path: str):
        progress = QProgressDialog("Cargando guion desde DOCX...", "Cancelar", 0, 0, self.tw)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setRange(0, 0)
        progress.show()
        QApplication.processEvents()

        try:
            df, header_data, _ = self.tw.guion_manager.load_from_docx(file_path)
            self.tw._post_load_script_actions(file_path, df, header_data)
        except FileNotFoundError:
            self.tw.handle_exception(FileNotFoundError(f"El archivo no se encontró: {file_path}"), "Error al cargar DOCX")
            self.tw.clear_script_state()
        except Exception as e:
            self.tw.handle_exception(e, f"Error al procesar el archivo DOCX: {file_path}")
            self.tw.clear_script_state()
        finally:
            progress.close()

    def import_excel(self):
        """Abre el diálogo para importar desde Excel."""
        path, _ = QFileDialog.getOpenFileName(self.tw, "Importar Guion desde Excel", "", "Archivos Excel (*.xlsx)")
        if path:
            self._load_excel_path(path)

    def _load_excel_path(self, file_path: str):
        progress = QProgressDialog("Procesando archivo Excel...", "Cancelar", 0, 0, self.tw)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setRange(0, 0)
        progress.show()
        QApplication.processEvents()

        try:
            raw_df, header_data, needs_mapping = self.tw.guion_manager.check_excel_columns(file_path)
            final_df = None
            if needs_mapping:
                progress.close()
                dialog = ExcelMappingDialog(raw_df, self.tw)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    progress.setLabelText("Aplicando mapeo y cargando datos...")
                    progress.show()
                    QApplication.processEvents()
                    
                    mapping = dialog.get_mapping()
                    mapped_df = pd.DataFrame()
                    for app_col, excel_col in mapping.items():
                        if excel_col != "--- NO ASIGNAR / USAR VALOR POR DEFECTO ---":
                            mapped_df[app_col] = raw_df.get(excel_col, "")
                    final_df = mapped_df
                else:
                    progress.close()
                    return
            else:
                final_df = raw_df
            
            if final_df is not None:
                df_processed, _ = self.tw.guion_manager.process_dataframe(final_df, file_source=file_path)
                self.tw._post_load_script_actions(file_path, df_processed, header_data)
                
        except FileNotFoundError:
            self.tw.handle_exception(FileNotFoundError(f"El archivo no se encontró: {file_path}"), "Error al cargar Excel")
            self.tw.clear_script_state()
        except (ValueError, KeyError) as e:
            self.tw.handle_exception(e, f"El archivo Excel '{os.path.basename(file_path)}' tiene un formato inesperado.")
            self.tw.clear_script_state()
        except Exception as e:
            self.tw.handle_exception(e, f"Error al procesar el archivo Excel: {file_path}")
            self.tw.clear_script_state()
        finally:
            progress.close()

    def load_json(self):
        """Abre el diálogo para cargar un guion desde JSON."""
        path, _ = QFileDialog.getOpenFileName(self.tw, "Cargar Guion desde JSON", "", "Archivos JSON (*.json)")
        if path:
            self._load_json_path(path)

    def _load_json_path(self, file_path: str):
        progress = QProgressDialog("Cargando guion desde JSON...", "Cancelar", 0, 0, self.tw)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setRange(0, 0)
        progress.show()
        QApplication.processEvents()

        try:
            df, header_data, _ = self.tw.guion_manager.load_from_json(file_path)
            self.tw._post_load_script_actions(file_path, df, header_data)
        except FileNotFoundError:
            self.tw.handle_exception(FileNotFoundError(f"El archivo no se encontró: {file_path}"), "Error al cargar JSON")
            self.tw.clear_script_state()
        except json.JSONDecodeError as e:
            self.tw.handle_exception(e, f"El archivo JSON '{os.path.basename(file_path)}' está corrupto.")
            self.tw.clear_script_state()
        except Exception as e:
            self.tw.handle_exception(e, f"Error al procesar el archivo JSON: {file_path}")
            self.tw.clear_script_state()
        finally:
            progress.close()

    def export_excel(self) -> bool:
        """Abre el diálogo para exportar a Excel y realiza la operación."""
        if self.tw.pandas_model.dataframe().empty:
            QMessageBox.information(self.tw, "Exportar", "No hay datos para exportar.")
            return False
        
        default_filename = self.tw._generate_default_filename("xlsx")
        path, _ = QFileDialog.getSaveFileName(self.tw, "Exportar a Excel", default_filename, "Archivos Excel (*.xlsx)")
        
        if path:
            try:
                self.tw.guion_manager.save_to_excel(path, self.tw.pandas_model.dataframe(), self.tw._get_header_data_from_ui())
                QMessageBox.information(self.tw, "Éxito", "Guion guardado en Excel.")
                self.tw.current_script_name = os.path.basename(path)
                self.tw.current_script_path = path
                self.tw.undo_stack.setClean()
                if self.tw.main_window:
                    self.tw.main_window.add_to_recent_files(path)
                return True
            except Exception as e:
                self.tw.handle_exception(e, "Error al guardar en Excel")
        return False

    def save_as_json(self) -> bool:
        """Abre el diálogo "Guardar como..." para JSON."""
        if self.tw.pandas_model.dataframe().empty:
            QMessageBox.information(self.tw, "Guardar", "No hay datos para guardar.")
            return False
            
        default_filename = self.tw._generate_default_filename("json")
        path, _ = QFileDialog.getSaveFileName(self.tw, "Guardar como JSON", default_filename, "Archivos JSON (*.json)")
        
        if path:
            try:
                self.tw.guion_manager.save_to_json(path, self.tw.pandas_model.dataframe(), self.tw._get_header_data_from_ui())
                QMessageBox.information(self.tw, "Éxito", "Guion guardado como JSON.")
                self.tw.current_script_name = os.path.basename(path)
                self.tw.current_script_path = path
                self.tw.undo_stack.setClean()
                if self.tw.main_window:
                    self.tw.main_window.add_to_recent_files(path)
                return True
            except Exception as e:
                self.tw.handle_exception(e, "Error al guardar como JSON")
        return False