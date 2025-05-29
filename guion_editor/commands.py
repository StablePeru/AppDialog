from PyQt6.QtGui import QUndoCommand
from typing import Any, List, Dict, Optional
import pandas as pd # For MergeInterventionsCommand.data_df_idx2 type hint, will remove if not needed

# Forward declaration for type hinting if ScriptModel is in the same file or for clarity
# from guion_editor.models.script_model import ScriptModel
# For now, assume ScriptModel will be imported properly.
# If ScriptModel is not found, I might need to adjust the import path.
# Let's assume the path is:
from ..models.script_model import ScriptModel


class EditCommand(QUndoCommand):
    def __init__(self, script_model: ScriptModel, df_row_index: int, df_col_name: str, 
                 old_value: Any, new_value: Any, description: Optional[str] = None):
        super().__init__()
        self.script_model = script_model
        self.df_row_index = df_row_index
        self.df_col_name = df_col_name
        self.old_value = old_value
        self.new_value = new_value
        if description:
            self.setText(description)
        else:
            self.setText(f"Editar {df_col_name} en fila {df_row_index}")

    def redo(self):
        self.script_model.update_cell_data(self.df_row_index, self.df_col_name, self.new_value)

    def undo(self):
        self.script_model.update_cell_data(self.df_row_index, self.df_col_name, self.old_value)


class AddRowCommand(QUndoCommand):
    def __init__(self, script_model: ScriptModel, df_row_insert_at: int, 
                 new_row_data_dict: Optional[Dict[str, Any]] = None, description: Optional[str] = None):
        super().__init__()
        self.script_model = script_model
        self.df_row_insert_at = df_row_insert_at
        self.new_row_data_dict = new_row_data_dict 
        self.added_row_actual_data: Optional[Dict[str, Any]] = None
        if description:
            self.setText(description)
        else:
            self.setText("Agregar fila")

    def redo(self):
        self.added_row_actual_data = self.script_model.add_row_data(self.df_row_insert_at, self.new_row_data_dict)
        if self.added_row_actual_data and 'ID' in self.added_row_actual_data:
            # ID might be int or string, ensure it's presented clearly
            self.setText(f"Agregar fila (ID {self.added_row_actual_data['ID']})")

    def undo(self):
        if self.added_row_actual_data and 'ID' in self.added_row_actual_data and self.added_row_actual_data['ID'] is not None:
            # ID could be 0, so check for None explicitly if that's the convention for "no ID"
            added_id = self.added_row_actual_data['ID']
            # Ensure ID is of a type that find_df_index_by_id expects (e.g. int)
            try:
                # Assuming find_df_index_by_id expects int. Adjust if it expects string.
                id_to_find = int(added_id) 
                found_idx = self.script_model.find_df_index_by_id(id_to_find)
                if found_idx is not None:
                    self.script_model.remove_rows_by_indices([found_idx])
                else:
                    print(f"AddRowCommand undo: Could not find row with ID {added_id} for removal. Trying original insert index.")
                    # Fallback, less reliable if other operations happened
                    self.script_model.remove_rows_by_indices([self.df_row_insert_at])
            except ValueError:
                 print(f"AddRowCommand undo: ID {added_id} is not a valid integer. Trying original insert index.")
                 self.script_model.remove_rows_by_indices([self.df_row_insert_at])

        else:
            # Fallback if ID was not stored or is None
            print(f"AddRowCommand undo: No ID in added_row_actual_data. Using original insert index {self.df_row_insert_at} for removal.")
            self.script_model.remove_rows_by_indices([self.df_row_insert_at])


class RemoveRowsCommand(QUndoCommand):
    def __init__(self, script_model: ScriptModel, df_indices_to_remove: List[int], 
                 description: Optional[str] = None):
        super().__init__()
        self.script_model = script_model
        # Store sorted indices to ensure consistent behavior, especially for undo
        self.df_indices_to_remove = sorted(list(set(df_indices_to_remove)))
        self.removed_data_list: List[Dict[str, Any]] = []
        if description:
            self.setText(description)
        else:
            self.setText(f"Eliminar {len(self.df_indices_to_remove)} fila(s)")

    def redo(self):
        # ScriptModel.remove_rows_by_indices expects original indices,
        # and handles sorting descending internally for removal.
        # It returns data in the order of the provided indices (if they were sorted asc).
        self.removed_data_list = self.script_model.remove_rows_by_indices(self.df_indices_to_remove)

    def undo(self):
        if not self.removed_data_list:
            return
        # For re-adding, we need to add them back at their original indices.
        # If multiple rows were removed, adding them in the order of their original indices
        # should restore them correctly, assuming add_row_data handles index shifts.
        # To be safe, iterate through original indices and corresponding data.
        # The self.removed_data_list is already ordered by the original indices (ascending).
        for original_df_idx, row_data_dict in zip(self.df_indices_to_remove, self.removed_data_list):
            self.script_model.add_row_data(original_df_idx, row_data_dict)


