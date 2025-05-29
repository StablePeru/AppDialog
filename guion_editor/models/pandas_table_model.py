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
        # column_map: Mapea índice de columna de la VISTA a nombre de columna del DataFrame
        self.column_map = column_map
        self.view_column_names = view_column_names
        # df_column_order: Orden esperado de columnas en el DataFrame interno
        self.df_column_order = [column_map[i] for i in sorted(column_map.keys())]

        self._dataframe = pd.DataFrame(columns=self.df_column_order)
        self._ensure_df_structure() # Asegurar columnas y tipos iniciales

        # Mapeo inverso para búsquedas rápidas
        self.df_col_to_view_col: Dict[str, int] = {v: k for k, v in column_map.items()}

        # Almacenamiento para el estado de validación de IN/OUT, para BackgroundRole
        # Key: df_row_idx, Value: bool (True si es válido, False si no)
        self._time_validation_status: Dict[int, bool] = {}


    def _ensure_df_structure(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Asegura que el DataFrame (interno o proporcionado) tenga las columnas y tipos esperados."""
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
        
        # Reordenar columnas
        cols_in_df = [col for col in self.df_column_order if col in target_df.columns]
        other_cols = [col for col in target_df.columns if col not in self.df_column_order]
        return target_df[cols_in_df + other_cols]

    def dataframe(self) -> pd.DataFrame:
        return self._dataframe

    def set_dataframe(self, dataframe: pd.DataFrame):
        self.beginResetModel()
        if dataframe is not None:
            self._dataframe = self._ensure_df_structure(dataframe.copy())
        else:
            self._dataframe = pd.DataFrame(columns=self.df_column_order)
            self._dataframe = self._ensure_df_structure(self._dataframe)
        
        self._time_validation_status.clear() # Resetear estado de validación
        for i in range(len(self._dataframe)): # Validar todas las filas nuevas
            self._validate_in_out_for_row(i)

        self.endResetModel()
        self.layoutChangedSignal.emit() # Informar a TableWindow para ajustes de UI

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

        df_actual_col_idx = self._dataframe.columns.get_loc(df_col_name)
        value = self._dataframe.iat[df_row_idx, df_actual_col_idx]
        
        if pd.isna(value):
            value = ""

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return str(value)
        
        if role == Qt.ItemDataRole.BackgroundRole:
            if df_col_name in ["IN", "OUT"]:
                is_valid = self._time_validation_status.get(df_row_idx, True) # Default a True si no está
                return QBrush(VALID_TIME_BG_COLOR if is_valid else INVALID_TIME_BG_COLOR)
        
        # if role == Qt.ItemDataRole.SizeHintRole and df_col_name == 'DIÁLOGO':
        #     # Esto sería para ajustar la altura de la fila basada en el contenido del diálogo
        #     # Necesitaría QFontMetrics. No es trivial de implementar aquí sin acceso a la vista/fuente.
        #     # Es mejor que la vista use table_view.resizeRowToContents(row)
        #     pass

        return None

    def setData(self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        df_row_idx = index.row()
        view_col_idx = index.column()
        df_col_name = self.column_map.get(view_col_idx)

        if df_col_name is None or df_row_idx >= len(self._dataframe) or df_col_name not in self._dataframe.columns:
            return False

        df_actual_col_idx = self._dataframe.columns.get_loc(df_col_name)
        # old_value = self._dataframe.iat[df_row_idx, df_actual_col_idx] # QUndoCommand se encarga del old_value

        try:
            str_value = str(value)
            if df_col_name == 'ID':
                # El ID no debería ser editable a través de setData directamente por el usuario.
                # Se asigna al crear filas. Si se permite, debe ser con cuidado.
                # Por ahora, asumimos que no se edita así. Si se necesitara:
                # new_typed_value = pd.NA if not str_value else int(str_value)
                return False # No permitir edición de ID por aquí
            elif df_col_name == 'SCENE':
                new_typed_value = str_value.strip()
                if new_typed_value: # Validar si es un número
                    int(new_typed_value)
            elif df_col_name in ['IN', 'OUT']:
                # Validar formato HH:MM:SS:FF (4 partes, 2 dígitos cada una)
                parts = str_value.split(':')
                if len(parts) == 4 and all(len(p) == 2 and p.isdigit() for p in parts):
                    new_typed_value = str_value
                else: # Formato inválido, no cambiar o revertir
                    # print(f"Formato de tiempo inválido: {str_value} para {df_col_name}")
                    return False 
            else: # PERSONAJE, DIÁLOGO
                new_typed_value = str_value
        except ValueError:
            # print(f"Error de conversión de valor '{value}' para columna '{df_col_name}'.")
            return False # Indica fallo

        self._dataframe.iat[df_row_idx, df_actual_col_idx] = new_typed_value
        
        # Roles afectados: DisplayRole y EditRole son los principales.
        # BackgroundRole podría cambiar si IN/OUT se modifica.
        roles_changed = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
        if df_col_name in ['IN', 'OUT']:
            self._validate_in_out_for_row(df_row_idx)
            roles_changed.append(Qt.ItemDataRole.BackgroundRole)
            # Necesitamos notificar el cambio de fondo para ambas celdas IN y OUT
            in_view_col = self.get_view_column_index('IN')
            out_view_col = self.get_view_column_index('OUT')
            if in_view_col is not None:
                in_idx = self.index(df_row_idx, in_view_col)
                self.dataChanged.emit(in_idx, in_idx, [Qt.ItemDataRole.BackgroundRole])
            if out_view_col is not None:
                out_idx = self.index(df_row_idx, out_view_col)
                self.dataChanged.emit(out_idx, out_idx, [Qt.ItemDataRole.BackgroundRole])


        self.dataChanged.emit(index, index, roles_changed)
        # La señal data_changed_for_undo es redundante si QUndoCommand llama a setData
        # self.data_changed_for_undo.emit(df_row_idx, view_col_idx, old_value, new_typed_value)
        return True

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if 0 <= section < len(self.view_column_names):
                    return self.view_column_names[section]
            # if orientation == Qt.Orientation.Vertical: return str(section + 1) # Números de fila
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        df_col_name = self.column_map.get(index.column())
        if df_col_name == 'ID': # ID no editable
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def insert_row_data(self, df_row_idx_to_insert_at: int, row_data_dict: Dict[str, Any]) -> bool:
        self.beginInsertRows(QModelIndex(), df_row_idx_to_insert_at, df_row_idx_to_insert_at)
        
        # Crear una serie con el orden de columnas del modelo
        new_row_series = pd.Series(index=self.df_column_order, dtype=object)
        for col_name, value in row_data_dict.items():
            if col_name in self.df_column_order:
                if col_name == 'ID' and pd.notna(value):
                    new_row_series[col_name] = int(value)
                elif col_name == 'SCENE':
                    new_row_series[col_name] = str(value)
                else:
                    new_row_series[col_name] = value
        
        # Asegurar que todas las columnas esperadas tengan un valor (aunque sea default)
        for col_name in self.df_column_order:
            if col_name not in new_row_series or pd.isna(new_row_series[col_name]):
                if col_name == 'ID': new_row_series[col_name] = pd.NA # Será Int64
                elif col_name in ['IN', 'OUT']: new_row_series[col_name] = "00:00:00:00"
                elif col_name == 'SCENE': new_row_series[col_name] = "1"
                else: new_row_series[col_name] = ""


        if df_row_idx_to_insert_at >= len(self._dataframe):
            self._dataframe = pd.concat([self._dataframe, pd.DataFrame([new_row_series])], ignore_index=True)
        else:
            df_part1 = self._dataframe.iloc[:df_row_idx_to_insert_at]
            df_part2 = self._dataframe.iloc[df_row_idx_to_insert_at:]
            self._dataframe = pd.concat([df_part1, pd.DataFrame([new_row_series]), df_part2], ignore_index=True)
        
        self._dataframe = self._ensure_df_structure(self._dataframe) # Re-asegurar tipos
        self._validate_in_out_for_row(df_row_idx_to_insert_at) # Validar la nueva fila
        
        self.endInsertRows()
        return True

    def remove_row_by_df_index(self, df_row_idx: int) -> Optional[pd.Series]:
        if 0 <= df_row_idx < len(self._dataframe):
            self.beginRemoveRows(QModelIndex(), df_row_idx, df_row_idx)
            removed_row_data = self._dataframe.iloc[df_row_idx].copy()
            self._dataframe.drop(index=df_row_idx, inplace=True)
            self._dataframe.reset_index(drop=True, inplace=True)
            # Reconstruir el _time_validation_status o shiftearlo
            self._rebuild_time_validation_after_remove(df_row_idx)
            self.endRemoveRows()
            return removed_row_data
        return None

    def move_df_row(self, source_df_idx: int, target_df_idx: int) -> bool:
        if not (0 <= source_df_idx < len(self._dataframe)): return False
        # target_df_idx es donde se insertará en la lista *después* de quitar el elemento fuente.
        # Qt espera el índice destino *antes* del cual se insertará el elemento movido.
        # Si movemos 0 a 2 (en [a,b,c]): pop a -> [b,c]. insertar a en pos 2 (nuevo) -> [b,c,a]. Qt dest = 3.
        # Si movemos 2 a 0 (en [a,b,c]): pop c -> [a,b]. insertar c en pos 0 (nuevo) -> [c,a,b]. Qt dest = 0.

        qt_target_row = target_df_idx
        if source_df_idx < target_df_idx: # Moviendo hacia abajo
             qt_target_row = target_df_idx + 1 # El elemento se insertará antes de esta posición
        # Si se mueve hacia arriba, target_df_idx es correcto para Qt.

        if not self.beginMoveRows(QModelIndex(), source_df_idx, source_df_idx, QModelIndex(), qt_target_row):
             # print("beginMoveRows falló")
             return False
        try:
            # Operación en el DataFrame
            row_to_move_data = self._dataframe.iloc[source_df_idx].to_dict()
            
            temp_df_list = self._dataframe.to_dict(orient='records')
            moved_item = temp_df_list.pop(source_df_idx)
            temp_df_list.insert(target_df_idx, moved_item)
            self._dataframe = pd.DataFrame(temp_df_list, columns=self.df_column_order)
            self._dataframe = self._ensure_df_structure(self._dataframe)

            # Actualizar validación de tiempo para las filas afectadas
            self._rebuild_time_validation_after_move(source_df_idx, target_df_idx)

        except Exception as e:
            # print(f"Error durante el movimiento de fila en DataFrame: {e}")
            self.endMoveRows()
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
        # Asegurar que la columna ID sea numérica para la comparación
        df_ids_numeric = pd.to_numeric(self._dataframe['ID'], errors='coerce')
        matches = self._dataframe.index[df_ids_numeric == id_value].tolist()
        return matches[0] if matches else None

    def get_view_column_index(self, df_column_name: str) -> Optional[int]:
        return self.df_col_to_view_col.get(df_column_name)

    def get_df_column_name(self, view_column_index: int) -> Optional[str]:
        return self.column_map.get(view_column_index)

    # --- Métodos de validación de tiempo ---
    def _convert_tc_to_ms(self, time_code: str) -> Optional[int]:
        try:
            parts = time_code.split(':')
            if len(parts) != 4: return None
            h, m, s, f = map(int, parts)
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / 25.0) * 1000.0))
        except:
            return None

    def _validate_in_out_for_row(self, df_row_idx: int):
        if 0 <= df_row_idx < len(self._dataframe):
            in_tc = str(self._dataframe.at[df_row_idx, 'IN'])
            out_tc = str(self._dataframe.at[df_row_idx, 'OUT'])
            
            in_ms = self._convert_tc_to_ms(in_tc)
            out_ms = self._convert_tc_to_ms(out_tc)

            if in_ms is not None and out_ms is not None:
                self._time_validation_status[df_row_idx] = (out_ms >= in_ms)
            else: # Formato inválido, marcar como inválido
                self._time_validation_status[df_row_idx] = False
        else:
             if df_row_idx in self._time_validation_status:
                 del self._time_validation_status[df_row_idx]


    def _rebuild_time_validation_after_remove(self, removed_df_idx: int):
        new_status = {}
        for old_idx, is_valid in self._time_validation_status.items():
            if old_idx < removed_df_idx:
                new_status[old_idx] = is_valid
            elif old_idx > removed_df_idx:
                new_status[old_idx - 1] = is_valid
        self._time_validation_status = new_status

    def _rebuild_time_validation_after_move(self, source_idx: int, target_idx: int):
        # Esto es simplista, una reconstrucción completa es más segura si hay muchos movimientos
        # Por ahora, solo validamos las filas alrededor de las posiciones de origen y destino
        # y la fila movida.
        self._time_validation_status.clear() # Forzar revalidación completa
        for i in range(len(self._dataframe)):
            self._validate_in_out_for_row(i)

        # Más preciso sería shiftearlo como con remove, pero es más complejo
        # moved_status = self._time_validation_status.pop(source_idx, True)
        # temp_status_list = []
        # for i in range(len(self._dataframe) + 1): # +1 porque el item fue "removido" temporalmente
        #     if i == source_idx: continue
        #     temp_status_list.append(self._time_validation_status.get(i, True))
        # temp_status_list.insert(target_idx, moved_status)
        # self._time_validation_status = {i:s for i,s in enumerate(temp_status_list)}

    def force_time_validation_update_for_row(self, df_row_idx: int):
        """Llamado desde TableWindow si necesita forzar una revalidación y repintado."""
        if 0 <= df_row_idx < len(self._dataframe):
            self._validate_in_out_for_row(df_row_idx)
            in_view_col = self.get_view_column_index('IN')
            out_view_col = self.get_view_column_index('OUT')
            if in_view_col is not None:
                in_idx = self.index(df_row_idx, in_view_col)
                self.dataChanged.emit(in_idx, in_idx, [Qt.ItemDataRole.BackgroundRole])
            if out_view_col is not None:
                out_idx = self.index(df_row_idx, out_view_col)
                self.dataChanged.emit(out_idx, out_idx, [Qt.ItemDataRole.BackgroundRole])