# guion_editor/commands/undo_commands.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, List, Dict, Optional, Tuple

import pandas as pd
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QAbstractItemView, QMessageBox

# Para evitar importaciones circulares, usamos TYPE_CHECKING.
# 'TableWindow' solo se importa para la comprobación de tipos, no en tiempo de ejecución.
if TYPE_CHECKING:
    from guion_editor.widgets.table_window import TableWindow


class EditCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', df_row_index: int, view_col_index: int, old_value: Any, new_value: Any):
        super().__init__()
        self.tw = table_window
        self.df_row_idx = df_row_index
        self.view_col_idx = view_col_index
        self.old_value = old_value
        self.new_value = new_value
        df_col_name = self.tw.pandas_model.get_df_column_name(self.view_col_idx) or f"Col {view_col_index}"
        self.setText(f"Editar '{df_col_name}' en fila {self.df_row_idx + 1}")

    def _apply_value(self, value_to_apply: Any):
        model_idx = self.tw.pandas_model.index(self.df_row_idx, self.view_col_idx)
        if model_idx.isValid():
            self.tw.pandas_model.setData(model_idx, value_to_apply, Qt.ItemDataRole.EditRole)

    def undo(self):
        self._apply_value(self.old_value)
        self.tw.set_unsaved_changes(True)

    def redo(self):
        self._apply_value(self.new_value)
        self.tw.set_unsaved_changes(True)


class AddRowCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', view_row_insert_at: int, df_row_insert_at: int):
        super().__init__()
        self.tw = table_window
        self.view_row_insert_at = view_row_insert_at
        self.df_row_insert_at = df_row_insert_at
        self.new_row_id = -1
        self.new_row_data: Optional[Dict] = None
        self.setText("Agregar fila")

    def redo(self):
        self.new_row_id = self.tw.pandas_model.get_next_id()
        current_df = self.tw.pandas_model.dataframe()
        scene, char = ("1" if not self.tw.has_scene_numbers() else ""), ""
        if 0 < self.df_row_insert_at <= len(current_df):
            prev_df_idx = self.df_row_insert_at - 1
            scene = str(current_df.at[prev_df_idx, 'SCENE'])
            char = str(current_df.at[prev_df_idx, 'PERSONAJE'])
        elif not current_df.empty and self.df_row_insert_at == len(current_df):
            last_df_idx = len(current_df) - 1
            scene = str(current_df.at[last_df_idx, 'SCENE'])
            char = str(current_df.at[last_df_idx, 'PERSONAJE'])

        self.new_row_data = {'ID': self.new_row_id, 'SCENE': scene, 'IN': '00:00:00:00', 'OUT': '00:00:00:00', 'PERSONAJE': char, 'DIÁLOGO': '', 'EUSKERA': ''}
        self.tw.pandas_model.insert_row_data(self.df_row_insert_at, self.new_row_data)
        self.tw.table_view.selectRow(self.view_row_insert_at)
        idx_to_scroll = self.tw.pandas_model.index(self.view_row_insert_at, 0)
        if idx_to_scroll.isValid():
            self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer_and_notify()
        self.setText(f"Agregar fila (ID {self.new_row_id}) en pos. {self.df_row_insert_at + 1}")

    def undo(self):
        if self.new_row_id == -1:
            return
        idx_to_remove = self.tw.pandas_model.find_df_index_by_id(self.new_row_id)
        if idx_to_remove is None:
            idx_to_remove = self.df_row_insert_at
        if idx_to_remove is not None and 0 <= idx_to_remove < self.tw.pandas_model.rowCount():
            self.tw.pandas_model.remove_row_by_df_index(idx_to_remove)
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer_and_notify()


class RemoveRowsCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', df_indices_to_remove: List[int]):
        super().__init__()
        self.tw = table_window
        self.df_indices = sorted(df_indices_to_remove)
        self.removed_data_list: List[Tuple[int, pd.Series]] = []
        self.setText(f"Eliminar {len(self.df_indices)} fila(s)")

    def redo(self):
        self.removed_data_list.clear()
        for df_idx in sorted(self.df_indices, reverse=True):
            removed_series = self.tw.pandas_model.remove_row_by_df_index(df_idx)
            if removed_series is not None:
                self.removed_data_list.insert(0, (df_idx, removed_series))
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer_and_notify()

    def undo(self):
        for original_df_idx, row_data_series in sorted(self.removed_data_list, key=lambda x: x[0]):
            self.tw.pandas_model.insert_row_data(original_df_idx, row_data_series.to_dict())
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer_and_notify()


class MoveRowCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', df_source_idx: int, df_target_idx: int):
        super().__init__()
        self.tw = table_window
        self.df_source_idx, self.df_target_idx = df_source_idx, df_target_idx
        self.setText(f"Mover fila {df_source_idx + 1} a {df_target_idx + 1}")

    def _move(self, from_idx, to_idx):
        if self.tw.pandas_model.move_df_row(from_idx, to_idx):
            self.tw.table_view.selectRow(to_idx)
            idx_to_scroll = self.tw.pandas_model.index(to_idx, 0)
            if idx_to_scroll.isValid():
                self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
            self.tw.set_unsaved_changes(True)

    def undo(self):
        self._move(self.df_target_idx, self.df_source_idx)

    def redo(self):
        self._move(self.df_source_idx, self.df_target_idx)


class SplitInterventionCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', df_idx_split: int,
                 before_txt: str, after_txt: str, text_before_split: str,
                 df_column_name_to_split: str):
        super().__init__()
        self.tw = table_window
        self.df_idx_split = df_idx_split
        self.before_txt = before_txt
        self.after_txt = after_txt
        self.text_that_was_split = text_before_split
        self.df_column_name_to_split = df_column_name_to_split
        self.new_row_id = -1
        self.setText(f"Separar '{self.df_column_name_to_split}' en fila {df_idx_split + 1}")

    def redo(self):
        current_df = self.tw.pandas_model.dataframe()
        if not (0 <= self.df_idx_split < len(current_df)):
            print(f"SplitInterventionCommand.redo: df_idx_split ({self.df_idx_split}) out of bounds for df len ({len(current_df)})")
            return

        self.new_row_id = self.tw.pandas_model.get_next_id()

        target_col_view_idx = self.tw.pandas_model.get_view_column_index(self.df_column_name_to_split)
        if target_col_view_idx is None:
            print(f"SplitInterventionCommand.redo: Columna '{self.df_column_name_to_split}' no encontrada en el mapeo del modelo.")
            return

        original_row_data_for_new_row = current_df.iloc[self.df_idx_split].copy().to_dict()

        self.tw.pandas_model.setData(
            self.tw.pandas_model.index(self.df_idx_split, target_col_view_idx),
            self.before_txt,
            Qt.ItemDataRole.EditRole
        )

        new_row_full_data = {**original_row_data_for_new_row, 'ID': self.new_row_id}
        new_row_full_data[self.df_column_name_to_split] = self.after_txt

        if self.df_column_name_to_split == 'DIÁLOGO':
            if 'EUSKERA' in new_row_full_data:
                new_row_full_data['EUSKERA'] = ""
        elif self.df_column_name_to_split == 'EUSKERA':
            if 'DIÁLOGO' in new_row_full_data:
                new_row_full_data['DIÁLOGO'] = ""

        self.tw.pandas_model.insert_row_data(self.df_idx_split + 1, new_row_full_data)

        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer_and_notify()

        self.tw.table_view.selectRow(self.df_idx_split + 1)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx_split + 1, 0)
        if idx_to_scroll.isValid():
            self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)

        self.tw.request_resize_rows_to_contents_deferred()

    def undo(self):
        if self.new_row_id == -1:
            return

        target_col_view_idx = self.tw.pandas_model.get_view_column_index(self.df_column_name_to_split)
        if target_col_view_idx is None:
            print(f"SplitInterventionCommand.undo: Columna '{self.df_column_name_to_split}' no encontrada.")
            return

        self.tw.pandas_model.setData(
            self.tw.pandas_model.index(self.df_idx_split, target_col_view_idx),
            self.text_that_was_split,
            Qt.ItemDataRole.EditRole
        )

        idx_to_remove = self.tw.pandas_model.find_df_index_by_id(self.new_row_id)
        if idx_to_remove is None:
            idx_to_remove = self.df_idx_split + 1
            print(f"SplitInterventionCommand.undo: Could not find row by ID {self.new_row_id}, attempting to remove at index {idx_to_remove}.")

        if idx_to_remove is not None and 0 <= idx_to_remove < self.tw.pandas_model.rowCount():
            self.tw.pandas_model.remove_row_by_df_index(idx_to_remove)
        else:
            print(f"SplitInterventionCommand.undo: Row to remove (ID {self.new_row_id} or index {idx_to_remove}) not found or index invalid.")

        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer_and_notify()

        self.tw.table_view.selectRow(self.df_idx_split)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx_split, 0)
        if idx_to_scroll.isValid():
            self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)

        self.tw.request_resize_rows_to_contents_deferred()