class MoveRowCommand(QUndoCommand):
    def __init__(self, script_model: ScriptModel, df_source_idx: int, df_target_idx: int, 
                 description: Optional[str] = None):
        super().__init__()
        self.script_model = script_model
        self.df_source_idx = df_source_idx
        self.df_target_idx = df_target_idx
        if description:
            self.setText(description)
        else:
            self.setText(f"Mover fila {df_source_idx} a {df_target_idx}")

    def redo(self):
        self.script_model.move_row_data(self.df_source_idx, self.df_target_idx)

    def undo(self):
        # To undo a move from source to target, we move from target back to source.
        # However, the target index in the redo operation might be different from
        # the source index for the undo if other operations occurred or due to how
        # move_row_data adjusts indices.
        # The key is that ScriptModel.move_row_data handles the logic of row identity.
        # What was at df_target_idx (after redo) needs to move back to df_source_idx.
        # ScriptModel.move_row_data needs the current index of the row that was moved.
        # This is tricky if we don't know the ID of the moved row.
        # The simplest approach is to assume that if row X moved from S to T,
        # to undo, row X (now at T) moves back to S.
        # The current implementation of ScriptModel.move_row_data should handle this.
        self.script_model.move_row_data(self.df_target_idx, self.df_source_idx)


class SplitInterventionCommand(QUndoCommand):
    def __init__(self, script_model: ScriptModel, df_idx_split: int, 
                 before_txt: str, after_txt: str, description: Optional[str] = None):
        super().__init__()
        self.script_model = script_model
        self.df_idx_split = df_idx_split
        self.before_txt = before_txt
        self.after_txt = after_txt
        self.original_dialog: Optional[str] = None
        self.added_row_data: Optional[Dict[str, Any]] = None
        if description:
            self.setText(description)
        else:
            self.setText(f"Separar intervención en fila {df_idx_split}")

    def redo(self):
        try:
            # Ensure the row and column exist before trying to access .at
            if 0 <= self.df_idx_split < len(self.script_model.get_dataframe()) and \
               'DIÁLOGO' in self.script_model.get_dataframe().columns:
                self.original_dialog = self.script_model.get_dataframe().at[self.df_idx_split, 'DIÁLOGO']
            else:
                print(f"SplitInterventionCommand redo: Cannot find original dialog at index {self.df_idx_split}.")
                self.original_dialog = "" # Default if not found, though this indicates an issue
        except Exception as e:
            print(f"SplitInterventionCommand redo: Error getting original dialog: {e}")
            self.original_dialog = ""

        self.added_row_data = self.script_model.split_intervention_data(self.df_idx_split, self.before_txt, self.after_txt)

    def undo(self):
        if self.original_dialog is not None:
            self.script_model.update_cell_data(self.df_idx_split, 'DIÁLOGO', self.original_dialog)

        if self.added_row_data and 'ID' in self.added_row_data and self.added_row_data['ID'] is not None:
            added_id = self.added_row_data['ID']
            try:
                id_to_find = int(added_id)
                found_idx = self.script_model.find_df_index_by_id(id_to_find)
                if found_idx is not None:
                    self.script_model.remove_rows_by_indices([found_idx])
                else:
                    # Fallback: if the added row can't be found by ID, it's harder to remove.
                    # This might happen if its ID was changed or row deleted by other means.
                    # Removing the row immediately after the split point might be a guess.
                    print(f"SplitInterventionCommand undo: Could not find added row ID {added_id}. Trying index after split.")
                    self.script_model.remove_rows_by_indices([self.df_idx_split + 1])
            except ValueError:
                print(f"SplitInterventionCommand undo: Added row ID {added_id} is not a valid integer.")
                self.script_model.remove_rows_by_indices([self.df_idx_split + 1])


