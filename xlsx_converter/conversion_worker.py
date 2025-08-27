# conversion_worker.py

import os
import traceback
import pandas as pd
import unicodedata

from PySide6.QtCore import QObject, Signal, Slot, QThread

from config import COL_TAKE, COL_IN, COL_OUT, COL_PERSONAJE, COL_DIALOGO
from utils import format_timecode, get_formatted_date

def _normalize_text_for_output(text: str) -> str:
    """
    Normaliza el texto para la salida TXT:
    - Reemplaza caracteres específicos.
    - Elimina acentos y diacríticos.
    """
    if not isinstance(text, str):
        text = str(text)

    text = text.replace("…", "...")
    text = text.replace("--", "_")
    text = text.replace("“", "\"")
    text = text.replace("”", "\"")

    nfkd_form = unicodedata.normalize('NFD', text)
    text_without_diacritics = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    
    return text_without_diacritics

class ConversionWorker(QObject):
    """Realiza la conversión de UN archivo Excel a TXT."""
    progress_update = Signal(str)
    detailed_progress = Signal(str)
    finished = Signal(bool, str, str)
    progress_value = Signal(int)

    def __init__(self, excel_path, output_dir, header_info):
        super().__init__()
        self.excel_path = excel_path
        self.output_dir = output_dir
        self.header_info = header_info
        self._is_cancelled = False

    @Slot()
    def request_cancel(self):
        print(f"Cancelación solicitada para: {os.path.basename(self.excel_path)}")
        self._is_cancelled = True

    @Slot()
    def run(self):
        output_path = None
        success = False
        file_basename = os.path.basename(self.excel_path)
        try:
            self.progress_update.emit(f"Iniciando: {file_basename}")
            self.progress_value.emit(-1)

            df = pd.read_excel(self.excel_path, engine='openpyxl', dtype={
                COL_IN: str, COL_OUT: str, COL_PERSONAJE: str, COL_DIALOGO: str
            })
            required_cols = [COL_TAKE, COL_IN, COL_OUT, COL_PERSONAJE, COL_DIALOGO]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols: raise ValueError(f"Faltan columnas: {', '.join(missing_cols)}")

            df[COL_PERSONAJE] = df[COL_PERSONAJE].fillna('').astype(str)
            df[COL_DIALOGO] = df[COL_DIALOGO].fillna('').astype(str)
            
            df.dropna(subset=[COL_TAKE], inplace=True)
            try:
                df[COL_TAKE] = pd.to_numeric(df[COL_TAKE], errors='coerce')
                df.dropna(subset=[COL_TAKE], inplace=True)
                df[COL_TAKE] = df[COL_TAKE].astype(int)
            except Exception as e: raise ValueError(f"Columna '{COL_TAKE}' inválida: {e}")

            grouped = df.groupby(COL_TAKE)
            output_lines = []
            fecha_hoy = get_formatted_date()
            
            output_lines.extend([
                f"Título: {_normalize_text_for_output(self.header_info['Título'])}",
                f"Capítulo: {_normalize_text_for_output(self.header_info['Capítulo'])}",
                f"Traductor: {_normalize_text_for_output(self.header_info['Traductor'])}",
                f"Takeo: {_normalize_text_for_output(self.header_info['Takeo'])}",
                f"Fecha: {fecha_hoy}",
                ""
            ])

            self.progress_update.emit(f"Procesando: {file_basename}...")
            total_takes = len(grouped)
            processed_takes = 0
            self.progress_value.emit(0)

            for take_num, group in grouped:
                if self._is_cancelled:
                    self.progress_update.emit(f"Cancelado: {file_basename}")
                    self.detailed_progress.emit("Cancelado.")
                    self.finished.emit(False, "Cancelado por el usuario.", self.excel_path)
                    return

                if group.empty: continue

                first_row, last_row = group.iloc[0], group.iloc[-1]
                start_time, end_time = format_timecode(first_row[COL_IN]), format_timecode(last_row[COL_OUT])
                
                output_lines.append(f"TAKE {take_num}")
                output_lines.append(start_time)
                
                current_speaker, accumulated_dialogue = None, ""
                for index, row in group.iterrows():
                    personaje_raw = row[COL_PERSONAJE].strip()
                    
                    # MODIFICADO: Se procesa el diálogo para eliminar saltos de línea internos
                    dialogo_raw = row[COL_DIALOGO]

                    # --- INICIO DEL ARREGLO ---
                    # Reemplaza cualquier salto de línea (\n) o retorno de carro (\r) por un espacio.
                    # Esto asegura que el diálogo siempre permanezca en una sola línea en el TXT.
                    # Finalmente, .strip() elimina cualquier espacio sobrante al principio o final.
                    dialogo_raw = dialogo_raw.replace('\n', ' ').replace('\r', ' ').strip()
                    # --- FIN DEL ARREGLO ---

                    personaje = _normalize_text_for_output(personaje_raw)
                    dialogo = _normalize_text_for_output(dialogo_raw)
                    
                    if personaje and dialogo:
                        if personaje == current_speaker: 
                            accumulated_dialogue += " " + dialogo
                        else:
                            if current_speaker and accumulated_dialogue: 
                                output_lines.append(f"{current_speaker}: {accumulated_dialogue}")
                            current_speaker, accumulated_dialogue = personaje, dialogo
                    else:
                        if current_speaker and accumulated_dialogue:
                            output_lines.append(f"{current_speaker}: {accumulated_dialogue}")
                        current_speaker, accumulated_dialogue = None, "" 
                
                if current_speaker and accumulated_dialogue:
                    output_lines.append(f"{current_speaker}: {accumulated_dialogue}")
                
                output_lines.append(end_time)
                output_lines.append("")

                processed_takes += 1
                progress_percent = int((processed_takes / total_takes) * 100)
                self.progress_value.emit(progress_percent)
                self.detailed_progress.emit(f"Procesando Take {processed_takes}/{total_takes}")
                QThread.msleep(1)

            base_name = os.path.splitext(file_basename)[0]
            output_path = os.path.join(self.output_dir, f"{base_name}.txt")
            self.progress_update.emit(f"Guardando: {os.path.basename(output_path)}")
            self.detailed_progress.emit("Guardando archivo...")
            self.progress_value.emit(100)

            with open(output_path, 'w', encoding='utf-8') as f:
                for line in output_lines:
                    f.write(line + '\n')

            self.progress_update.emit(f"Completado: {file_basename}")
            self.detailed_progress.emit("¡Éxito!")
            success = True

        except Exception as e:
            print(f"--- ERROR Procesando {file_basename} ---")
            traceback.print_exc()
            print("--- END TRACEBACK ---")
            error_msg = f"Error en '{file_basename}': {e}"
            self.progress_update.emit(f"Error: {file_basename}")
            self.detailed_progress.emit(f"Error: {e}")
            self.finished.emit(False, error_msg, self.excel_path)
        finally:
            if success:
                self.finished.emit(True, output_path, self.excel_path)