class MergeInterventionsCommand(QUndoCommand):
    def __init__(self, tw: 'TableWindow', df_idx_first_row: int,
                 merged_dialog_text: str, merged_euskera_text: str,
                 df_idx_second_row_original: int, original_out_time_first_row: str):
        super().__init__()
        self.tw = tw
        self.df_idx1 = df_idx_first_row
        self.merged_dlg = merged_dialog_text
        self.merged_eusk = merged_euskera_text
        self.df_idx2_rem_orig = df_idx_second_row_original

        self.orig_out1 = original_out_time_first_row
        self.orig_dlg1: Optional[str] = None
        self.orig_eusk1: Optional[str] = None
        self.data_df_idx2: Optional[pd.Series] = None

        self.setText(f"Juntar filas {df_idx_first_row + 1} y {df_idx_first_row + 2}")

    def redo(self):
        current_df = self.tw.pandas_model.dataframe()
        df_idx_actual_second_row_to_merge = self.df_idx1 + 1

        if not (0 <= self.df_idx1 < len(current_df) and \
                0 <= df_idx_actual_second_row_to_merge < len(current_df)):
            print(f"MergeCommand.redo: Indices out of bounds. df_idx1={self.df_idx1}, actual_second_idx={df_idx_actual_second_row_to_merge}, df_len={len(current_df)}")
            return

        if self.orig_dlg1 is None:
            self.orig_dlg1 = str(current_df.at[self.df_idx1, 'DIÁLOGO'])
        if self.orig_eusk1 is None:
            self.orig_eusk1 = str(current_df.at[self.df_idx1, 'EUSKERA'])

        if self.data_df_idx2 is None:
            self.data_df_idx2 = current_df.iloc[df_idx_actual_second_row_to_merge].copy()

        view_col_dlg = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        view_col_eusk = self.tw.pandas_model.get_view_column_index('EUSKERA')
        view_col_out = self.tw.pandas_model.get_view_column_index('OUT')

        if view_col_dlg is None or view_col_out is None or view_col_eusk is None:
            print("MergeCommand.redo: One or more critical column view indices not found.")
            return

        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_dlg), self.merged_dlg, Qt.ItemDataRole.EditRole)
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_eusk), self.merged_eusk, Qt.ItemDataRole.EditRole)

        if self.data_df_idx2 is not None and 'OUT' in self.data_df_idx2 and pd.notna(self.data_df_idx2['OUT']):
             self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_out), self.data_df_idx2['OUT'], Qt.ItemDataRole.EditRole)

        self.tw.pandas_model.remove_row_by_df_index(df_idx_actual_second_row_to_merge)

        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer_and_notify()
        self.tw.table_view.selectRow(self.df_idx1)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx1, 0)
        if idx_to_scroll.isValid():
            self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
        self.tw.request_resize_rows_to_contents_deferred()


    def undo(self):
        if self.orig_dlg1 is None or self.data_df_idx2 is None or self.orig_eusk1 is None:
            print("MergeCommand.undo: Original data for undo not available.")
            return

        view_col_dlg = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        view_col_eusk = self.tw.pandas_model.get_view_column_index('EUSKERA')
        view_col_out = self.tw.pandas_model.get_view_column_index('OUT')

        if view_col_dlg is None or view_col_out is None or view_col_eusk is None:
            print("MergeCommand.undo: One or more critical column view indices not found.")
            return

        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_dlg), self.orig_dlg1, Qt.ItemDataRole.EditRole)
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_eusk), self.orig_eusk1, Qt.ItemDataRole.EditRole)
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_out), self.orig_out1, Qt.ItemDataRole.EditRole)

        self.tw.pandas_model.insert_row_data(self.df_idx1 + 1, self.data_df_idx2.to_dict())

        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer_and_notify()
        self.tw.table_view.selectRow(self.df_idx1)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx1, 0)
        if idx_to_scroll.isValid():
            self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
        self.tw.request_resize_rows_to_contents_deferred()


class ChangeSceneCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', df_start_idx: int):
        super().__init__()
        self.tw = table_window
        self.df_start_idx = df_start_idx
        self.old_scenes_map: Dict[int, str] = {}
        self.setText(f"Incrementar escena desde fila {df_start_idx + 1}")

    def _apply_scenes(self, scene_map: Dict[int, str], select_row: Optional[int]):
        view_col_scene = self.tw.pandas_model.get_view_column_index('SCENE')
        if view_col_scene is None:
            return
        for df_idx, scene_val in scene_map.items():
            if 0 <= df_idx < self.tw.pandas_model.rowCount():
                self.tw.pandas_model.setData(self.tw.pandas_model.index(df_idx, view_col_scene), scene_val, Qt.ItemDataRole.EditRole)
        if select_row is not None and 0 <= select_row < self.tw.pandas_model.rowCount():
            self.tw.table_view.selectRow(select_row)
            idx_to_scroll = self.tw.pandas_model.index(select_row, 0)
            if idx_to_scroll.isValid():
                self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
        self.tw.set_unsaved_changes(True)

    def redo(self):
        current_df = self.tw.pandas_model.dataframe()
        if not (0 <= self.df_start_idx < len(current_df)):
            self.setText(f"Incrementar escena (fila {self.df_start_idx+1} inválida)")
            return

        for df_idx in range(self.df_start_idx, len(current_df)):
            scene_val_str = str(current_df.at[df_idx, 'SCENE']).strip()
            try:
                int(scene_val_str)
            except ValueError:
                QMessageBox.warning(self.tw, "Cambiar Escena",
                                    f"El valor de escena en la fila {df_idx + 1} ('{scene_val_str}') "
                                    "no es un número simple. No se puede autoincrementar en bloque. "
                                    "Todas las escenas desde la seleccionada deben ser numéricas.")
                self.setText("Incrementar escena (escena no numérica encontrada)")
                return

        self.old_scenes_map.clear()
        new_scenes_map_for_redo: Dict[int, str] = {}

        for df_idx in range(self.df_start_idx, len(current_df)):
            original_scene_str = str(current_df.at[df_idx, 'SCENE'])
            self.old_scenes_map[df_idx] = original_scene_str

            scene_num = int(original_scene_str.strip())
            new_scene_val = str(scene_num + 1)
            new_scenes_map_for_redo[df_idx] = new_scene_val

        self._apply_scenes(new_scenes_map_for_redo, self.df_start_idx)
        self.setText(f"Incrementar escenas desde fila {self.df_start_idx + 1}")

    def undo(self):
        if not self.old_scenes_map:
            self.setText(f"Incrementar escena (sin datos para undo)")
            return
        self._apply_scenes(self.old_scenes_map, self.df_start_idx)


class HeaderEditCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', old_header_data: Dict[str, Any], new_header_data: Dict[str, Any], text: str = "Cambiar datos de cabecera"):
        super().__init__(text)
        self.tw = table_window
        self.old_data = old_header_data.copy()
        self.new_data = new_header_data.copy()

    def redo(self):
        self.tw._populate_header_ui(self.new_data)
        self.tw._current_header_data_for_undo = self.new_data.copy()
        self.tw.set_unsaved_changes(True)
        self.tw._update_toggle_header_button_text_and_icon()

    def undo(self):
        self.tw._populate_header_ui(self.old_data)
        self.tw._current_header_data_for_undo = self.old_data.copy()
        self.tw.set_unsaved_changes(True)
        self.tw._update_toggle_header_button_text_and_icon()

class ToggleBookmarkCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', df_indices: List[int]):
        super().__init__()
        self.tw = table_window
        self.df_indices = df_indices
        self.original_states: Dict[int, bool] = {}

        for df_idx in self.df_indices:
            if 0 <= df_idx < self.tw.pandas_model.rowCount():
                self.original_states[df_idx] = self.tw.pandas_model.dataframe().at[df_idx, 'BOOKMARK']
        
        self.setText(f"Marcar/Desmarcar {len(self.df_indices)} fila(s)")

    def _set_bookmark_state(self, is_bookmarked: bool, df_idx: int):
        """Método auxiliar para cambiar el estado de una fila."""
        view_col_bookmark = self.tw.pandas_model.get_view_column_index('BOOKMARK')
        if view_col_bookmark is not None:
            model_idx = self.tw.pandas_model.index(df_idx, view_col_bookmark)
            self.tw.pandas_model.setData(model_idx, is_bookmarked, Qt.ItemDataRole.EditRole)

    def redo(self):
        """Aplica el estado contrario al original."""
        for df_idx, original_state in self.original_states.items():
            self._set_bookmark_state(not original_state, df_idx)
        self.tw.set_unsaved_changes(True)

    def undo(self):
        """Restaura el estado original."""
        for df_idx, original_state in self.original_states.items():
            self._set_bookmark_state(original_state, df_idx)
        self.tw.set_unsaved_changes(True)

