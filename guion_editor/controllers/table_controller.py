import os
from PyQt6.QtCore import QObject
from typing import Optional, List, Dict, Any

from guion_editor.models.script_model import ScriptModel
from guion_editor.commands import (
    EditCommand, AddRowCommand, RemoveRowsCommand, MoveRowCommand,
    SplitInterventionCommand, MergeInterventionsCommand, ChangeSceneCommand
)
from guion_editor.utils.dialog_utils import ajustar_dialogo # Assuming this is the utility for adjust_dialogs
# For find_and_replace, we might need re if ScriptModel doesn't expose a case-insensitive replace for individual cells.
import re


class TableController(QObject):
    def __init__(self, main_window_ref: Optional[Any] = None):
        super().__init__()
        self.script_model = ScriptModel()
        self.main_window_ref = main_window_ref # For global app functions like recent files
        self.table_window: Optional[Any] = None # Will be a TableWindow instance
        self.current_script_path: Optional[str] = None
        self._unsaved_changes: bool = False

        self.script_model.undo_stack.cleanChanged.connect(self._handle_clean_changed)
        self._listen_to_model_changes()

    def _listen_to_model_changes(self):
        self.script_model.subscribe(self._on_script_model_changed)

    def _on_script_model_changed(self, event_type: str, data: Optional[Dict] = None):
        print(f"Controller received model event: {event_type}, data: {data}")
        # This method is primarily for the controller to react to model changes.
        # View updates based on model changes are ideally handled by the view itself
        # subscribing to the model, or the controller explicitly telling the view.
        # For example, after a script is loaded, the controller might tell the view to refresh.
        if self.table_window:
            if event_type == "script_loaded":
                # Ensure view reflects the newly loaded model state
                self.table_window.load_dataframe(self.script_model.get_dataframe())
                self.table_window.update_header_fields(self.script_model.get_header_data())
                self.table_window.clear_selection()
                # Title update is handled by set_unsaved_changes
            # Other events like "rows_added", "cell_updated" might trigger view updates
            # if the view is not directly listening or needs controller coordination.

    def _handle_clean_changed(self, clean: bool):
        self.set_unsaved_changes(not clean)

    def set_unsaved_changes(self, changed: bool):
        if self._unsaved_changes == changed:
            return
        self._unsaved_changes = changed
        
        # As per subtask: Call a method on self.table_window to update its title.
        if self.table_window and hasattr(self.table_window, 'update_window_title_status'):
            self.table_window.update_window_title_status(self._unsaved_changes, self.current_script_path or "Sin Título")
        elif self.table_window:
            # Fallback or alternative if the method name is different or for debugging
            print(f"TableController: View title update method 'update_window_title_status' not found on table_window. Unsaved changes: {self._unsaved_changes}")


    def has_unsaved_changes(self) -> bool:
        return self._unsaved_changes

    def set_view(self, table_window_instance: Any):
        self.table_window = table_window_instance
        # Initialize the view with current model data
        if self.table_window:
            self.table_window.load_dataframe(self.script_model.get_dataframe())
            self.table_window.update_header_fields(self.script_model.get_header_data())
            # Update title status based on current state
            self.set_unsaved_changes(self._unsaved_changes)


    # --- Action Handlers ---
    def handle_load_script_request(self, file_path: str, file_type: str):
        df = None
        header_data = None
        # has_scenes is derived by ScriptModel.has_scene_numbers property

        try:
            if file_type == "excel":
                df, header_data, _ = self.script_model.guion_manager.load_from_excel(file_path)
            elif file_type == "json":
                df, header_data, _ = self.script_model.guion_manager.load_from_json(file_path)
            elif file_type == "docx":
                df, header_data, _ = self.script_model.guion_manager.load_from_docx(file_path)
            else:
                if self.table_window: self.table_window.show_error_message("Error de Carga", f"Tipo de archivo no soportado: {file_type}")
                return

            if df is not None and header_data is not None:
                self.script_model._dataframe = df # Direct update as per subtask
                self.script_model.set_header_data(header_data) # Notifies listeners
                
                self.current_script_path = file_path
                self.script_model.undo_stack.clear() # Triggers _handle_clean_changed -> set_unsaved_changes(False)
                self.set_unsaved_changes(False) # Explicitly ensure it's false after load

                self.script_model.notify_listeners("script_loaded") # No data as per refined subtask interpretation
                
                if self.table_window: self.table_window.show_info_message("Éxito", f"Guion '{os.path.basename(file_path)}' cargado.")
                if self.main_window_ref and hasattr(self.main_window_ref, 'add_to_recent_files'):
                    self.main_window_ref.add_to_recent_files(file_path)
            else:
                if self.table_window: self.table_window.show_error_message("Error de Carga", f"No se pudieron cargar datos desde: {file_path}")
        except Exception as e:
            if self.table_window: self.table_window.show_error_message("Error de Carga", f"Error al cargar guion: {str(e)}")


    def handle_save_script_request(self, file_path: str, file_type: str):
        header_data = self.script_model.get_header_data()
        df_to_save = self.script_model.get_dataframe()
        success = False
        try:
            if file_type == "excel":
                self.script_model.guion_manager.save_to_excel(file_path, df_to_save, header_data)
                success = True
            elif file_type == "json":
                self.script_model.guion_manager.save_to_json(file_path, df_to_save, header_data)
                success = True
            else:
                if self.table_window: self.table_window.show_error_message("Error al Guardar", f"Tipo de archivo no soportado: {file_type}")
                return

            if success:
                self.current_script_path = file_path
                self.script_model.undo_stack.setClean() # Triggers _handle_clean_changed -> set_unsaved_changes(False)
                self.set_unsaved_changes(False) # Explicitly ensure it's false after save
                if self.table_window: self.table_window.show_info_message("Éxito", f"Guion guardado en '{file_path}'.")
                if self.main_window_ref and hasattr(self.main_window_ref, 'add_to_recent_files'):
                    self.main_window_ref.add_to_recent_files(file_path)
        except Exception as e:
            if self.table_window: self.table_window.show_error_message("Error al Guardar", f"Error al guardar guion: {str(e)}")


    def handle_add_row_request(self, df_insert_idx: int, data: Optional[Dict[str, Any]] = None):
        command = AddRowCommand(self.script_model, df_insert_idx, data)
        self.script_model.undo_stack.push(command)

    def handle_remove_rows_request(self, df_indices: List[int]):
        if not df_indices: return # Avoid pushing command for no-op
        command = RemoveRowsCommand(self.script_model, df_indices)
        self.script_model.undo_stack.push(command)

    def handle_move_row_request(self, source_df_idx: int, target_df_idx: int):
        if source_df_idx == target_df_idx : return # Avoid pushing command for no-op
        command = MoveRowCommand(self.script_model, source_df_idx, target_df_idx)
        self.script_model.undo_stack.push(command)

    def handle_edit_cell_request(self, df_row_idx: int, df_col_name: str, old_value: Any, new_value: Any):
        if old_value == new_value:
            return
        command = EditCommand(self.script_model, df_row_idx, df_col_name, old_value, new_value)
        self.script_model.undo_stack.push(command)

    def handle_split_intervention_request(self, df_idx: int, before_text: str, after_text: str):
        command = SplitInterventionCommand(self.script_model, df_idx, before_text, after_text)
        self.script_model.undo_stack.push(command)

    def handle_merge_interventions_request(self, df_idx_curr: int, merged_dialog: str):
        command = MergeInterventionsCommand(self.script_model, df_idx_curr, merged_dialog)
        self.script_model.undo_stack.push(command)

    def handle_change_scene_request(self, df_start_idx: int):
        command = ChangeSceneCommand(self.script_model, df_start_idx)
        self.script_model.undo_stack.push(command)

    def handle_adjust_dialogs_request(self):
        self.script_model.undo_stack.beginMacro("Ajustar Diálogos")
        changed_count = 0
        df = self.script_model.get_dataframe()
        for idx in range(len(df)):
            original_dialog = str(df.at[idx, 'DIÁLOGO'])
            # Use imported utility function 'ajustar_dialogo'
            adjusted_text = ajustar_dialogo(original_dialog) 
            if original_dialog != adjusted_text:
                cmd = EditCommand(self.script_model, idx, 'DIÁLOGO', original_dialog, adjusted_text, 
                                  description=f"Ajustar diálogo en fila {idx}")
                self.script_model.undo_stack.push(cmd)
                changed_count +=1
        
        if changed_count == 0:
            self.script_model.undo_stack.endMacro() # End macro even if no changes to keep stack clean
            if self.table_window: self.table_window.show_info_message("Info", "No hubo diálogos que ajustar.")
        else:
            self.script_model.undo_stack.endMacro()
            if self.table_window: self.table_window.show_info_message("Éxito", f"{changed_count} diálogo(s) ajustado(s).")


    def handle_update_character_name_request(self, old_name: str, new_name: str):
        if not new_name.strip():
            if self.table_window: self.table_window.show_warning_message("Nombre Inválido", "Nombre no puede ser vacío.")
            return
            
        self.script_model.undo_stack.beginMacro(f"Cambiar '{old_name}' a '{new_name}'")
        changed_count = 0
        df = self.script_model.get_dataframe()
        for idx in range(len(df)):
            if str(df.at[idx, 'PERSONAJE']) == old_name:
                cmd = EditCommand(self.script_model, idx, 'PERSONAJE', old_name, new_name,
                                  description=f"Cambiar nombre personaje en fila {idx}")
                self.script_model.undo_stack.push(cmd)
                changed_count += 1
        
        if changed_count == 0:
            self.script_model.undo_stack.endMacro()
        else:
            self.script_model.undo_stack.endMacro()


    def handle_find_replace_request(self, find_text: str, replace_text: str, search_in_character: bool, search_in_dialogue: bool):
        if not find_text: # Cannot find/replace empty string meaningfully
            if self.table_window: self.table_window.show_warning_message("Buscar", "Texto a buscar no puede ser vacío.")
            return

        self.script_model.undo_stack.beginMacro("Buscar y Reemplazar")
        changed_count = 0
        df = self.script_model.get_dataframe()
        
        for idx in range(len(df)):
            if search_in_character and 'PERSONAJE' in df.columns:
                old_val = str(df.at[idx, 'PERSONAJE'])
                if find_text.lower() in old_val.lower(): # Case-insensitive find
                    new_val = re.sub(find_text, replace_text, old_val, flags=re.IGNORECASE)
                    if old_val != new_val:
                        cmd = EditCommand(self.script_model, idx, 'PERSONAJE', old_val, new_val)
                        self.script_model.undo_stack.push(cmd)
                        changed_count +=1
            if search_in_dialogue and 'DIÁLOGO' in df.columns:
                old_val = str(df.at[idx, 'DIÁLOGO'])
                if find_text.lower() in old_val.lower():
                    new_val = re.sub(find_text, replace_text, old_val, flags=re.IGNORECASE)
                    if old_val != new_val:
                        cmd = EditCommand(self.script_model, idx, 'DIÁLOGO', old_val, new_val)
                        self.script_model.undo_stack.push(cmd)
                        changed_count +=1
        
        if changed_count == 0:
            self.script_model.undo_stack.endMacro()
            if self.table_window: self.table_window.show_info_message("Reemplazar", "No se encontraron coincidencias.")
        else:
            self.script_model.undo_stack.endMacro()
            if self.table_window: self.table_window.show_info_message("Reemplazar", f"{changed_count} reemplazo(s) realizado(s).")


    def handle_renumber_scenes_to_default_request(self):
        self.script_model.undo_stack.beginMacro("Renumerar Escenas a 1")
        changed_count = 0
        if not self.script_model.has_scene_numbers:
            df = self.script_model.get_dataframe()
            for idx in range(len(df)):
                old_scene = str(df.at[idx, 'SCENE'])
                if old_scene != "1": # Only change if not already "1"
                    cmd = EditCommand(self.script_model, idx, 'SCENE', old_scene, "1")
                    self.script_model.undo_stack.push(cmd)
                    changed_count +=1
        
        if changed_count == 0:
            self.script_model.undo_stack.endMacro()
        else:
            self.script_model.undo_stack.endMacro()


    def handle_undo_request(self):
        if self.script_model.undo_stack.canUndo():
            self.script_model.undo_stack.undo()

    def handle_redo_request(self):
        if self.script_model.undo_stack.canRedo():
            self.script_model.undo_stack.redo()
