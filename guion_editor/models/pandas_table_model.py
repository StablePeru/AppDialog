# guion_editor/models/pandas_table_model.py
import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSignal
from PyQt6.QtGui import QColor, QBrush
from typing import Any, List, Dict, Optional, Tuple

VALID_TIME_BG_COLOR = QColor(Qt.GlobalColor.white)
INVALID_TIME_BG_COLOR = QColor(255, 200, 200)

class PandasTableModel(QAbstractTableModel):
    data_changed_for_undo = pyqtSignal(int, int, object, object) # df_row_idx, view_col_idx, old_val, new_val
    rows_about_to_be_inserted_for_undo = pyqtSignal(int, int) # df_insert_idx, count
    rows_inserted_for_undo = pyqtSignal(int, int, list) # df_insert_idx, count, list_of_ids_inserted
    rows_about_to_be_removed_for_undo = pyqtSignal(list) # list_of_df_indices_to_remove
    rows_removed_for_undo = pyqtSignal(list, list) # list_of_df_indices_removed, list_of_removed_data_dicts

    layoutChangedSignal = pyqtSignal() # To signal full layout updates like modelReset

    def __init__(self, column_map: Dict[int, str], view_column_names: List[str], parent=None):
        super().__init__(parent)
        self._dataframe = pd.DataFrame(columns=list(column_map.values()))
        self.column_map = column_map # Maps view column index to DataFrame column name
        self.view_column_names = view_column_names
        self.df_column_order = list(column_map.values()) # Expected order in DataFrame

        # Precompute reverse mapping for faster lookups
        self.df_col_to_view_col: Dict[str, int] = {v: k for k, v in column_map.items()}


    def dataframe(self) -> pd.DataFrame:
        return self._dataframe

    def set_dataframe(self, dataframe: pd.DataFrame):
        self.beginResetModel()
        self._dataframe = dataframe.copy() if dataframe is not None else pd.DataFrame(columns=self.df_column_order)
        # Ensure all expected columns exist
        for df_col_name in self.df_column_order:
            if df_col_name not in self._dataframe.columns:
                if df_col_name == 'ID':
                    self._dataframe[df_col_name] = pd.Series(dtype='Int64') # Use Int64 for nullable integers
                elif df_col_name in ['IN', 'OUT']:
                    self._dataframe[df_col_name] = "00:00:00:00"
                elif df_col_name == 'SCENE':
                     self._dataframe[df_col_name] = "1"
                else:
                    self._dataframe[df_col_name] = ""

        # Ensure 'ID' column is of a numeric type that can handle NaNs, then integers
        if 'ID' in self._dataframe.columns:
            self._dataframe['ID'] = pd.to_numeric(self._dataframe['ID'], errors='coerce').astype('Int64')

        # Reorder DF columns to match expected order, handling missing columns
        cols_in_df = [col for col in self.df_column_order if col in self._dataframe.columns]
        other_cols = [col for col in self._dataframe.columns if col not in self.df_column_order]
        self._dataframe = self._dataframe[cols_in_df + other_cols]

        self.endResetModel()
        self.layoutChangedSignal.emit()


    def rowCount(self, parent=QModelIndex()):
        return len(self._dataframe)

    def columnCount(self, parent=QModelIndex()):
        return len(self.view_column_names)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        df_row_idx = index.row()
        view_col_idx = index.column()
        
        df_col_name = self.column_map.get(view_col_idx)

        if df_col_name is None or df_row_idx >= len(self._dataframe) or df_col_name not in self._dataframe.columns:
            return None

        value = self._dataframe.iat[df_row_idx, self._dataframe.columns.get_loc(df_col_name)]
        
        if pd.isna(value): # Handle NaN values gracefully
            value = ""

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return str(value)
        
        if role == Qt.ItemDataRole.BackgroundRole:
            if df_col_name in ["IN", "OUT"]:
                # Validation logic needs to be accessible here or handled by the view/delegate
                # For now, let's assume a method exists or pass it
                # This part is tricky as model shouldn't ideally know about view validation colors directly
                # This might be better handled by TableWindow after dataChanged signal
                pass # Defer IN/OUT color validation to TableWindow for now

        return None

    def setData(self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        df_row_idx = index.row()
        view_col_idx = index.column()
        df_col_name = self.column_map.get(view_col_idx)

        if df_col_name is None or df_row_idx >= len(self._dataframe) or df_col_name not in self._dataframe.columns:
            return False

        df_col_idx_num = self._dataframe.columns.get_loc(df_col_name)
        old_value = self._dataframe.iat[df_row_idx, df_col_idx_num]
        
        # Type conversion based on column
        try:
            if df_col_name == 'ID':
                new_typed_value = int(value) if value else pd.NA
            elif df_col_name == 'SCENE':
                new_typed_value = str(value).strip()
                if new_typed_value: int(new_typed_value) # Validate if it can be int
            else:
                new_typed_value = str(value)
        except ValueError:
            # print(f"Warning: Could not convert '{value}' for column '{df_col_name}'. Using original value.")
            return False # Indicate failure

        self._dataframe.iat[df_row_idx, df_col_idx_num] = new_typed_value
        self.dataChanged.emit(index, index, [role])
        # self.data_changed_for_undo.emit(df_row_idx, view_col_idx, old_value, new_typed_value)
        return True

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if 0 <= section < len(self.view_column_names):
                    return self.view_column_names[section]
            # Optional: Row numbers for vertical header
            # if orientation == Qt.Orientation.Vertical:
            #     return str(section + 1)
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        # Make ID column non-editable by default through flags
        df_col_name = self.column_map.get(index.column())
        if df_col_name == 'ID':
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def insert_row_data(self, df_row_idx_to_insert_at: int, row_data: Dict[str, Any]) -> bool:
        """Inserts a single row represented by a dictionary."""
        self.beginInsertRows(QModelIndex(), df_row_idx_to_insert_at, df_row_idx_to_insert_at)
        
        new_row_series = pd.Series(row_data, index=self.df_column_order)
        
        # Ensure ID is Int64 if present
        if 'ID' in new_row_series:
            new_row_series['ID'] = pd.to_numeric(new_row_series['ID'], errors='coerce').astype('Int64')

        if df_row_idx_to_insert_at >= len(self._dataframe): # Append
            self._dataframe = pd.concat([self._dataframe, pd.DataFrame([new_row_series])], ignore_index=True)
        else: # Insert
            df_part1 = self._dataframe.iloc[:df_row_idx_to_insert_at]
            df_part2 = self._dataframe.iloc[df_row_idx_to_insert_at:]
            self._dataframe = pd.concat([df_part1, pd.DataFrame([new_row_series]), df_part2], ignore_index=True)
        
        self.endInsertRows()
        return True

    def remove_row_by_df_index(self, df_row_idx: int) -> Optional[pd.Series]:
        """Removes a single row by its DataFrame index and returns the removed row's data."""
        if 0 <= df_row_idx < len(self._dataframe):
            self.beginRemoveRows(QModelIndex(), df_row_idx, df_row_idx)
            removed_row_data = self._dataframe.iloc[df_row_idx].copy()
            self._dataframe.drop(index=df_row_idx, inplace=True)
            self._dataframe.reset_index(drop=True, inplace=True)
            self.endRemoveRows()
            return removed_row_data
        return None

    def move_df_row(self, source_df_idx: int, target_df_idx: int) -> bool:
        """Moves a row within the DataFrame from source_df_idx to target_df_idx."""
        if not (0 <= source_df_idx < len(self._dataframe) and 0 <= target_df_idx <= len(self._dataframe)):
            return False

        # PyQt6 beginMoveRows expects destination to be where item will be *after* removal
        # If source is before dest, dest_param = dest. If source is after dest, dest_param = dest.
        # However, if moving down, target_df_idx is where it will be inserted *before* items shift.
        # If source_df_idx < target_df_idx (moving down), the effective insertion point for Qt is target_df_idx.
        # If source_df_idx > target_df_idx (moving up), the effective insertion point for Qt is target_df_idx.
        # The target_param for beginMoveRows is the row *before which* the source rows will appear
        # *after* they are removed from their original position.
        # If moving row 2 to row 5 (0-indexed), it's removed, list shrinks, then inserted at new 5.
        # If source_df_idx < target_df_idx (move down, e.g. 0 -> 2)
        #   row is removed from 0. list shifts. row inserted at 2 (which was 3). target is target_df_idx
        # If source_df_idx > target_df_idx (move up, e.g. 2 -> 0)
        #   row is removed from 2. list shifts. row inserted at 0. target is target_df_idx

        # Qt needs the destination parent and destination row. For a flat list/table, parent is QModelIndex().
        # The 'destinationChild' in beginMoveRows is the row *before which* the moved rows will appear.
        # If moving down (source_idx < dest_idx), the row is inserted at dest_idx, so it appears *before* dest_idx + 1.
        # If moving up (source_idx > dest_idx), the row is inserted at dest_idx, so it appears *before* dest_idx.
        
        # Correction for Qt's destination parameter in beginMoveRows:
        # If moving a row from `s` to `d`:
        # - If `s < d` (moving down), the row is inserted at index `d`. After insertion, it will be at `d`.
        #   The item previously at `d` will be at `d+1`. Qt's dest is `d+1`.
        # - If `s > d` (moving up), the row is inserted at index `d`. After insertion, it will be at `d`.
        #   The item previously at `d` will be at `d+1`. Qt's dest is `d`.

        qt_target_row = target_df_idx + 1 if source_df_idx < target_df_idx else target_df_idx
        
        if not self.beginMoveRows(QModelIndex(), source_df_idx, source_df_idx, QModelIndex(), qt_target_row):
            return False

        try:
            row_to_move = self._dataframe.iloc[source_df_idx].copy()
            temp_df = self._dataframe.drop(index=source_df_idx).reset_index(drop=True)
            
            # Adjust target_df_idx if source was removed before it
            # No, target_df_idx is the final position in the modified list (after pop)
            # If source_df_idx < target_df_idx, actual insertion index in temp_df is target_df_idx - 1
            # If source_df_idx > target_df_idx, actual insertion index in temp_df is target_df_idx

            # Simpler: convert to list of dicts, move, then back to DataFrame
            rows_list = self._dataframe.to_dict(orient='records')
            moved_row_data = rows_list.pop(source_df_idx)
            
            # Ensure target_df_idx is valid for insertion after pop
            # If source_df_idx < target_df_idx, the effective insertion is target_df_idx - 1
            # Example: move 0 to 2 (in [a,b,c,d]). pop a. list is [b,c,d]. target_df_idx = 2. insert at 2-1=1 -> [b,a,c,d]
            # this is not what we want. target_df_idx should be the final desired index.

            # if source_df_idx < target_df_idx:
            #     insert_idx_in_popped_list = target_df_idx -1
            # else:
            #     insert_idx_in_popped_list = target_df_idx

            # No, target_df_idx is the final index. If list is [0,1,2,3,4], move 1 to 3.
            # popped = rows_list.pop(1) -> [0,2,3,4]
            # rows_list.insert(3, popped) -> [0,2,3,popped,4] this is correct.

            rows_list.insert(target_df_idx, moved_row_data)
            self._dataframe = pd.DataFrame(rows_list, columns=self.df_column_order)

        except Exception as e:
            # print(f"Error during DataFrame row move: {e}")
            self.endMoveRows() # Must always call endMoveRows
            return False
        
        self.endMoveRows()
        return True

    def get_next_id(self) -> int:
        if not self._dataframe.empty and 'ID' in self._dataframe.columns:
            numeric_ids = pd.to_numeric(self._dataframe['ID'], errors='coerce').dropna()
            if not numeric_ids.empty:
                return int(numeric_ids.max()) + 1
        return 0

    def find_df_index_by_id(self, id_value: int) -> Optional[int]:
        if 'ID' not in self._dataframe.columns or self._dataframe.empty:
            return None
        df_ids_numeric = pd.to_numeric(self._dataframe['ID'], errors='coerce')
        matches = self._dataframe.index[df_ids_numeric == id_value].tolist()
        return matches[0] if matches else None

    def get_view_column_index(self, df_column_name: str) -> Optional[int]:
        return self.df_col_to_view_col.get(df_column_name)

    def get_df_column_name(self, view_column_index: int) -> Optional[str]:
        return self.column_map.get(view_column_index)