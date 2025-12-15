from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import pandas as pd
from typing import Dict, List, Set
from guion_editor import constants_logic as C

class ValidationWorker(QObject):
    """
    Worker class to perform heavy validation checks on the dataframe in a background thread.
    """
    validation_finished = pyqtSignal(dict)  # Returns the new validation status dictionary

    @pyqtSlot(pd.DataFrame)
    def validate(self, df: pd.DataFrame):
        """
        Performs the heavy line count validation logic.
        """
        new_status: Dict[int, Dict[str, bool]] = {}
        
        if not df.empty:
            # Filter rows that have at least one timecode set (optimization)
            # Actually, the original logic checks rows where IN != default OR OUT != default
            # But here we act on the passed copy
            
            # Note: We must respect the original logic's grouping
            df_valid_times = df[(df[C.COL_IN] != C.DEFAULT_TIMECODE) | (df[C.COL_OUT] != C.DEFAULT_TIMECODE)]
            
            if not df_valid_times.empty:
                # Group by IN and OUT to find simultaneous subtitles
                for _, group_df in df_valid_times.groupby([C.COL_IN, C.COL_OUT]):
                    group_indices = group_df.index.tolist()
                    
                    dialogo_error_indices = self._check_group_for_column(df, group_indices, C.COL_DIALOGO)
                    euskera_error_indices = self._check_group_for_column(df, group_indices, C.COL_EUSKERA)
                    
                    for idx in group_indices:
                        new_status[idx] = {
                            C.COL_DIALOGO: idx not in dialogo_error_indices,
                            C.COL_EUSKERA: idx not in euskera_error_indices
                        }

        # Emit the result back to the main thread
        self.validation_finished.emit(new_status)

    def _check_group_for_column(self, df: pd.DataFrame, group_indices: List[int], col_to_check: str) -> Set[int]:
        """
        Checks line constraints for a group of simultaneous subtitles.
        """
        total_lines_in_group = 0
        lines_per_char: Dict[str, int] = {}
        rows_per_char: Dict[str, List[int]] = {}
        error_indices_for_this_column = set()

        for idx in group_indices:
            # Access data safely from the dataframe copy
            text_val = df.at[idx, col_to_check]
            char_val = df.at[idx, C.COL_PERSONAJE]
            
            text = str(text_val) if pd.notna(text_val) else ""
            char = str(char_val) if pd.notna(char_val) else ""

            line_count = (text.count('\n') + 1) if text.strip() else 0
            
            total_lines_in_group += line_count
            
            lines_per_char[char] = lines_per_char.get(char, 0) + line_count
            if char not in rows_per_char: rows_per_char[char] = []
            rows_per_char[char].append(idx)

        character_error_found = False
        
        # Rule 1: A single character cannot have 6 or more lines in a simultaneous block
        for char, count in lines_per_char.items():
            if count >= 6:
                character_error_found = True
                error_indices_for_this_column.update(rows_per_char[char])
        
        # Rule 2: Total lines in the simultaneous block cannot be 11 or more
        if not character_error_found and total_lines_in_group >= 11:
            error_indices_for_this_column.update(group_indices)
            
        return error_indices_for_this_column
