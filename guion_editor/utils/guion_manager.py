# guion_editor/utils/guion_manager.py
import pandas as pd
import json
import os
from typing import Tuple, Dict, List, Any
from openpyxl.styles import PatternFill # -> AÑADIDO

from .dialog_utils import leer_guion

class GuionManager:
    BASE_COLUMNS = ['IN', 'OUT', 'PERSONAJE', 'DIÁLOGO']
    # -> INICIO: LISTA DE COLUMNAS ACTUALIZADA
    ALL_COLUMNS = ['ID', 'SCENE', 'IN', 'OUT', 'PERSONAJE', 'DIÁLOGO', 'EUSKERA', 'OHARRAK']
    # -> FIN

    def __init__(self):
        pass

    def _verify_and_prepare_df(self, df: pd.DataFrame, file_source: str = "unknown") -> Tuple[pd.DataFrame, bool]:
        missing_cols = [col for col in self.BASE_COLUMNS if col not in df.columns]
        if missing_cols:
            pass 

        if 'ID' not in df.columns:
            if not df.empty:
                df.insert(0, 'ID', range(len(df)))
            else:
                df['ID'] = pd.Series(dtype='int')

        has_scene_numbers = False
        if 'SCENE' not in df.columns:
            insert_idx_for_scene = 0
            if 'ID' in df.columns:
                try:
                    insert_idx_for_scene = df.columns.get_loc('ID') + 1
                except KeyError: 
                    pass 
            
            df.insert(insert_idx_for_scene, 'SCENE', "1")
            has_scene_numbers = False
        else:
            df['SCENE'] = df['SCENE'].astype(str)

            # --- MODIFICACIÓN: Propagar el número de escena a filas vacías ---
            # Reemplazar strings vacíos y varios tipos de 'nan' con pd.NA para que ffill funcione
            df['SCENE'] = df['SCENE'].str.strip()
            df['SCENE'].replace(['', 'nan', 'none', 'NaN', 'None'], pd.NA, inplace=True)
            df['SCENE'].ffill(inplace=True) # Rellenar hacia adelante (forward fill)
            df['SCENE'].fillna("1", inplace=True) # Rellenar los que queden (el/los primero/s) con "1"
            # --- FIN DE LA MODIFICACIÓN ---

            def normalize_scene_value(scene_str: str) -> str:
                scene_str_stripped = scene_str.strip()
                if scene_str_stripped.endswith(".0"):
                    potential_int_part = scene_str_stripped[:-2]
                    try:
                        val_int = int(potential_int_part)
                        val_float_original = float(scene_str_stripped)
                        if val_int == val_float_original:
                            return potential_int_part
                    except ValueError:
                        pass
                return scene_str_stripped
            
            df['SCENE'] = df['SCENE'].apply(normalize_scene_value)

            non_empty_scenes = [s for s in df['SCENE'].tolist() if s.strip() and s.strip().lower() != 'nan']
            
            if not non_empty_scenes: 
                df['SCENE'] = "1" 
                has_scene_numbers = False
            else:
                unique_meaningful_scenes = set(non_empty_scenes)
                if len(unique_meaningful_scenes) > 1:
                    has_scene_numbers = True
                elif len(unique_meaningful_scenes) == 1:
                    single_scene_val = list(unique_meaningful_scenes)[0]
                    if single_scene_val == "1":
                        df['SCENE'] = "1"
                        has_scene_numbers = False
                    else:
                        has_scene_numbers = True 
                else:
                    df['SCENE'] = "1"
                    has_scene_numbers = False
        
        # -> INICIO: ASEGURARSE DE QUE 'OHARRAK' EXISTA
        if 'EUSKERA' not in df.columns:
            insert_pos = -1
            if 'DIÁLOGO' in df.columns:
                insert_pos = df.columns.get_loc('DIÁLOGO') + 1
            
            if insert_pos != -1 and insert_pos <= len(df.columns):
                df.insert(insert_pos, 'EUSKERA', "")
            else: 
                df['EUSKERA'] = ""

        if 'OHARRAK' not in df.columns:
            insert_pos_oh = -1
            if 'EUSKERA' in df.columns:
                insert_pos_oh = df.columns.get_loc('EUSKERA') + 1
            
            if insert_pos_oh != -1 and insert_pos_oh <= len(df.columns):
                df.insert(insert_pos_oh, 'OHARRAK', "")
            else:
                df['OHARRAK'] = ""
        # -> FIN

        ordered_present_columns = [col for col in self.ALL_COLUMNS if col in df.columns]
        extra_cols = [col for col in df.columns if col not in self.ALL_COLUMNS]
        df = df[ordered_present_columns + extra_cols]

        return df, has_scene_numbers

    def load_from_excel(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
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
                    pass
            
            df_processed, has_scenes = self._verify_and_prepare_df(df, file_source=path)
            return df_processed, header_data, has_scenes
        except Exception as e:
            raise

    # -> INICIO: MÉTODO `save_to_excel` MODIFICADO
    def save_to_excel(self, path: str, dataframe: pd.DataFrame, header_data: Dict[str, Any]) -> None:
        try:
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                df_to_save = dataframe.copy()

                # Reemplazar valores vacíos para que no se guarden como "nan" literales en Excel
                def replace_if_empty(value):
                    if pd.isna(value) or str(value).strip() == '':
                        return "" # Guardar como celda vacía real
                    return value

                for col in ['DIÁLOGO', 'EUSKERA', 'OHARRAK']:
                    if col in df_to_save.columns:
                        df_to_save[col] = df_to_save[col].apply(replace_if_empty)
                
                df_to_save.to_excel(writer, sheet_name='Guion', index=False)

                # --- LÓGICA DE RESALTADO ---
                if 'OHARRAK' in df_to_save.columns:
                    workbook = writer.book
                    worksheet = writer.sheets['Guion']
                    
                    # Define el estilo de relleno (amarillo claro)
                    highlight_fill = PatternFill(start_color="FFFFFF00", end_color="FFFFFF00", fill_type="solid")

                    # Itera sobre el DataFrame para encontrar filas con notas
                    for df_index, row in df_to_save.iterrows():
                        oharrak_content = row['OHARRAK']
                        if pd.notna(oharrak_content) and str(oharrak_content).strip() != '':
                            # El índice de la fila en Excel es el índice del DataFrame + 2
                            # (+1 porque Excel es 1-based, +1 para saltar la cabecera)
                            excel_row_index = df_index + 2
                            
                            # Aplica el relleno a todas las celdas de esa fila
                            for col_idx in range(1, len(df_to_save.columns) + 1):
                                worksheet.cell(row=excel_row_index, column=col_idx).fill = highlight_fill
                # --- FIN DE LÓGICA DE RESALTADO ---

                if header_data:
                    header_df = pd.DataFrame(list(header_data.items()), columns=['Campo', 'Valor'])
                    header_df.to_excel(writer, sheet_name='Header', index=False)
        except Exception as e:
            raise
    # -> FIN

    def load_from_json(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
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
        try:
            df_to_save = dataframe.copy()
            data_records = df_to_save.to_dict(orient='records')
            json_output = {"header": header_data, "data": data_records}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, ensure_ascii=False, indent=4)
        except Exception as e:
            raise

    def load_from_docx(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
        try:
            guion_list_of_dicts = leer_guion(path)
            if not guion_list_of_dicts:
                 df = pd.DataFrame(columns=self.BASE_COLUMNS)
            else:
                df = pd.DataFrame(guion_list_of_dicts)

            header_data = {}
            df_processed, _ = self._verify_and_prepare_df(df, file_source=path)
            return df_processed, header_data, False 
        except Exception as e:
            raise