class MergeInterventionsCommand(QUndoCommand):
    def __init__(self, script_model: ScriptModel, df_idx_curr: int, merged_dialog: str, 
                 description: Optional[str] = None):
        super().__init__()
        self.script_model = script_model
        self.df_idx_curr = df_idx_curr
        self.merged_dialog = merged_dialog
        
        self.original_dialog_first: Optional[str] = None
        self.original_out_first: Optional[str] = None
        self.removed_row_data_second: Optional[Dict[str, Any]] = None # Data of the merged/removed second row
        
        if description:
            self.setText(description)
        else:
            self.setText(f"Juntar filas {df_idx_curr} y {df_idx_curr + 1}")

    def redo(self):
        df_idx_next = self.df_idx_curr + 1
        current_df = self.script_model.get_dataframe()

        if not (0 <= self.df_idx_curr < len(current_df) and 0 <= df_idx_next < len(current_df)):
            print(f"MergeInterventionsCommand redo: Indices ({self.df_idx_curr}, {df_idx_next}) out of bounds.")
            # Mark command as invalid or prevent execution? For now, it will likely fail in merge_interventions_data
            return

        try:
            self.original_dialog_first = str(current_df.at[self.df_idx_curr, 'DIÁLOGO'])
            self.original_out_first = str(current_df.at[self.df_idx_curr, 'OUT'])
            # Store the entire second row that will be removed
            self.removed_row_data_second = current_df.iloc[df_idx_next].to_dict()
        except Exception as e:
            print(f"MergeInterventionsCommand redo: Error storing original data: {e}")
            # If we can't store original data, undo might be problematic.
            return

        # As per ScriptModel.merge_interventions_data(self, df_idx_curr: int, merged_dialog: str)
        # It internally handles taking OUT from the second row.
        self.script_model.merge_interventions_data(self.df_idx_curr, self.merged_dialog)

    def undo(self):
        # Restore the first row's original dialog and OUT time
        if self.original_dialog_first is not None:
            self.script_model.update_cell_data(self.df_idx_curr, 'DIÁLOGO', self.original_dialog_first)
        if self.original_out_first is not None:
            self.script_model.update_cell_data(self.df_idx_curr, 'OUT', self.original_out_first)

        # Re-add the second row (that was removed during redo)
        if self.removed_row_data_second:
            # The second row should be added at df_idx_curr + 1
            self.script_model.add_row_data(self.df_idx_curr + 1, self.removed_row_data_second)


class ChangeSceneCommand(QUndoCommand):
    def __init__(self, script_model: ScriptModel, df_start_idx: int, 
                 description: Optional[str] = None):
        super().__init__()
        self.script_model = script_model
        self.df_start_idx = df_start_idx
        self.old_scenes_map: Dict[int, str] = {}
        if description:
            self.setText(description)
        else:
            self.setText(f"Cambiar escena desde fila {df_start_idx}")

    def redo(self):
        self.old_scenes_map = self.script_model.change_scene_data(self.df_start_idx)

    def undo(self):
        if not self.old_scenes_map:
            return
        
        # To restore, it's better to iterate from largest index to smallest if updates
        # could cause re-indexing or length changes, though update_cell_data shouldn't.
        # For safety, or if specific order is needed. Here, direct mapping should be fine.
        for df_idx, old_scene_val in self.old_scenes_map.items():
            self.script_model.update_cell_data(df_idx, 'SCENE', old_scene_val)

# Remove pd import if it's not used directly in type hints after review
# For now, `pd.Series` was removed, so `import pandas as pd` is not strictly needed.
# If `ScriptModel` returns `pd.Series` in a way that commands must handle, it might be.
# Based on current adaptation, it seems Dicts are used primarily.
# Let's remove `import pandas as pd` for now.

# Example of other commands that could be adapted:
# UpdateCharacterNameCommand, FindAndReplaceCommand, RenumberScenesToDefaultCommand
# These would follow a similar pattern:
# - Store necessary parameters.
# - In redo(), call the corresponding ScriptModel method and store any data needed for undo (e.g., old values).
# - In undo(), use stored data to revert the changes, often by calling other ScriptModel methods.
# For instance, for UpdateCharacterNameCommand:
#   redo() -> calls script_model.update_character_name_data(), might need to store a list of (idx, old_char_name) if the model method doesn't return it.
#   undo() -> iterate stored list, call update_cell_data(idx, 'PERSONAJE', old_char_name) for each.
# However, the subtask only specified these 7 commands.

```python
# Placeholder for the rest of the file if other commands were to be added later.
# For now, the file contains the 7 specified commands.
```
