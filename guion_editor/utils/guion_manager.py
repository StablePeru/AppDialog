# guion_editor/utils/guion_manager.py

import pandas as pd
import json
import os # Para os.path.basename en algunos casos si es necesario
import logging
from typing import Tuple, Dict, List, Any

# Suponiendo que dialog_utils está en el mismo nivel o accesible
from .dialog_utils import leer_guion # REFAC: Importar leer_guion

logger = logging.getLogger(__name__)

class GuionManager:
    # REFAC: Columnas que GuionManager espera y maneja
    # 'ID' y 'SCENE' se añadirán si no existen en la carga.
    BASE_COLUMNS = ['IN', 'OUT', 'PERSONAJE', 'DIÁLOGO']
    ALL_COLUMNS = ['ID', 'SCENE', 'IN', 'OUT', 'PERSONAJE', 'DIÁLOGO']


    def __init__(self):
        # REFAC: GuionManager ya no mantiene un estado interno de dataframe/header
        # Actúa como un servicio para cargar/guardar.
        pass

    def _verify_and_prepare_df(self, df: pd.DataFrame, file_source: str = "unknown") -> Tuple[pd.DataFrame, bool]:
        """
        Verifica columnas requeridas, añade ID y SCENE si faltan,
        y procesa datos de escena.
        Retorna el DataFrame procesado y has_scene_numbers.
        """
        # Verificar columnas base
        missing_cols = [col for col in self.BASE_COLUMNS if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Faltan columnas requeridas en los datos de '{file_source}': {', '.join(missing_cols)}")

        # Añadir columna ID si no existe (crucial para la edición en TableWindow)
        if 'ID' not in df.columns:
            if not df.empty:
                df.insert(0, 'ID', range(len(df)))
            else:
                df['ID'] = pd.Series(dtype='int') # Para df vacío

        # Procesar columna SCENE
        has_scene_numbers = False
        if 'SCENE' not in df.columns:
            df.insert(df.columns.get_loc('IN'), 'SCENE', "1") # Insertar antes de IN
            logger.info(f"Fuente '{file_source}': Columna 'SCENE' no encontrada. Añadiendo con valor '1'.")
            has_scene_numbers = False
        else:
            # Asegurar que SCENE sea string para consistencia, ya que DOCX no la tiene
            # y la tabla puede tenerla como string.
            df['SCENE'] = df['SCENE'].astype(str)
            unique_scenes = set(df['SCENE'].tolist())
            # Se considera que tiene números de escena si hay más de un valor o si el único valor no es "1"
            if len(unique_scenes) > 1 or (len(unique_scenes) == 1 and "1" not in unique_scenes):
                logger.info(f"Fuente '{file_source}': Números de escena detectados.")
                has_scene_numbers = True
            else:
                logger.info(f"Fuente '{file_source}': Solo escena '1' detectada o columna de escenas vacía/implícita. Tratando como sin números de escena específicos.")
                df['SCENE'] = "1" # Estandarizar a "1" si solo hay "1" o está vacía
                has_scene_numbers = False
        
        # Reordenar columnas para asegurar consistencia
        # Crear una lista de columnas presentes en el df en el orden deseado
        ordered_present_columns = [col for col in self.ALL_COLUMNS if col in df.columns]
        # Añadir cualquier otra columna que pudiera existir al final
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
            df = pd.read_excel(xls, sheet_name=0) # Asume que los datos están en la primera hoja

            header_data = {}
            if 'Header' in xls.sheet_names:
                try:
                    header_df = pd.read_excel(xls, sheet_name='Header', header=None, index_col=0)
                    if not header_df.empty:
                         header_data = header_df[1].to_dict() # Asume formato Clave-Valor
                         # Convertir números de referencia/capítulo a string si son numéricos
                         for key in ["reference_number", "chapter_number"]:
                             if key in header_data and pd.notna(header_data[key]):
                                 header_data[key] = str(int(header_data[key])) if isinstance(header_data[key], (int, float)) else str(header_data[key])

                except Exception as e:
                    logger.warning(f"No se pudo cargar la hoja 'Header' de {path}: {e}")
            
            df_processed, has_scenes = self._verify_and_prepare_df(df, file_source=path)
            return df_processed, header_data, has_scenes
        except Exception as e:
            logger.error(f"Error al cargar Excel desde {path}: {e}")
            raise

    def save_to_excel(self, path: str, dataframe: pd.DataFrame, header_data: Dict[str, Any]) -> None:
        """
        Guarda el DataFrame y los datos de cabecera en un archivo Excel.
        Los datos de cabecera se guardan en una hoja separada llamada 'Header'.
        """
        try:
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                # Guardar el DataFrame principal (sin el índice de Pandas)
                df_to_save = dataframe.copy()
                if 'ID' in df_to_save.columns: # No es estrictamente necesario guardar el ID en Excel
                    # df_to_save = df_to_save.drop(columns=['ID'])
                    pass # Decidimos conservarlo por ahora, como estaba antes
                df_to_save.to_excel(writer, sheet_name='Guion', index=False)

                # Guardar datos de cabecera si existen
                if header_data:
                    header_df = pd.DataFrame(list(header_data.items()), columns=['Campo', 'Valor'])
                    header_df.to_excel(writer, sheet_name='Header', index=False)
            logger.info(f"Datos guardados en Excel: {path}")
        except Exception as e:
            logger.error(f"Error al guardar Excel en {path}: {e}")
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
            logger.error(f"Error al cargar JSON desde {path}: {e}")
            raise

    def save_to_json(self, path: str, dataframe: pd.DataFrame, header_data: Dict[str, Any]) -> None:
        """
        Guarda el DataFrame y los datos de cabecera en un archivo JSON.
        """
        try:
            # Convertir DataFrame a lista de diccionarios
            df_to_save = dataframe.copy()
            # if 'ID' in df_to_save.columns: # ID es interno, no siempre necesario en JSON de salida
                # df_to_save = df_to_save.drop(columns=['ID'])
                # pass # Conservamos ID
            
            data_records = df_to_save.to_dict(orient='records')
            
            json_output = {"header": header_data, "data": data_records}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, ensure_ascii=False, indent=4)
            logger.info(f"Datos guardados en JSON: {path}")
        except Exception as e:
            logger.error(f"Error al guardar JSON en {path}: {e}")
            raise

    def load_from_docx(self, path: str) -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
        """
        Carga datos desde un archivo DOCX usando la función `leer_guion`.
        El header_data estará vacío por defecto para DOCX.
        Retorna DataFrame, header_data (vacío), has_scene_numbers (siempre False para DOCX).
        """
        try:
            # leer_guion devuelve una lista de diccionarios con IN, OUT, PERSONAJE, DIÁLOGO
            guion_list_of_dicts = leer_guion(path)
            if not guion_list_of_dicts: # Si el DOCX está vacío o no se pudo parsear
                 df = pd.DataFrame(columns=self.BASE_COLUMNS) # Crear DF vacío con columnas esperadas
            else:
                df = pd.DataFrame(guion_list_of_dicts)

            # DOCX no tiene metadatos de cabecera estructurados ni números de escena
            header_data = {}
            
            # _verify_and_prepare_df añadirá ID y SCENE (con "1")
            df_processed, has_scenes = self._verify_and_prepare_df(df, file_source=path)
            # Para DOCX, has_scenes siempre será False por defecto tras _verify_and_prepare_df
            # porque o bien no había columna SCENE, o solo contenía "1".
            return df_processed, header_data, False # Forzar has_scenes a False
        except Exception as e:
            logger.error(f"Error al cargar DOCX desde {path}: {e}")
            raise