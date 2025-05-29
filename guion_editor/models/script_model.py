import pandas as pd
from PyQt6.QtGui import QUndoStack
from guion_editor.utils.guion_manager import GuionManager
from guion_editor.utils.dialog_utils import ajustar_dialogo
from typing import List, Dict, Optional, Any
import re

class ScriptModel:
    def __init__(self):
        self.guion_manager = GuionManager()
        self._dataframe = pd.DataFrame(columns=self.guion_manager.ALL_COLUMNS)
        self.reference_number = ""
        self.product_name = ""
        self.chapter_number = ""
        self.selected_type = ""
        self.undo_stack = QUndoStack()
        self._listeners = []
        # Regex for HH:MM:SS:FF format
        self.timecode_regex = re.compile(r"^\d{2}:\d{2}:\d{2}:\d{2}$")

    @property
    def has_scene_numbers(self) -> bool:
        if self._dataframe.empty or 'SCENE' not in self._dataframe.columns:
            return False
        try:
            # Ensure scene values are strings for consistent comparison
            scene_series = self._dataframe['SCENE'].astype(str).str.strip()
            unique_scenes = scene_series.unique()
            
            if len(unique_scenes) > 1:
                return True
            if len(unique_scenes) == 1:
                # Check if the single unique scene is neither "1" nor "" (empty string)
                single_scene_val = unique_scenes[0]
                if single_scene_val != "1" and single_scene_val != "":
                    return True
            return False
        except Exception as e:
            print(f"Error checking has_scene_numbers: {e}")
            return False


    def get_dataframe(self):
        return self._dataframe

    def get_header_data(self):
        return {
            "reference_number": self.reference_number,
            "product_name": self.product_name,
            "chapter_number": self.chapter_number,
            "selected_type": self.selected_type,
        }

    def set_header_data(self, header_data: dict):
        self.reference_number = header_data.get("reference_number", self.reference_number)
        self.product_name = header_data.get("product_name", self.product_name)
        self.chapter_number = header_data.get("chapter_number", self.chapter_number)
        self.selected_type = header_data.get("selected_type", self.selected_type)
        self.notify_listeners("header_data_changed", self.get_header_data())

    def subscribe(self, listener_callback):
        if listener_callback not in self._listeners:
            self._listeners.append(listener_callback)

    def notify_listeners(self, event_type: str, data: Any = None):
        for listener in self._listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                print(f"Error notifying listener {listener}: {e}")

    # --- Timecode Conversion Utilities ---
    def convert_time_code_to_milliseconds(self, time_code: str) -> int:
        if not self.timecode_regex.match(time_code):
            # print(f"Warning: Invalid timecode format '{time_code}' for conversion. Returning 0ms.")
            return 0
        try:
            parts = time_code.split(':')
            h, m, s, f = map(int, parts)
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / 25.0) * 1000.0))
        except ValueError: # Should be caught by regex, but as a safeguard
            return 0
        except Exception as e:
            print(f"Error converting timecode '{time_code}' to milliseconds: {e}")
            return 0

    def convert_milliseconds_to_time_code(self, ms: int) -> str:
        try:
            if ms < 0: ms = 0
            MS_PER_HOUR, MS_PER_MINUTE, MS_PER_SECOND = 3600000, 60000, 1000
            h, rem_h = divmod(ms, MS_PER_HOUR)
            m, rem_m = divmod(rem_h, MS_PER_MINUTE)
            s, rem_s_ms = divmod(rem_m, MS_PER_SECOND)
            f = int(round(rem_s_ms / (1000.0 / 25.0)))
            if f >= 25: f = 24
            return f"{int(h):02}:{int(m):02}:{int(s):02}:{int(f):02}"
        except Exception as e:
            print(f"Error converting {ms}ms to timecode: {e}")
            return "00:00:00:00"

    # --- ID Management ---
    def get_next_id(self) -> int:
        if self._dataframe.empty or 'ID' not in self._dataframe.columns:
            return 0
        numeric_ids = pd.to_numeric(self._dataframe['ID'], errors='coerce').dropna()
        return int(numeric_ids.max()) + 1 if not numeric_ids.empty else 0

    def find_df_index_by_id(self, id_value: int) -> Optional[int]:
        if 'ID' not in self._dataframe.columns or self._dataframe.empty:
            return None
        try:
            id_series_numeric = pd.to_numeric(self._dataframe['ID'], errors='coerce')
            matches = self._dataframe.index[id_series_numeric == id_value].tolist()
            return matches[0] if matches else None
        except Exception as e:
            print(f"Error finding df index by ID {id_value}: {e}")
            return None

    # --- Row Operations ---
    def add_row_data(self, df_insert_idx: int, data_dict: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        actual_row_data: Dict[str, Any] = {}
        if data_dict is None:
            actual_row_data = {col: "" for col in self.guion_manager.ALL_COLUMNS}
            actual_row_data['ID'] = self.get_next_id()
            actual_row_data['SCENE'] = "1" # Default scene as string
            actual_row_data['IN'] = "00:00:00:00"
            actual_row_data['OUT'] = "00:00:00:00"
        else:
            actual_row_data = {col: data_dict.get(col, "") for col in self.guion_manager.ALL_COLUMNS}
            if 'ID' not in data_dict or pd.isna(data_dict['ID']) or str(data_dict['ID']).strip() == "":
                actual_row_data['ID'] = self.get_next_id()
            else: # Ensure ID is stored consistently, e.g. as int or string if preferred
                actual_row_data['ID'] = data_dict['ID'] 
            if 'SCENE' in actual_row_data: # Ensure SCENE is string
                 actual_row_data['SCENE'] = str(actual_row_data['SCENE'])


        for col in self.guion_manager.ALL_COLUMNS:
            if col not in actual_row_data: actual_row_data[col] = ""
        
        new_row_series = pd.Series(actual_row_data)
        try:
            requested_df_insert_idx = max(0, df_insert_idx)
            if requested_df_insert_idx >= len(self._dataframe):
                self._dataframe = pd.concat([self._dataframe, new_row_series.to_frame().T], ignore_index=True)
            else:
                df_part1 = self._dataframe.iloc[:requested_df_insert_idx]
                df_part2 = self._dataframe.iloc[requested_df_insert_idx:]
                self._dataframe = pd.concat([df_part1, new_row_series.to_frame().T, df_part2]).reset_index(drop=True)
            self.notify_listeners("rows_added", {"indices": [requested_df_insert_idx], "count": 1})
            return actual_row_data
        except Exception as e:
            print(f"Error adding row data: {e}")
            self._dataframe.reset_index(drop=True, inplace=True)
            return None

    def remove_rows_by_indices(self, df_indices: List[int]) -> List[Dict[str, Any]]:
        removed_rows_data: List[Dict[str, Any]] = []
        if not df_indices or self._dataframe.empty: return removed_rows_data
        valid_indices_to_remove = sorted([idx for idx in list(set(df_indices)) if 0 <= idx < len(self._dataframe)], reverse=True)
        if not valid_indices_to_remove: return removed_rows_data
        for idx in valid_indices_to_remove:
            removed_rows_data.insert(0, self._dataframe.iloc[idx].to_dict())
        try:
            self._dataframe.drop(index=valid_indices_to_remove, inplace=True)
            self._dataframe.reset_index(drop=True, inplace=True)
            self.notify_listeners("rows_removed", {"indices": df_indices})
            return removed_rows_data
        except Exception as e:
            print(f"Error removing rows by indices: {e}")
            self._dataframe.reset_index(drop=True, inplace=True)
            return []

    def move_row_data(self, source_df_idx: int, target_df_idx: int) -> bool:
        if not (0 <= source_df_idx < len(self._dataframe)):
            print(f"Error moving row: Source index {source_df_idx} out of bounds.")
            return False
        clamped_target_df_idx = max(0, min(target_df_idx, len(self._dataframe)))
        try:
            row_to_move = self._dataframe.iloc[source_df_idx].copy()
            temp_df = self._dataframe.drop(index=source_df_idx).reset_index(drop=True)
            insertion_point_in_temp_df = clamped_target_df_idx
            if source_df_idx < clamped_target_df_idx: insertion_point_in_temp_df = clamped_target_df_idx - 1
            insertion_point_in_temp_df = max(0, min(insertion_point_in_temp_df, len(temp_df)))
            if insertion_point_in_temp_df == len(temp_df):
                 self._dataframe = pd.concat([temp_df, row_to_move.to_frame().T]).reset_index(drop=True)
            else:
                df_part1 = temp_df.iloc[:insertion_point_in_temp_df]
                df_part2 = temp_df.iloc[insertion_point_in_temp_df:]
                self._dataframe = pd.concat([df_part1, row_to_move.to_frame().T, df_part2]).reset_index(drop=True)
            self.notify_listeners("rows_moved", {"source": source_df_idx, "target": target_df_idx})
            return True
        except Exception as e:
            print(f"Error moving row data from {source_df_idx} to {target_df_idx}: {e}")
            self._dataframe.reset_index(drop=True, inplace=True)
            return False

    def update_cell_data(self, df_row_idx: int, df_col_name: str, new_value: Any) -> bool:
        if not (0 <= df_row_idx < len(self._dataframe)):
            print(f"Error updating cell: Row index {df_row_idx} out of bounds.")
            return False
        if df_col_name not in self._dataframe.columns:
            print(f"Error updating cell: Column '{df_col_name}' does not exist.")
            return False

        if df_col_name == 'ID':
            print("Error: 'ID' column cannot be changed directly using update_cell_data.")
            return False

        validated_new_value = new_value
        if df_col_name in ['IN', 'OUT']:
            if not isinstance(new_value, str) or not self.timecode_regex.match(new_value):
                print(f"Error: Invalid timecode format '{new_value}' for column '{df_col_name}'. Must be HH:MM:SS:FF.")
                return False
        elif df_col_name == 'SCENE':
            validated_new_value = str(new_value) # Ensure SCENE is stored as string

        try:
            old_value = self._dataframe.at[df_row_idx, df_col_name]
            if old_value != validated_new_value: # Only update and notify if value changed
                self._dataframe.at[df_row_idx, df_col_name] = validated_new_value
                if df_col_name in ['PERSONAJE', 'DIÁLOGO', 'SCENE', 'IN', 'OUT']:
                    self.notify_listeners("cell_updated", {
                        "row": df_row_idx, 
                        "col_name": df_col_name, 
                        "new_value": validated_new_value
                    })
            return True
        except Exception as e:
            print(f"Error updating cell data at ({df_row_idx}, {df_col_name}): {e}")
            return False

    # --- Relocated and Adapted Intervention Logic ---
    def split_intervention_data(self, df_idx_to_split: int, before_text: str, after_text: str) -> Optional[Dict[str, Any]]:
        if not (0 <= df_idx_to_split < len(self._dataframe)):
            print(f"Error splitting: Index {df_idx_to_split} out of bounds.")
            return None

        # Update the original row's dialog
        if not self.update_cell_data(df_idx_to_split, 'DIÁLOGO', before_text):
            print(f"Error updating dialog for original part of split at index {df_idx_to_split}.")
            return None

        # Create new row data for the part after split
        original_row_data = self._dataframe.iloc[df_idx_to_split].copy().to_dict()
        new_row_data = original_row_data
        new_row_data['ID'] = self.get_next_id()
        new_row_data['DIÁLOGO'] = after_text
        # Optional: Set 'IN' of new row to 'OUT' of original row
        # new_row_data['IN'] = original_row_data.get('OUT', "00:00:00:00") 

        return self.add_row_data(df_idx_to_split + 1, new_row_data)

    def merge_interventions_data(self, df_idx_curr: int, merged_dialog: str) -> bool:
        df_idx_next = df_idx_curr + 1
        if not (0 <= df_idx_curr < len(self._dataframe) and 0 <= df_idx_next < len(self._dataframe)):
            print("Error merging: Current or next index out of bounds.")
            return False

        out_time_next_row = str(self._dataframe.at[df_idx_next, 'OUT'])

        # Update current row's dialog and OUT time
        if not self.update_cell_data(df_idx_curr, 'DIÁLOGO', merged_dialog):
            return False
        if not self.update_cell_data(df_idx_curr, 'OUT', out_time_next_row):
            # Attempt to revert dialog change if OUT update fails
            # This is simplistic; proper transaction handling would be better
            # For now, we proceed, but this could leave data inconsistent if not handled by undo stack
            print(f"Warning: Failed to update OUT time during merge for row {df_idx_curr}. Dialog was updated.")
            # return False # Or decide to proceed with dialog change only

        # Remove the next row
        removed_rows = self.remove_rows_by_indices([df_idx_next])
        return bool(removed_rows)

    # --- Relocated and Adapted Other Data Operations ---
    def adjust_dialogs_data(self) -> int:
        changed_count = 0
        if 'DIÁLOGO' not in self._dataframe.columns: return 0
        for df_idx in range(len(self._dataframe)):
            original_dialog = str(self._dataframe.at[df_idx, 'DIÁLOGO'])
            adjusted_text = ajustar_dialogo(original_dialog)
            if original_dialog != adjusted_text:
                if self.update_cell_data(df_idx, 'DIÁLOGO', adjusted_text):
                    changed_count += 1
        return changed_count

    def update_in_out_data(self, df_idx: int, column_name: str, time_code_str: str) -> bool:
        if column_name not in ['IN', 'OUT']:
            print(f"Error: Invalid column '{column_name}' for IN/OUT update.")
            return False
        return self.update_cell_data(df_idx, column_name, time_code_str)

    def change_scene_data(self, df_start_idx: int) -> Dict[int, str]:
        old_scenes_map: Dict[int, str] = {}
        if not (0 <= df_start_idx < len(self._dataframe)) or 'SCENE' not in self._dataframe.columns:
            return old_scenes_map

        current_scene_val_str = str(self._dataframe.at[df_start_idx, 'SCENE']).strip()
        try:
            # Attempt to convert to int, assuming scene numbers are numeric or can be
            current_scene_num = int(current_scene_val_str) if current_scene_val_str else 0
        except ValueError:
            # If current scene is not a simple number (e.g., "1A", "EXT. PARK"),
            # this logic might need adjustment based on desired behavior.
            # For now, treat non-integer as 0 for incrementing.
            current_scene_num = 0 
        
        new_scene_str = str(current_scene_num + 1)

        for df_idx in range(df_start_idx, len(self._dataframe)):
            old_scenes_map[df_idx] = str(self._dataframe.at[df_idx, 'SCENE'])
            self.update_cell_data(df_idx, 'SCENE', new_scene_str) # update_cell_data ensures it's stored as string
        return old_scenes_map

    def update_character_name_data(self, old_name: str, new_name: str) -> int:
        changed_count = 0
        if 'PERSONAJE' not in self._dataframe.columns or not new_name.strip(): return 0
        
        for df_idx in range(len(self._dataframe)):
            if str(self._dataframe.at[df_idx, 'PERSONAJE']) == old_name:
                if self.update_cell_data(df_idx, 'PERSONAJE', new_name):
                    changed_count += 1
        return changed_count

    def find_and_replace_data(self, find_text: str, replace_text: str, search_in_character: bool, search_in_dialogue: bool) -> int:
        changed_count = 0
        if not find_text: return 0 # Cannot find empty string effectively for replacement

        # For case-insensitive replacement, pandas str.replace with regex=True and flags=re.IGNORECASE
        # is powerful, but update_cell_data operates cell by cell.
        # We'll do case-insensitive find, then replace.
        
        for df_idx in range(len(self._dataframe)):
            if search_in_character and 'PERSONAJE' in self._dataframe.columns:
                char_text = str(self._dataframe.at[df_idx, 'PERSONAJE'])
                # Perform case-insensitive find
                if find_text.lower() in char_text.lower():
                    # For replacement, use original find_text to respect its casing if needed,
                    # or use re.sub for more complex replacement. Simple str.replace is case-sensitive.
                    # Using re.sub for case-insensitive replacement:
                    new_char_text = re.sub(find_text, replace_text, char_text, flags=re.IGNORECASE)
                    if char_text != new_char_text:
                        if self.update_cell_data(df_idx, 'PERSONAJE', new_char_text):
                            changed_count +=1
            
            if search_in_dialogue and 'DIÁLOGO' in self._dataframe.columns:
                dialog_text = str(self._dataframe.at[df_idx, 'DIÁLOGO'])
                if find_text.lower() in dialog_text.lower():
                    new_dialog_text = re.sub(find_text, replace_text, dialog_text, flags=re.IGNORECASE)
                    if dialog_text != new_dialog_text:
                        if self.update_cell_data(df_idx, 'DIÁLOGO', new_dialog_text):
                            changed_count += 1
        return changed_count

    def renumber_scenes_to_default_data(self) -> int:
        changed_count = 0
        if self._dataframe.empty or 'SCENE' not in self._dataframe.columns:
            return 0
        
        # Condition: not self.has_scene_numbers implies scenes are all "1", all empty, or a mix.
        # We want to change to "1" IF they are not already "1".
        # The original logic was "if not self.has_scene_numbers".
        # If has_scene_numbers is False, it means either:
        # 1. All scenes are "1" or "" (or a mix).
        # 2. DataFrame is empty or no SCENE column (handled).
        # So, we should renumber to "1" if has_scene_numbers is False,
        # and the current value is not "1".
        if not self.has_scene_numbers:
            for df_idx in range(len(self._dataframe)):
                current_scene = str(self._dataframe.at[df_idx, 'SCENE']).strip()
                if current_scene != "1":
                    if self.update_cell_data(df_idx, 'SCENE', "1"):
                        changed_count += 1
        return changed_count
