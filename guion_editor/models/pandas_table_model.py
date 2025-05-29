# guion_editor/models/pandas_table_model.py
import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSignal
from PyQt6.QtGui import QColor, QBrush
from typing import Any, List, Dict, Optional, Tuple

# Colores de validación (pueden moverse a un archivo de constantes/configuración)
VALID_TIME_BG_COLOR = QColor(Qt.GlobalColor.white) # O un color de fondo "normal" del tema
INVALID_TIME_BG_COLOR = QColor(255, 200, 200) # Rojo claro para inválido

class PandasTableModel(QAbstractTableModel):
    # Señales para el sistema Undo/Redo o para que TableWindow reaccione
    # data_changed_for_undo = pyqtSignal(int, int, object, object) # df_row_idx, view_col_idx, old_val, new_val
    # ... (otras señales de undo pueden ser eliminadas si los comandos operan directamente en el modelo)

    layoutChangedSignal = pyqtSignal() # Para señalar actualizaciones completas

    def __init__(self, column_map: Dict[int, str], view_column_names: List[str], parent=None):
        super().__init__(parent)
        self.column_map = column_map
        self.view_column_names = view_column_names
        self.df_column_order = [column_map[i] for i in sorted(column_map.keys())]

        # Initialize with defined column order
        self._dataframe = pd.DataFrame(columns=self.df_column_order) 
        # _ensure_df_structure will be called by set_dataframe or if an empty df is set initially.
        # For an initially empty model, it's good to have the columns defined.
        # self._ensure_df_structure() # Call this if you want default values in an empty df on init

        # Mapeo inverso para búsquedas rápidas
        self.df_col_to_view_col: Dict[str, int] = {v: k for k, v in column_map.items()}

        self._time_validation_status: Dict[int, bool] = {}


    def _ensure_df_structure(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Ensures the DataFrame (internal or provided) has expected columns and basic types."""
        target_df = df if df is not None else self._dataframe.copy() # Work on a copy if modifying

        for df_col_name in self.df_column_order:
            if df_col_name not in target_df.columns:
                # Define default types or values for missing columns
                if df_col_name == 'ID':
                    # Use pandas' nullable integer type if appropriate, or object for mixed types
                    target_df[df_col_name] = pd.Series(dtype='object') # Or Int64 if IDs are strictly integers
                elif df_col_name in ['IN', 'OUT']:
                    target_df[df_col_name] = "00:00:00:00"
                elif df_col_name == 'SCENE':
                    target_df[df_col_name] = "1" # Default scene
                else:
                    target_df[df_col_name] = "" # Default for other text-based columns

        # Ensure specific column types after creation or data load
        if 'ID' in target_df.columns:
             # Coerce to numeric, but keep as object to allow pd.NA for missing, then potentially to Int64
            target_df['ID'] = pd.to_numeric(target_df['ID'], errors='coerce').astype('object')
            # target_df['ID'] = target_df['ID'].astype('Int64') # If all IDs must be int or NA
        if 'SCENE' in target_df.columns:
             target_df['SCENE'] = target_df['SCENE'].astype(str)
        
        # Reorder columns to match df_column_order, adding any extra columns at the end
        present_cols = [col for col in self.df_column_order if col in target_df.columns]
        # Include columns that might be in target_df but not in df_column_order (e.g. from a loaded file)
        additional_cols = [col for col in target_df.columns if col not in present_cols]
        
        return target_df[present_cols + additional_cols]


    def dataframe(self) -> pd.DataFrame:
        return self._dataframe

    def set_dataframe(self, dataframe: pd.DataFrame):
        self.beginResetModel()
        if dataframe is not None and not dataframe.empty:
            self._dataframe = self._ensure_df_structure(dataframe.copy())
        else:
            # Create an empty DataFrame with the correct columns if None or empty is passed
            self._dataframe = pd.DataFrame(columns=self.df_column_order)
            self._dataframe = self._ensure_df_structure(self._dataframe) # Ensure types for empty df
        
        self._rebuild_all_time_validation_status() # Unified validation method
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
        
        # Ensure the column actually exists in the dataframe before trying to get its location
        if df_col_name not in self._dataframe.columns:
            return None # Should not happen if _ensure_df_structure is robust

        df_actual_col_idx = self._dataframe.columns.get_loc(df_col_name)
        value = self._dataframe.iat[df_row_idx, df_actual_col_idx]
        
        if pd.isna(value): # Convert pandas NA to empty string for display/edit
            value = ""

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return str(value)
        
        if role == Qt.ItemDataRole.BackgroundRole:
            if df_col_name in ["IN", "OUT"]:
                is_valid = self._time_validation_status.get(df_row_idx, True) # Default to True if not found
                return QBrush(VALID_TIME_BG_COLOR if is_valid else INVALID_TIME_BG_COLOR)
        
        return None

    def setData(self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole):
        # This model is now read-only from the view's direct edit perspective.
        # All data changes are driven by ScriptModel via set_dataframe.
        return False

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if 0 <= section < len(self.view_column_names):
                    return self.view_column_names[section]
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        # Make all cells selectable but not editable directly through the view/model.
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        # Original flags logic:
        # df_col_name = self.column_map.get(index.column())
        # if df_col_name == 'ID': # ID no editable
        #     return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        # return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    # Removed: insert_row_data
    # Removed: remove_row_by_df_index
    # Removed: move_df_row
    # Removed: get_next_id
    # Removed: find_df_index_by_id

    def get_view_column_index(self, df_column_name: str) -> Optional[int]:
        return self.df_col_to_view_col.get(df_column_name)

    def get_df_column_name(self, view_column_index: int) -> Optional[str]:
        return self.column_map.get(view_column_index)

    # --- Timecode Validation Methods ---
    def _convert_tc_to_ms(self, time_code: str) -> Optional[int]:
        try:
            parts = time_code.split(':')
            if len(parts) != 4: return None
            h, m, s, f = map(int, parts)
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / 25.0) * 1000.0))
        except: # Catch any conversion error
            return None

    def _validate_in_out_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            in_tc = str(self._dataframe.at[df_row_idx, 'IN'])
            out_tc = str(self._dataframe.at[df_row_idx, 'OUT'])
            
            in_ms = self._convert_tc_to_ms(in_tc)
            out_ms = self._convert_tc_to_ms(out_tc)

            if in_ms is not None and out_ms is not None:
                self._time_validation_status[df_row_idx] = (out_ms >= in_ms)
            else: # Invalid timecode format means invalid state
                self._time_validation_status[df_row_idx] = False
        elif df_row_idx in self._time_validation_status: # Clean up if row index becomes invalid
             del self._time_validation_status[df_row_idx]

    def _rebuild_all_time_validation_status(self):
        """Rebuilds the time validation status for all rows."""
        self._time_validation_status.clear()
        for i in range(len(self._dataframe)):
            self._validate_in_out_for_row(i)

    def force_time_validation_update_for_row(self, df_row_idx: int):
        """Called to force a revalidation and repaint of a specific row's timecode cells."""
        if 0 <= df_row_idx < len(self._dataframe):
            self._validate_in_out_for_row(df_row_idx)
            
            # Emit dataChanged for IN and OUT cells of this row to trigger repaint
            in_view_col = self.get_view_column_index('IN')
            out_view_col = self.get_view_column_index('OUT')
            
            roles_to_update = [Qt.ItemDataRole.BackgroundRole]

            if in_view_col is not None:
                in_idx = self.index(df_row_idx, in_view_col)
                self.dataChanged.emit(in_idx, in_idx, roles_to_update)
            if out_view_col is not None:
                out_idx = self.index(df_row_idx, out_view_col)
                self.dataChanged.emit(out_idx, out_idx, roles_to_update)