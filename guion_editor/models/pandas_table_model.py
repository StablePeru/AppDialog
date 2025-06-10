# guion_editor/models/pandas_table_model.py
import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSignal
from PyQt6.QtGui import QColor, QBrush
from typing import Any, List, Dict, Optional, Tuple

# Colores de validación (apropiados para tema oscuro)
VALID_TIME_BG_COLOR = QColor(Qt.GlobalColor.transparent) # Sin color de fondo para válido
INVALID_TIME_BG_COLOR = QColor(139, 0, 0) # Rojo oscuro para inválido

ROW_NUMBER_COL_IDENTIFIER = "__ROW_NUMBER__"
MAX_INTERVENTION_DURATION_MS = 30000 # Límite de 30 segundos en milisegundos

class PandasTableModel(QAbstractTableModel):
    layoutChangedSignal = pyqtSignal()

    def __init__(self, column_map: Dict[int, str], view_column_names: List[str], parent=None):
        super().__init__(parent)
        self.column_map = column_map
        self.view_column_names = view_column_names
        self.df_column_order = [
            col_name for col_name in column_map.values()
            if col_name != ROW_NUMBER_COL_IDENTIFIER
        ]

        self._dataframe = pd.DataFrame(columns=self.df_column_order)
        self._ensure_df_structure()

        self.df_col_to_view_col: Dict[str, int] = {
            df_name: view_idx for view_idx, df_name in column_map.items()
            if df_name != ROW_NUMBER_COL_IDENTIFIER
        }
        self._time_validation_status: Dict[int, bool] = {}
        self._scene_validation_status: Dict[int, bool] = {}

    def _ensure_df_structure(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        target_df = df if df is not None else self._dataframe

        for df_col_name in self.df_column_order:
            if df_col_name not in target_df.columns:
                if df_col_name == 'ID':
                    target_df[df_col_name] = pd.Series(dtype='Int64')
                elif df_col_name in ['IN', 'OUT']:
                    target_df[df_col_name] = "00:00:00:00"
                elif df_col_name == 'SCENE':
                    target_df[df_col_name] = "1"
                else:
                    target_df[df_col_name] = ""

        if 'ID' in target_df.columns:
            target_df['ID'] = pd.to_numeric(target_df['ID'], errors='coerce').astype('Int64')
        if 'SCENE' in target_df.columns:
             target_df['SCENE'] = target_df['SCENE'].astype(str)

        cols_in_df_ordered = [col for col in self.df_column_order if col in target_df.columns]
        other_cols = [col for col in target_df.columns if col not in self.df_column_order]

        final_df = target_df[cols_in_df_ordered + other_cols]

        if df is None:
            self._dataframe = final_df

        return final_df

    def dataframe(self) -> pd.DataFrame:
        return self._dataframe

    def set_dataframe(self, dataframe: pd.DataFrame):
        self.beginResetModel()
        if dataframe is not None:
            self._dataframe = self._ensure_df_structure(dataframe.copy())
        else:
            self._dataframe = pd.DataFrame(columns=self.df_column_order)
            self._dataframe = self._ensure_df_structure(self._dataframe)

        self._time_validation_status.clear()
        self._scene_validation_status.clear()
        for i in range(len(self._dataframe)):
            self._validate_in_out_for_row(i)
            self._validate_scene_for_row(i)
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

        col_identifier = self.column_map.get(view_col_idx)

        if col_identifier is None:
            return None

        if col_identifier == ROW_NUMBER_COL_IDENTIFIER:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(df_row_idx + 1)
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            return None

        df_col_name = col_identifier
        if df_row_idx >= len(self._dataframe) or df_col_name not in self._dataframe.columns:
            return None

        df_actual_col_idx = self._dataframe.columns.get_loc(df_col_name)
        value = self._dataframe.iat[df_row_idx, df_actual_col_idx]

        if pd.isna(value):
            value = ""

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return str(value)

        if role == Qt.ItemDataRole.BackgroundRole:
            if df_col_name in ["IN", "OUT"]:
                is_valid = self._time_validation_status.get(df_row_idx, True)
                return QBrush(VALID_TIME_BG_COLOR if is_valid else INVALID_TIME_BG_COLOR)
            elif df_col_name == "SCENE":
                is_valid = self._scene_validation_status.get(df_row_idx, True)
                return QBrush(VALID_TIME_BG_COLOR if is_valid else INVALID_TIME_BG_COLOR)
        return None

    def setData(self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        df_row_idx = index.row()
        view_col_idx = index.column()

        col_identifier = self.column_map.get(view_col_idx)
        if col_identifier is None: return False

        if col_identifier == ROW_NUMBER_COL_IDENTIFIER:
            return False

        df_col_name = col_identifier
        if df_row_idx >= len(self._dataframe) or df_col_name not in self._dataframe.columns:
            return False

        df_actual_col_idx = self._dataframe.columns.get_loc(df_col_name)

        try:
            str_value = str(value)
            if df_col_name == 'ID': return False
            elif df_col_name == 'SCENE':
                new_typed_value = str_value
            elif df_col_name in ['IN', 'OUT']:
                parts = str_value.split(':')
                if len(parts) == 4 and all(len(p) == 2 and p.isdigit() for p in parts):
                    new_typed_value = str_value
                else: return False
            else:
                new_typed_value = str_value
        except ValueError:
            return False

        current_df_value = self._dataframe.iat[df_row_idx, df_actual_col_idx]
        current_value_str = "" if pd.isna(current_df_value) else str(current_df_value)

        if current_value_str == new_typed_value:
            return True

        self._dataframe.iat[df_row_idx, df_actual_col_idx] = new_typed_value

        roles_changed_for_current_cell = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]

        if df_col_name in ['IN', 'OUT']:
            old_validation_status = self._time_validation_status.get(df_row_idx, True)
            self._validate_in_out_for_row(df_row_idx)
            new_validation_status = self._time_validation_status.get(df_row_idx, True)

            if old_validation_status != new_validation_status:
                roles_changed_for_current_cell.append(Qt.ItemDataRole.BackgroundRole)
                in_view_col = self.get_view_column_index('IN')
                out_view_col = self.get_view_column_index('OUT')
                if in_view_col is not None:
                    in_idx = self.index(df_row_idx, in_view_col)
                    self.dataChanged.emit(in_idx, in_idx, [Qt.ItemDataRole.BackgroundRole])
                if out_view_col is not None:
                    out_idx = self.index(df_row_idx, out_view_col)
                    self.dataChanged.emit(out_idx, out_idx, [Qt.ItemDataRole.BackgroundRole])
        elif df_col_name == 'SCENE':
            old_validation_status = self._scene_validation_status.get(df_row_idx, True)
            self._validate_scene_for_row(df_row_idx)
            new_validation_status = self._scene_validation_status.get(df_row_idx, True)
            if old_validation_status != new_validation_status:
                roles_changed_for_current_cell.append(Qt.ItemDataRole.BackgroundRole)

        self.dataChanged.emit(index, index, roles_changed_for_current_cell)
        return True

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if 0 <= section < len(self.view_column_names):
                    return self.view_column_names[section]
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        df_col_name = self.column_map.get(index.column())
        if df_col_name == 'ID':
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def insert_row_data(self, df_row_idx_to_insert_at: int, row_data_dict: Dict[str, Any]) -> bool:
        self.beginInsertRows(QModelIndex(), df_row_idx_to_insert_at, df_row_idx_to_insert_at)

        new_row_series = pd.Series(index=self.df_column_order, dtype=object)
        for col_name, value in row_data_dict.items():
            if col_name in self.df_column_order:
                if col_name == 'ID' and pd.notna(value): new_row_series[col_name] = int(value)
                elif col_name == 'SCENE': new_row_series[col_name] = str(value)
                else: new_row_series[col_name] = value

        for col_name in self.df_column_order:
            if col_name not in new_row_series or pd.isna(new_row_series[col_name]):
                if col_name == 'ID': new_row_series[col_name] = self.get_next_id()
                elif col_name in ['IN', 'OUT']: new_row_series[col_name] = "00:00:00:00"
                elif col_name == 'SCENE': new_row_series[col_name] = "1"
                elif col_name == 'EUSKERA': new_row_series[col_name] = ""
                else: new_row_series[col_name] = ""

        new_row_df = pd.DataFrame([new_row_series])

        if df_row_idx_to_insert_at >= len(self._dataframe):
            self._dataframe = pd.concat([self._dataframe, new_row_df], ignore_index=True)
        else:
            df_part1 = self._dataframe.iloc[:df_row_idx_to_insert_at]
            df_part2 = self._dataframe.iloc[df_row_idx_to_insert_at:]
            self._dataframe = pd.concat([df_part1, new_row_df, df_part2], ignore_index=True)

        self._dataframe = self._ensure_df_structure(self._dataframe)

        self._rebuild_time_validation_after_insert(df_row_idx_to_insert_at)
        self._validate_in_out_for_row(df_row_idx_to_insert_at)
        self._rebuild_scene_validation_after_insert(df_row_idx_to_insert_at)
        self._validate_scene_for_row(df_row_idx_to_insert_at)

        self.endInsertRows()
        return True

    def _rebuild_time_validation_after_insert(self, inserted_df_idx: int):
        new_status = {}
        for old_idx, is_valid in self._time_validation_status.items():
            if old_idx < inserted_df_idx:
                new_status[old_idx] = is_valid
            else:
                new_status[old_idx + 1] = is_valid
        self._time_validation_status = new_status

    def _rebuild_scene_validation_after_insert(self, inserted_df_idx: int):
        new_status = {}
        for old_idx, is_valid in self._scene_validation_status.items():
            if old_idx < inserted_df_idx:
                new_status[old_idx] = is_valid
            else:
                new_status[old_idx + 1] = is_valid
        self._scene_validation_status = new_status


    def remove_row_by_df_index(self, df_row_idx: int) -> Optional[pd.Series]:
        if 0 <= df_row_idx < len(self._dataframe):
            self.beginRemoveRows(QModelIndex(), df_row_idx, df_row_idx)
            removed_row_data = self._dataframe.iloc[df_row_idx].copy()
            self._dataframe.drop(index=df_row_idx, inplace=True)
            self._dataframe.reset_index(drop=True, inplace=True)
            self._rebuild_time_validation_after_remove(df_row_idx)
            self._rebuild_scene_validation_after_remove(df_row_idx)
            self.endRemoveRows()
            return removed_row_data
        return None

    def _rebuild_time_validation_after_remove(self, removed_df_idx: int):
        new_status = {}
        for old_idx, is_valid in self._time_validation_status.items():
            if old_idx < removed_df_idx:
                new_status[old_idx] = is_valid
            elif old_idx > removed_df_idx:
                new_status[old_idx - 1] = is_valid
        self._time_validation_status = new_status

    def _rebuild_scene_validation_after_remove(self, removed_df_idx: int):
        new_status = {}
        for old_idx, is_valid in self._scene_validation_status.items():
            if old_idx < removed_df_idx:
                new_status[old_idx] = is_valid
            elif old_idx > removed_df_idx:
                new_status[old_idx - 1] = is_valid
        self._scene_validation_status = new_status


    def move_df_row(self, source_df_idx: int, target_df_idx: int) -> bool:
        if not (0 <= source_df_idx < len(self._dataframe)): return False

        qt_target_row = target_df_idx
        if source_df_idx < target_df_idx:
             qt_target_row = target_df_idx + 1

        if not self.beginMoveRows(QModelIndex(), source_df_idx, source_df_idx, QModelIndex(), qt_target_row):
             return False
        try:
            temp_df_list = self._dataframe.to_dict(orient='records')
            moved_item_data = temp_df_list.pop(source_df_idx)
            temp_df_list.insert(target_df_idx, moved_item_data)
            self._dataframe = pd.DataFrame(temp_df_list, columns=self.df_column_order)
            self._dataframe = self._ensure_df_structure(self._dataframe)

            new_time_validation_status = {}
            new_scene_validation_status = {}
            for i in range(len(self._dataframe)):
                in_tc = str(self._dataframe.at[i, 'IN'])
                out_tc = str(self._dataframe.at[i, 'OUT'])
                in_ms = self._convert_tc_to_ms(in_tc)
                out_ms = self._convert_tc_to_ms(out_tc)

                is_time_valid = False
                if in_ms is not None and out_ms is not None:
                    duration_ms = out_ms - in_ms
                    if duration_ms >= 0 and duration_ms <= MAX_INTERVENTION_DURATION_MS:
                        is_time_valid = True
                new_time_validation_status[i] = is_time_valid

                scene_val = str(self._dataframe.at[i, 'SCENE'])
                new_scene_validation_status[i] = not (scene_val.strip() == "" or scene_val.strip().lower() == "nan")

            self._time_validation_status = new_time_validation_status
            self._scene_validation_status = new_scene_validation_status

        except Exception as e:
            self.endMoveRows()
            return False

        self.endMoveRows()
        return True

    def get_next_id(self) -> int:
        if self._dataframe.empty or 'ID' not in self._dataframe.columns or self._dataframe['ID'].isna().all():
            return 0

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
        col_identifier = self.column_map.get(view_column_index)
        if col_identifier == ROW_NUMBER_COL_IDENTIFIER:
            return None
        return col_identifier

    def _convert_tc_to_ms(self, time_code: str) -> Optional[int]:
        try:
            parts = time_code.split(':')
            if len(parts) != 4: return None
            h, m, s, f = map(int, parts)
            if not (0 <= h < 100 and 0 <= m < 60 and 0 <= s < 60 and 0 <= f < 100):
                 return None
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / 25.0) * 1000.0))
        except (ValueError, TypeError):
            return None

    def _validate_in_out_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            in_tc = str(self._dataframe.at[df_row_idx, 'IN'])
            out_tc = str(self._dataframe.at[df_row_idx, 'OUT'])

            in_ms = self._convert_tc_to_ms(in_tc)
            out_ms = self._convert_tc_to_ms(out_tc)

            is_valid = False
            if in_ms is not None and out_ms is not None:
                duration_ms = out_ms - in_ms
                # Condición: OUT debe ser >= IN Y la duración debe ser <= MAX_INTERVENTION_DURATION_MS
                if duration_ms >= 0 and duration_ms <= MAX_INTERVENTION_DURATION_MS:
                    is_valid = True
            self._time_validation_status[df_row_idx] = is_valid
        elif df_row_idx in self._time_validation_status:
                 del self._time_validation_status[df_row_idx]

    def _validate_scene_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            scene_value = str(self._dataframe.at[df_row_idx, 'SCENE'])
            is_valid = not (scene_value.strip() == "" or scene_value.strip().lower() == "nan")
            self._scene_validation_status[df_row_idx] = is_valid
        elif df_row_idx in self._scene_validation_status:
            del self._scene_validation_status[df_row_idx]


    def force_time_validation_update_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            old_status = self._time_validation_status.get(df_row_idx, True)
            self._validate_in_out_for_row(df_row_idx)
            new_status = self._time_validation_status.get(df_row_idx, True)

            if old_status != new_status:
                in_view_col = self.get_view_column_index('IN')
                out_view_col = self.get_view_column_index('OUT')
                if in_view_col is not None:
                    in_idx = self.index(df_row_idx, in_view_col)
                    self.dataChanged.emit(in_idx, in_idx, [Qt.ItemDataRole.BackgroundRole])
                if out_view_col is not None:
                    out_idx = self.index(df_row_idx, out_view_col)
                    self.dataChanged.emit(out_idx, out_idx, [Qt.ItemDataRole.BackgroundRole])

    def force_scene_validation_update_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            old_status = self._scene_validation_status.get(df_row_idx, True)
            self._validate_scene_for_row(df_row_idx)
            new_status = self._scene_validation_status.get(df_row_idx, True)

            if old_status != new_status:
                scene_view_col = self.get_view_column_index('SCENE')
                if scene_view_col is not None:
                    scene_idx = self.index(df_row_idx, scene_view_col)
                    self.dataChanged.emit(scene_idx, scene_idx, [Qt.ItemDataRole.BackgroundRole])
        return None