# guion_editor/models/pandas_table_model.py
import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSignal, QThread, QTimer, pyqtSlot
from PyQt6.QtGui import QColor, QBrush
from typing import Any, List, Dict, Optional, Tuple, Union

from guion_editor import constants as C
from guion_editor.workers.validation_worker import ValidationWorker

# Colores de validación (apropiados para tema oscuro)
VALID_TIME_BG_COLOR = QColor(Qt.GlobalColor.transparent) # Sin color de fondo para válido
INVALID_TIME_BG_COLOR = QColor(139, 0, 0) # Rojo oscuro para inválido
BOOKMARK_BG_COLOR = QColor(221, 211, 237, 40) # Lila claro con transparencia
LINE_ERROR_BG_COLOR = QColor(255, 165, 0, 60) # Naranja con algo de transparencia

# MAX_INTERVENTION_DURATION_MS removed, using C.MAX_INTERVENTION_DURATION_MS


class PandasTableModel(QAbstractTableModel):
    layoutChangedSignal = pyqtSignal()
    start_async_validation = pyqtSignal(pd.DataFrame)


    def __init__(self, column_map: Dict[int, str], view_column_names: List[str], parent=None):
        super().__init__(parent)
        self.column_map = column_map
        self.view_column_names = view_column_names
        self.df_column_order = C.DF_COLUMN_ORDER

        self._dataframe = pd.DataFrame(columns=self.df_column_order)
        self._ensure_df_structure()

        self.df_col_to_view_col: Dict[str, int] = {
            df_name: view_idx for view_idx, df_name in column_map.items()
            if df_name != C.ROW_NUMBER_COL_IDENTIFIER and df_name != C.DURATION_COL_IDENTIFIER
        }
        self._time_validation_status: Dict[int, Union[bool, str]] = {}
        self._scene_validation_status: Dict[int, Union[bool, str]] = {}
        self._line_validation_status: Dict[int, Dict[str, bool]] = {}

        # --- Async Validation Setup ---
        self.validation_thread = QThread()
        self.worker = ValidationWorker()
        self.worker.moveToThread(self.validation_thread)
        
        # Connect signals
        self.start_async_validation.connect(self.worker.validate)
        self.worker.validation_finished.connect(self._on_validation_finished)
        self.validation_thread.start()

        # Debounce Timer
        self._validation_debounce_timer = QTimer()
        self._validation_debounce_timer.setSingleShot(True)
        self._validation_debounce_timer.setInterval(300) # 300ms debounce
        self._validation_debounce_timer.timeout.connect(self._trigger_async_validation)

        
    def _convert_ms_to_duration_str(self, ms: int) -> str:
        if ms < 0:
            return "-.s"
        return f"{ms / 1000.0:.1f}s"

    def _ensure_df_structure(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        target_df = df if df is not None else self._dataframe

        for df_col_name in self.df_column_order:
            if df_col_name not in target_df.columns:
                if df_col_name == C.COL_ID:
                    target_df[df_col_name] = pd.Series(dtype='Int64')
                elif df_col_name in [C.COL_IN, C.COL_OUT]:
                    target_df[df_col_name] = C.DEFAULT_TIMECODE
                elif df_col_name == C.COL_SCENE:
                    target_df[df_col_name] = C.DEFAULT_SCENE
                elif df_col_name == C.COL_OHARRAK:
                    target_df[df_col_name] = ""
                elif df_col_name == C.COL_BOOKMARK:
                    target_df[df_col_name] = False
                else:
                    target_df[df_col_name] = ""

        if C.COL_ID in target_df.columns:
            target_df[C.COL_ID] = pd.to_numeric(target_df[C.COL_ID], errors='coerce').astype('Int64')
        if C.COL_SCENE in target_df.columns:
             target_df[C.COL_SCENE] = target_df[C.COL_SCENE].astype(str)
        if C.COL_BOOKMARK in target_df.columns:
            target_df[C.COL_BOOKMARK] = target_df[C.COL_BOOKMARK].fillna(False).astype(bool)

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
        self.revalidate_all_lines()
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

        if col_identifier == C.ROW_NUMBER_COL_IDENTIFIER:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(df_row_idx + 1)
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            return None
            
        if col_identifier == C.DURATION_COL_IDENTIFIER:
            if role == Qt.ItemDataRole.DisplayRole:
                in_tc = self._dataframe.at[df_row_idx, C.COL_IN]
                out_tc = self._dataframe.at[df_row_idx, C.COL_OUT]
                in_ms = self._convert_tc_to_ms(in_tc)
                out_ms = self._convert_tc_to_ms(out_tc)
                if in_ms is not None and out_ms is not None:
                    duration_ms = out_ms - in_ms
                    return self._convert_ms_to_duration_str(duration_ms)
                return "?.?s"
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            return None

        df_col_name = col_identifier
        if df_row_idx >= len(self._dataframe) or df_col_name not in self._dataframe.columns:
            return None

        df_actual_col_idx = self._dataframe.columns.get_loc(df_col_name)
        value = self._dataframe.iat[df_row_idx, df_actual_col_idx]
        if pd.isna(value): value = ""

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if df_col_name == C.COL_BOOKMARK:
                return ""
            return str(value)

        if role == Qt.ItemDataRole.ToolTipRole:
            if df_col_name in [C.COL_IN, C.COL_OUT]:
                status = self._time_validation_status.get(df_row_idx, True)
                if status is not True: return status
            if df_col_name == C.COL_SCENE:
                status = self._scene_validation_status.get(df_row_idx, True)
                if status is not True: return status

        if role == Qt.ItemDataRole.BackgroundRole:
            df_row_idx = index.row()
            line_status = self._line_validation_status.get(df_row_idx)
            if line_status:
                is_col_valid = line_status.get(df_col_name, True)
                if not is_col_valid: return QBrush(LINE_ERROR_BG_COLOR)

            if df_col_name in [C.COL_IN, C.COL_OUT]:
                is_valid = self._time_validation_status.get(df_row_idx, True) is True
                if not is_valid: return QBrush(INVALID_TIME_BG_COLOR)
            elif df_col_name == C.COL_SCENE:
                is_valid = self._scene_validation_status.get(df_row_idx, True) is True
                if not is_valid: return QBrush(INVALID_TIME_BG_COLOR)

            is_bookmarked = self._dataframe.at[df_row_idx, C.COL_BOOKMARK]
            if is_bookmarked: return QBrush(BOOKMARK_BG_COLOR)
        return None

    def setData(self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole: return False

        df_row_idx = index.row()
        view_col_idx = index.column()
        col_identifier = self.column_map.get(view_col_idx)
        if col_identifier is None or col_identifier in [C.ROW_NUMBER_COL_IDENTIFIER, C.DURATION_COL_IDENTIFIER]:
            return False

        df_col_name = col_identifier
        if df_row_idx >= len(self._dataframe) or df_col_name not in self._dataframe.columns:
            return False

        try:
            if df_col_name == C.COL_BOOKMARK: new_typed_value = bool(value)
            elif df_col_name in [C.COL_IN, C.COL_OUT]:
                parts = str(value).split(':')
                if len(parts) == 4 and all(len(p) == 2 and p.isdigit() for p in parts): new_typed_value = str(value)
                else: return False
            else: new_typed_value = str(value)
        except (ValueError, TypeError): return False

        df_actual_col_idx = self._dataframe.columns.get_loc(df_col_name)
        current_df_value = self._dataframe.iat[df_row_idx, df_actual_col_idx]
        
        if df_col_name == C.COL_BOOKMARK:
            if current_df_value == new_typed_value: return True
        else:
            current_value_str = "" if pd.isna(current_df_value) else str(current_df_value)
            if current_value_str == new_typed_value: return True

        self._dataframe.iat[df_row_idx, df_actual_col_idx] = new_typed_value
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.EditRole, Qt.ItemDataRole.DisplayRole])

        if df_col_name in [C.COL_IN, C.COL_OUT]: self.force_time_validation_update_for_row(df_row_idx)
        if df_col_name == C.COL_SCENE: self.force_scene_validation_update_for_row(df_row_idx)
        if df_col_name == C.COL_BOOKMARK:
            start_index, end_index = self.index(df_row_idx, 0), self.index(df_row_idx, self.columnCount() - 1)
            self.dataChanged.emit(start_index, end_index, [Qt.ItemDataRole.BackgroundRole])
        return True

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.view_column_names):
                return self.view_column_names[section]
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid(): return Qt.ItemFlag.NoItemFlags
        col_identifier = self.column_map.get(index.column())
        if col_identifier == C.DURATION_COL_IDENTIFIER:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        df_col_name = col_identifier
        if df_col_name in [C.COL_ID, C.COL_BOOKMARK]:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def insert_row_data(self, df_row_idx_to_insert_at: int, row_data_dict: Dict[str, Any]) -> bool:
        self.beginInsertRows(QModelIndex(), df_row_idx_to_insert_at, df_row_idx_to_insert_at)

        new_row_series = pd.Series(index=self.df_column_order, dtype=object)
        for col_name, value in row_data_dict.items():
            if col_name in self.df_column_order:
                if col_name == C.COL_ID and pd.notna(value): new_row_series[col_name] = int(value)
                elif col_name == C.COL_SCENE: new_row_series[col_name] = str(value)
                elif col_name == C.COL_BOOKMARK: new_row_series[col_name] = bool(value)
                else: new_row_series[col_name] = value

        for col_name in self.df_column_order:
            if col_name not in new_row_series or pd.isna(new_row_series[col_name]):
                if col_name == C.COL_ID: new_row_series[col_name] = self.get_next_id()
                elif col_name in [C.COL_IN, C.COL_OUT]: new_row_series[col_name] = C.DEFAULT_TIMECODE
                elif col_name == C.COL_SCENE: new_row_series[col_name] = C.DEFAULT_SCENE
                elif col_name in [C.COL_EUSKERA, C.COL_OHARRAK]: new_row_series[col_name] = ""
                elif col_name == C.COL_BOOKMARK: new_row_series[col_name] = False
                else: new_row_series[col_name] = ""

        new_row_df = pd.DataFrame([new_row_series])
        if df_row_idx_to_insert_at >= len(self._dataframe):
            self._dataframe = pd.concat([self._dataframe, new_row_df], ignore_index=True)
        else:
            df_part1, df_part2 = self._dataframe.iloc[:df_row_idx_to_insert_at], self._dataframe.iloc[df_row_idx_to_insert_at:]
            self._dataframe = pd.concat([df_part1, new_row_df, df_part2], ignore_index=True)
        self._dataframe = self._ensure_df_structure(self._dataframe)
        self._rebuild_time_validation_after_insert(df_row_idx_to_insert_at)
        self._validate_in_out_for_row(df_row_idx_to_insert_at)
        self._rebuild_scene_validation_after_insert(df_row_idx_to_insert_at)
        self._validate_scene_for_row(df_row_idx_to_insert_at)
        self.endInsertRows()
        # self._revalidate_all_lines()
        return True

    def _rebuild_time_validation_after_insert(self, inserted_df_idx: int):
        new_status = {}
        for old_idx, is_valid in self._time_validation_status.items():
            new_status[old_idx if old_idx < inserted_df_idx else old_idx + 1] = is_valid
        self._time_validation_status = new_status

    def _rebuild_scene_validation_after_insert(self, inserted_df_idx: int):
        new_status = {}
        for old_idx, is_valid in self._scene_validation_status.items():
            new_status[old_idx if old_idx < inserted_df_idx else old_idx + 1] = is_valid
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
            if old_idx < removed_df_idx: new_status[old_idx] = is_valid
            elif old_idx > removed_df_idx: new_status[old_idx - 1] = is_valid
        self._time_validation_status = new_status

    def _rebuild_scene_validation_after_remove(self, removed_df_idx: int):
        new_status = {}
        for old_idx, is_valid in self._scene_validation_status.items():
            if old_idx < removed_df_idx: new_status[old_idx] = is_valid
            elif old_idx > removed_df_idx: new_status[old_idx - 1] = is_valid
        self._scene_validation_status = new_status

    def move_df_row(self, source_df_idx: int, target_df_idx: int) -> bool:
        if not (0 <= source_df_idx < len(self._dataframe)): return False
        qt_target_row = target_df_idx if source_df_idx > target_df_idx else target_df_idx + 1
        if not self.beginMoveRows(QModelIndex(), source_df_idx, source_df_idx, QModelIndex(), qt_target_row): return False
        try:
            temp_df_list = self._dataframe.to_dict(orient='records')
            moved_item_data = temp_df_list.pop(source_df_idx)
            temp_df_list.insert(target_df_idx, moved_item_data)
            self._dataframe = pd.DataFrame(temp_df_list, columns=self.df_column_order)
            self._dataframe = self._ensure_df_structure(self._dataframe)
            for i in range(len(self._dataframe)):
                self._validate_in_out_for_row(i)
                self._validate_scene_for_row(i)
        except Exception as e:
            self.endMoveRows()
            return False
        self.endMoveRows()
        # self._revalidate_all_lines()
        return True

    def get_next_id(self) -> int:
        if self._dataframe.empty or C.COL_ID not in self._dataframe.columns or self._dataframe[C.COL_ID].isna().all(): return 0
        numeric_ids = pd.to_numeric(self._dataframe[C.COL_ID], errors='coerce').dropna()
        return int(numeric_ids.max()) + 1 if not numeric_ids.empty else 0

    def find_df_index_by_id(self, id_value: int) -> Optional[int]:
        if C.COL_ID not in self._dataframe.columns or self._dataframe.empty: return None
        df_ids_numeric = pd.to_numeric(self._dataframe[C.COL_ID], errors='coerce')
        matches = self._dataframe.index[df_ids_numeric == id_value].tolist()
        return matches[0] if matches else None

    def get_view_column_index(self, df_column_name: str) -> Optional[int]:
        return self.df_col_to_view_col.get(df_column_name)

    def get_df_column_name(self, view_column_index: int) -> Optional[str]:
        col_identifier = self.column_map.get(view_column_index)
        if col_identifier == C.ROW_NUMBER_COL_IDENTIFIER: return None
        return col_identifier

    def _convert_tc_to_ms(self, time_code: str) -> Optional[int]:
        try:
            parts = time_code.split(':')
            if len(parts) != 4: return None
            h, m, s, f = map(int, parts)
            if not (0 <= h < 100 and 0 <= m < 60 and 0 <= s < 60 and 0 <= f < 100): return None
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / C.FPS) * 1000.0))
        except (ValueError, TypeError): return None

    def _validate_in_out_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            in_tc = str(self._dataframe.at[df_row_idx, C.COL_IN])
            out_tc = str(self._dataframe.at[df_row_idx, C.COL_OUT])
            in_ms, out_ms = self._convert_tc_to_ms(in_tc), self._convert_tc_to_ms(out_tc)
            validation_result: Union[bool, str] = True
            if in_ms is None or out_ms is None: validation_result = "Formato de tiempo inválido (HH:MM:SS:FF)."
            elif in_ms == 0 and out_ms == 0: validation_result = "Tiempos IN y OUT no pueden ser ambos cero."
            else:
                duration_ms = out_ms - in_ms
                if duration_ms < 0: validation_result = f"Error: OUT ({out_tc}) es anterior a IN ({in_tc})."
                elif duration_ms > C.MAX_INTERVENTION_DURATION_MS:
                    validation_result = f"Duración ({duration_ms / 1000.0:.1f}s) excede el máximo ({C.MAX_INTERVENTION_DURATION_MS / 1000.0:.0f}s)."
            self._time_validation_status[df_row_idx] = validation_result
        elif df_row_idx in self._time_validation_status: del self._time_validation_status[df_row_idx]

    def _validate_scene_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            scene_value = str(self._dataframe.at[df_row_idx, C.COL_SCENE]).strip()
            validation_result: Union[bool, str] = True
            if not scene_value or scene_value.lower() == "nan": validation_result = "La escena no puede estar vacía."
            else:
                try: int(scene_value)
                except ValueError: validation_result = f"La escena '{scene_value}' no es un número entero."
            self._scene_validation_status[df_row_idx] = validation_result
        elif df_row_idx in self._scene_validation_status: del self._scene_validation_status[df_row_idx]

    def force_time_validation_update_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            old_status, new_status = self._time_validation_status.get(df_row_idx, True), self._time_validation_status.get(df_row_idx, True)
            self._validate_in_out_for_row(df_row_idx)
            if old_status != new_status:
                in_view_col, out_view_col = self.get_view_column_index(C.COL_IN), self.get_view_column_index(C.COL_OUT)
                if in_view_col is not None:
                    in_idx = self.index(df_row_idx, in_view_col)
                    self.dataChanged.emit(in_idx, in_idx, [Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.ToolTipRole])
                if out_view_col is not None:
                    out_idx = self.index(df_row_idx, out_view_col)
                    self.dataChanged.emit(out_idx, out_idx, [Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.ToolTipRole])

    def force_scene_validation_update_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            old_status, new_status = self._scene_validation_status.get(df_row_idx, True), self._scene_validation_status.get(df_row_idx, True)
            self._validate_scene_for_row(df_row_idx)
            if old_status != new_status:
                scene_view_col = self.get_view_column_index(C.COL_SCENE)
                if scene_view_col is not None:
                    scene_idx = self.index(df_row_idx, scene_view_col)
                    self.dataChanged.emit(scene_idx, scene_idx, [Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.ToolTipRole])
        return None
    
    def cleanup(self):
        """Clean up thread on exit"""
        self.validation_thread.quit()
        self.validation_thread.wait()

    def revalidate_all_lines(self):
        """Triggers the debounced async validation."""
        self._validation_debounce_timer.start()

    def _trigger_async_validation(self):
        """Captures current dataframe state and starts worker."""
        if not self._dataframe.empty:
            # Pass a copy to ensure thread safety
            self.start_async_validation.emit(self._dataframe.copy())

    @pyqtSlot(dict)
    def _on_validation_finished(self, new_status: Dict[int, Dict[str, bool]]):
        """Updates the model with results from the worker."""
        old_error_indices = set(k for k, v in self._line_validation_status.items() if not v.get(C.COL_DIALOGO, True) or not v.get(C.COL_EUSKERA, True))
        
        self._line_validation_status = new_status
        
        new_error_indices = set(k for k, v in self._line_validation_status.items() if not v.get(C.COL_DIALOGO, True) or not v.get(C.COL_EUSKERA, True))
        indices_to_update = old_error_indices.symmetric_difference(new_error_indices)
        
        if indices_to_update:
            view_col_dialogo = self.get_view_column_index(C.COL_DIALOGO)
            view_col_euskera = self.get_view_column_index(C.COL_EUSKERA)
            
            # Batch updates if possible, but simplest is loop
            # Optimization: could use layoutChanged if too many, but that resets everything
            for df_idx in indices_to_update:
                if view_col_dialogo is not None:
                    idx = self.index(df_idx, view_col_dialogo)
                    if idx.isValid():
                        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.BackgroundRole])
                if view_col_euskera is not None:
                    idx = self.index(df_idx, view_col_euskera)
                    if idx.isValid():
                        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.BackgroundRole])
                
    # _check_group_for_column removed as it is now in ValidationWorker
