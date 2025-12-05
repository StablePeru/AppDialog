# conversion_worker.py

import os
import traceback
import pandas as pd
import unicodedata

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread

# --- CORRECCIÓN DE IMPORTS ---
try:
    from .config import COL_TAKE, COL_IN, COL_OUT, COL_PERSONAJE, COL_DIALOGO
    from .utils import format_timecode, get_formatted_date
except ImportError:
    from config import COL_TAKE, COL_IN, COL_OUT, COL_PERSONAJE, COL_DIALOGO
    from utils import format_timecode, get_formatted_date
# -----------------------------

def _normalize_text(text: str) -> str:
    """Limpia caracteres extraños y normaliza unicode."""
    if not isinstance(text, str):
        text = str(text)
    
    # Reemplazos tipográficos comunes
    text = text.replace("…", "...").replace("“", "\"").replace("”", "\"")
    
    # Eliminar saltos de línea internos para que quede en una línea en el TXT
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Normalizar Unicode (quitar acentos si fuera necesario, pero aquí mantenemos acentos)
    # Si quisieras quitar acentos descomenta las siguientes líneas:
    # nfkd_form = unicodedata.normalize('NFD', text)
    # text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    
    return text.strip()

class ConversionWorker(QObject):
    """Worker que procesa el Excel y genera el TXT estructurado por Takes."""
    
    progress_update = pyqtSignal(str)
    detailed_progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str) # Success, Message, FilePath
    progress_value = pyqtSignal(int)

    def __init__(self, excel_path, output_dir, header_info):
        super().__init__()
        self.excel_path = excel_path
        self.output_dir = output_dir
        self.header_info = header_info
        self._is_cancelled = False

    @pyqtSlot()
    def request_cancel(self):
        self._is_cancelled = True

    @pyqtSlot()
    def run(self):
        output_path = None
        success = False
        try:
            # 1. Cargar Excel
            df = pd.read_excel(self.excel_path, engine='openpyxl')
            
            # Normalizar nombres de columnas a mayúsculas para evitar errores
            df.columns = df.columns.astype(str).str.upper().str.strip()
            
            # Determinar columna de diálogo real
            col_dialogo_real = COL_DIALOGO # Por defecto 'EUSKERA' según config.py
            if COL_DIALOGO not in df.columns and 'DIALOGO' in df.columns:
                col_dialogo_real = 'DIALOGO'
            elif COL_DIALOGO not in df.columns and 'DIÁLOGO' in df.columns:
                col_dialogo_real = 'DIÁLOGO'
                
            # Verificar columnas esenciales
            required = [COL_TAKE, COL_IN, COL_OUT, COL_PERSONAJE]
            missing = [c for c in required if c not in df.columns]
            
            if missing:
                raise ValueError(f"Faltan columnas en el Excel: {', '.join(missing)}")
            
            if col_dialogo_real not in df.columns:
                 raise ValueError(f"No se encontró columna de diálogo (EUSKERA/DIALOGO).")

            # Limpiar filas sin TAKE válido
            df = df.dropna(subset=[COL_TAKE])
            df[COL_TAKE] = pd.to_numeric(df[COL_TAKE], errors='coerce')
            df = df.dropna(subset=[COL_TAKE])
            df[COL_TAKE] = df[COL_TAKE].astype(int)
            
            # Ordenar por TAKE y luego por IN (por si acaso)
            # Asumimos que IN es texto, así que el orden alfabético suele funcionar para TC
            df = df.sort_values(by=[COL_TAKE, COL_IN])

            # 2. Generar Cabecera
            lines = []
            lines.append(f"Título: {self.header_info.get('Título', '')}")
            lines.append(f"Capítulo: {self.header_info.get('Capítulo', '')}")
            lines.append(f"Traductor: {self.header_info.get('Traductor', '')}")
            lines.append(f"Takeo: {self.header_info.get('Takeo', '')}")
            lines.append(f"Fecha: {get_formatted_date()}")
            lines.append("") # Línea en blanco separadora

            # 3. Procesar Grupos (Takes)
            # Agrupar por número de TAKE
            grouped = df.groupby(COL_TAKE)
            
            for take_num, group in grouped:
                if self._is_cancelled: break
                
                # Obtener IN del primer elemento y OUT del último elemento del grupo
                # (Asumiendo que están ordenados temporalmente dentro del take)
                start_tc = format_timecode(group.iloc[0][COL_IN])
                end_tc = format_timecode(group.iloc[-1][COL_OUT])
                
                lines.append(f"TAKE {take_num}")
                lines.append(start_tc)
                
                # Procesar líneas de diálogo dentro del Take
                for _, row in group.iterrows():
                    personaje = str(row[COL_PERSONAJE]).strip().upper()
                    texto = _normalize_text(row[col_dialogo_real])
                    
                    if personaje and texto:
                        lines.append(f"{personaje}: {texto}")
                
                lines.append(end_tc)
                lines.append("") # Línea en blanco entre takes

            # 4. Guardar Archivo
            base_name = os.path.splitext(os.path.basename(self.excel_path))[0]
            output_path = os.path.join(self.output_dir, f"{base_name}.txt")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            
            success = True
            self.finished.emit(True, "Conversión completada.", self.excel_path)

        except Exception as e:
            traceback.print_exc()
            self.finished.emit(False, str(e), self.excel_path)