# -> INICIO: NUEVO COMANDO PARA UNIFICAR PERSONAJES
class UpdateMultipleCharactersCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', old_names_list: List[str], new_name: str):
        super().__init__()
        self.tw = table_window
        self.old_names_list = old_names_list
        self.new_name = new_name
        self.original_series: Optional[pd.Series] = None
        
        text = f"Unificar personajes a '{self.new_name}'"
        if len(self.old_names_list) == 1:
            text = f"Renombrar '{self.old_names_list[0]}' a '{self.new_name}'"
        self.setText(text)

    def redo(self):
        model = self.tw.pandas_model
        df = model.dataframe()
        
        # Máscara para encontrar todas las filas cuyos nombres de personaje (limpios)
        # están en la lista de nombres antiguos.
        mask = df['PERSONAJE'].astype(str).str.strip().isin(self.old_names_list)
        
        if not mask.any():
            # Si no se encuentra ninguna coincidencia, no hay nada que hacer.
            # Esto puede ocurrir si los datos cambiaron entre la creación del comando y su ejecución.
            return

        # Si es la primera vez que se ejecuta, guardar los datos originales para poder deshacer.
        if self.original_series is None:
            self.original_series = df.loc[mask, 'PERSONAJE'].copy()

        # Aplicar el nuevo nombre a todas las filas que coinciden.
        # Usamos .loc para asegurar que estamos modificando el DataFrame original.
        df.loc[mask, 'PERSONAJE'] = self.new_name
        
        # Notificar a la vista que los datos han cambiado. layoutChanged es una forma
        # robusta de asegurar que todo se actualice (incluida la ventana de reparto).
        model.layoutChanged.emit()
        self.tw.set_unsaved_changes(True)

    def undo(self):
        if self.original_series is None or self.original_series.empty:
            return

        model = self.tw.pandas_model
        df = model.dataframe()

        # Restaurar los valores originales usando el índice guardado en la Serie.
        df.loc[self.original_series.index, 'PERSONAJE'] = self.original_series
        
        model.layoutChanged.emit()
        self.tw.set_unsaved_changes(True)

class SplitCharacterCommand(QUndoCommand):
    def __init__(self, table_window: 'TableWindow', old_name: str, new_name1: str, new_name2: str):
        super().__init__()
        self.tw = table_window
        self.old_name = old_name
        self.new_name1 = new_name1
        self.new_name2 = new_name2
        
        # Guardaremos los datos originales para poder deshacer
        self.original_rows_data: Dict[int, pd.Series] = {}
        # Guardaremos los IDs de las nuevas filas creadas para poder borrarlas al deshacer
        self.added_row_ids: List[int] = []

        self.setText(f"Separar '{old_name}' en '{new_name1}' y '{new_name2}'")

    def redo(self):
        model = self.tw.pandas_model
        df = model.dataframe()
        
        # Encontrar todas las filas que coinciden con el nombre antiguo
        indices_to_split = df[df['PERSONAJE'] == self.old_name].index.tolist()
        
        if not indices_to_split:
            return

        view_col_char = model.get_view_column_index('PERSONAJE')
        if view_col_char is None:
            return

        # Guardar datos originales si es la primera vez que se ejecuta
        if not self.original_rows_data:
            for df_idx in indices_to_split:
                self.original_rows_data[df_idx] = df.iloc[df_idx].copy()

        self.added_row_ids.clear()

        # Iteramos en orden inverso para que las inserciones no afecten los índices de las filas pendientes
        for df_idx in reversed(indices_to_split):
            # 1. Renombrar la fila original al primer nombre nuevo
            model.setData(model.index(df_idx, view_col_char), self.new_name1, Qt.ItemDataRole.EditRole)
            
            # 2. Preparar los datos para la nueva fila duplicada
            original_row_data = df.iloc[df_idx].to_dict()
            new_row_data = original_row_data.copy()
            new_row_data['PERSONAJE'] = self.new_name2
            
            # 3. Asignar un ID único a la nueva fila
            new_id = model.get_next_id()
            new_row_data['ID'] = new_id
            self.added_row_ids.append(new_id)
            
            # 4. Insertar la nueva fila justo después de la original
            model.insert_row_data(df_idx + 1, new_row_data)

        self.tw.set_unsaved_changes(True)
        # Notificar a la vista que la estructura ha cambiado drásticamente
        model.layoutChanged.emit()

    def undo(self):
        if not self.original_rows_data:
            return

        model = self.tw.pandas_model
        
        # 1. Eliminar las filas que se añadieron
        for row_id in self.added_row_ids:
            df_idx_to_remove = model.find_df_index_by_id(row_id)
            if df_idx_to_remove is not None:
                model.remove_row_by_df_index(df_idx_to_remove)
        
        # 2. Restaurar el nombre original en las filas que se modificaron
        view_col_char = model.get_view_column_index('PERSONAJE')
        if view_col_char is not None:
            for df_idx in self.original_rows_data.keys():
                model.setData(model.index(df_idx, view_col_char), self.old_name, Qt.ItemDataRole.EditRole)

        self.tw.set_unsaved_changes(True)
        model.layoutChanged.emit()