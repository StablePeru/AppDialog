# guion_editor/utils/guion_manager.py
import pandas as pd
import json
import os
from typing import Tuple, Dict, List, Any
from openpyxl.styles import PatternFill

from .dialog_utils import leer_guion

class GuionManager:
    BASE_COLUMNS = ['IN', 'OUT', 'PERSONAJE', 'DIÁLOGO']
    ALL_COLUMNS = ['ID', 'SCENE', 'IN', 'OUT', 'PERSONAJE', 'DIÁLOGO', 'EUSKERA', 'OHARRAK']

    def __init__(self):
        pass

    # -> MODIFICADO: Este método ahora solo procesa un DataFrame que ya se supone correcto
    def process_dataframe(self, df: pd.DataFrame, file_source: str = "unknown") -> Tuple[pd.DataFrame, bool]:
        # El nombre original era _verify_and_prepare_df
        # ... (el contenido de este método es EXACTAMENTE el mismo que el de tu _verify_and_prepare_df)
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
            df['SCENE'] = df['SCENE'].str.strip()
            df['SCENE'].replace(['', 'nan', 'none', 'NaN', 'None'], pd.NA, inplace=True)
            df['SCENE'].ffill(inplace=True)
            df['SCENE'].fillna("1", inplace=True)

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

        ordered_present_columns = [col for col in self.ALL_COLUMNS if col in df.columns]
        extra_cols = [col for col in df.columns if col not in self.ALL_COLUMNS]
        df = df[ordered_present_columns + extra_cols]

        return df, has_scene_numbers

    # -> NUEVO: Este método solo lee y comprueba las columnas
    def check_excel_columns(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
        """
        Lee un archivo Excel y comprueba si sus columnas coinciden con el formato esperado.
        Devuelve el DataFrame crudo, los datos de cabecera y un booleano 'needs_mapping'.
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
                    pass
            
            # Comprobación estricta: ¿están TODAS las columnas requeridas (excepto ID) presentes?
            # 'ID' no es estrictamente necesario en el Excel, ya que lo podemos generar.
            expected_cols_in_excel = [col for col in self.ALL_COLUMNS if col != 'ID']
            needs_mapping = not all(col in df.columns for col in expected_cols_in_excel)
            
            return df, header_data, needs_mapping
        except Exception as e:
            raise

    # -> RENOMBRADO: El antiguo `load_from_excel` se renombra para evitar confusión, aunque no se use directamente.
    def old_load_from_excel_renamed(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
        # Este es el código de tu antiguo `load_from_excel`
        try:
            xls = pd.ExcelFile(path)
            df = pd.read_excel(xls, sheet_name=0)

            header_data = {}
            if 'Header' in xls.sheet_names:
                # ... (código de lectura de cabecera)
                pass
            
            df_processed, has_scenes = self.process_dataframe(df, file_source=path)
            return df_processed, header_data, has_scenes
        except Exception as e:
            raise

    # ... (resto de la clase sin cambios)
    def save_to_excel(self, path: str, dataframe: pd.DataFrame, header_data: Dict[str, Any]) -> None:
        try:
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                df_to_save = dataframe.copy()
                def replace_if_empty(value):
                    if pd.isna(value) or str(value).strip() == '':
                        return ""
                    return value
                for col in ['DIÁLOGO', 'EUSKERA', 'OHARRAK']:
                    if col in df_to_save.columns:
                        df_to_save[col] = df_to_save[col].apply(replace_if_empty)
                df_to_save.to_excel(writer, sheet_name='Guion', index=False)
                if 'OHARRAK' in df_to_save.columns:
                    workbook = writer.book
                    worksheet = writer.sheets['Guion']
                    highlight_fill = PatternFill(start_color="FFFFFF00", end_color="FFFFFF00", fill_type="solid")
                    for df_index, row in df_to_save.iterrows():
                        oharrak_content = row['OHARRAK']
                        if pd.notna(oharrak_content) and str(oharrak_content).strip() != '':
                            excel_row_index = df_index + 2
                            for col_idx in range(1, len(df_to_save.columns) + 1):
                                worksheet.cell(row=excel_row_index, column=col_idx).fill = highlight_fill
                if header_data:
                    header_df = pd.DataFrame(list(header_data.items()), columns=['Campo', 'Valor'])
                    header_df.to_excel(writer, sheet_name='Header', index=False)
        except Exception as e:
            raise

    def load_from_json(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            header_data = json_data.get("header", {})
            script_data = json_data.get("data", [])
            df = pd.DataFrame(script_data)
            df_processed, has_scenes = self.process_dataframe(df, file_source=path)
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
            df_processed, _ = self.process_dataframe(df, file_source=path)
            return df_processed, header_data, False 
        except Exception as e:
            raise