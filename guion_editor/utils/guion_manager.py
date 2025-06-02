import pandas as pd
import json
import os
from typing import Tuple, Dict, List, Any

from .dialog_utils import leer_guion

class GuionManager:
    BASE_COLUMNS = ['IN', 'OUT', 'PERSONAJE', 'DIÁLOGO']
    # AÑADIR 'EUSKERA' a ALL_COLUMNS
    ALL_COLUMNS = ['ID', 'SCENE', 'IN', 'OUT', 'PERSONAJE', 'DIÁLOGO', 'EUSKERA']

    def __init__(self):
        pass

    def _verify_and_prepare_df(self, df: pd.DataFrame, file_source: str = "unknown") -> Tuple[pd.DataFrame, bool]:
        missing_cols = [col for col in self.BASE_COLUMNS if col not in df.columns]
        if missing_cols:
            # No lanzaremos error si falta 'EUSKERA' en la carga, se añadirá si es necesario.
            # El error solo es para las columnas base.
            pass # Opcionalmente, loguear una advertencia si faltan columnas no base pero esperadas.

        if 'ID' not in df.columns:
            if not df.empty:
                df.insert(0, 'ID', range(len(df)))
            else:
                df['ID'] = pd.Series(dtype='int')

        has_scene_numbers = False
        if 'SCENE' not in df.columns:
            df.insert(df.columns.get_loc('IN'), 'SCENE', "1") # Asume posición relativa a 'IN'
            has_scene_numbers = False
        else:
            df['SCENE'] = df['SCENE'].astype(str)
            unique_scenes = set(df['SCENE'].tolist())
            if len(unique_scenes) > 1 or (len(unique_scenes) == 1 and "1" not in unique_scenes):
                has_scene_numbers = True
            else:
                df['SCENE'] = "1"
                has_scene_numbers = False
        
        # Añadir EUSKERA si no existe, PandasTableModel también lo hará si está en su df_column_order
        if 'EUSKERA' not in df.columns:
            # Insertar después de DIÁLOGO si DIÁLOGO existe, sino al final de las columnas base
            insert_pos = -1
            if 'DIÁLOGO' in df.columns:
                insert_pos = df.columns.get_loc('DIÁLOGO') + 1
            elif self.BASE_COLUMNS[-1] in df.columns: # Si DIÁLOGO no está pero la última de BASE_COLUMNS sí
                 insert_pos = df.columns.get_loc(self.BASE_COLUMNS[-1]) + 1
            
            if insert_pos != -1 and insert_pos <= len(df.columns):
                df.insert(insert_pos, 'EUSKERA', "")
            else: # Fallback, añadir al final
                df['EUSKERA'] = ""


        ordered_present_columns = [col for col in self.ALL_COLUMNS if col in df.columns]
        extra_cols = [col for col in df.columns if col not in self.ALL_COLUMNS]
        df = df[ordered_present_columns + extra_cols]

        return df, has_scene_numbers

    def load_from_excel(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
        """
        Carga datos desde un archivo Excel.
        Intenta cargar metadatos de una hoja 'Header' si existe.
        Retorna DataFrame, header_data, has_scene_numbers.
        """
        try:
            xls = pd.ExcelFile(path)
            df = pd.read_excel(xls, sheet_name=0)

            header_data = {}
            if 'Header' in xls.sheet_names:
                try:
                    header_df = pd.read_excel(xls, sheet_name='Header', header=None, index_col=0)
                    if not header_df.empty:
                         header_data = header_df[1].to_dict()
                         for key in ["reference_number", "chapter_number"]:
                             if key in header_data and pd.notna(header_data[key]):
                                 header_data[key] = str(int(header_data[key])) if isinstance(header_data[key], (int, float)) else str(header_data[key])
                except Exception:
                    # Silently ignore if header cannot be loaded
                    pass
            
            df_processed, has_scenes = self._verify_and_prepare_df(df, file_source=path)
            return df_processed, header_data, has_scenes
        except Exception as e:
            # Consider re-raising a more specific exception or handling it
            raise

    def save_to_excel(self, path: str, dataframe: pd.DataFrame, header_data: Dict[str, Any]) -> None:
        """
        Guarda el DataFrame y los datos de cabecera en un archivo Excel.
        Los datos de cabecera se guardan en una hoja separada llamada 'Header'.
        """
        try:
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                df_to_save = dataframe.copy()
                # Consider if 'ID' column should be dropped before saving to Excel
                # if 'ID' in df_to_save.columns:
                #     df_to_save = df_to_save.drop(columns=['ID'])
                df_to_save.to_excel(writer, sheet_name='Guion', index=False)

                if header_data:
                    header_df = pd.DataFrame(list(header_data.items()), columns=['Campo', 'Valor'])
                    header_df.to_excel(writer, sheet_name='Header', index=False)
        except Exception as e:
            raise

    def load_from_json(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
        """
        Carga datos desde un archivo JSON.
        Espera un JSON con una clave "header" para metadatos y "data" para el guion.
        Retorna DataFrame, header_data, has_scene_numbers.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            header_data = json_data.get("header", {})
            script_data = json_data.get("data", [])
            df = pd.DataFrame(script_data)

            df_processed, has_scenes = self._verify_and_prepare_df(df, file_source=path)
            return df_processed, header_data, has_scenes
        except Exception as e:
            raise

    def save_to_json(self, path: str, dataframe: pd.DataFrame, header_data: Dict[str, Any]) -> None:
        """
        Guarda el DataFrame y los datos de cabecera en un archivo JSON.
        """
        try:
            df_to_save = dataframe.copy()
            # Consider if 'ID' column should be dropped
            # if 'ID' in df_to_save.columns:
            #     df_to_save = df_to_save.drop(columns=['ID'])
            
            data_records = df_to_save.to_dict(orient='records')
            
            json_output = {"header": header_data, "data": data_records}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, ensure_ascii=False, indent=4)
        except Exception as e:
            raise

    def load_from_docx(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
        """
        Carga datos desde un archivo DOCX usando la función `leer_guion`.
        El header_data estará vacío por defecto para DOCX.
        Retorna DataFrame, header_data (vacío), has_scene_numbers (siempre False para DOCX).
        """
        try:
            guion_list_of_dicts = leer_guion(path)
            if not guion_list_of_dicts:
                 df = pd.DataFrame(columns=self.BASE_COLUMNS)
            else:
                df = pd.DataFrame(guion_list_of_dicts)

            header_data = {}
            df_processed, _ = self._verify_and_prepare_df(df, file_source=path)
            return df_processed, header_data, False # Forzar has_scenes a False
        except Exception as e:
            raise