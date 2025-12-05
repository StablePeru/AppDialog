# guion_editor/widgets/xlsx_converter/main.py
import sys
import os
import pandas as pd
import traceback

from PyQt6.QtWidgets import QApplication

try:
    from .main_window import MainWindow
    from .config import COL_TAKE, COL_IN, COL_OUT, COL_PERSONAJE, COL_DIALOGO
    from .utils import format_timecode, get_formatted_date
except ImportError:
    from main_window import MainWindow
    from config import COL_TAKE, COL_IN, COL_OUT, COL_PERSONAJE, COL_DIALOGO
    from utils import format_timecode, get_formatted_date

def _normalize_text(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("…", "...").replace("“", "\"").replace("”", "\"")
    # Eliminar saltos de línea internos
    text = text.replace('\n', ' ').replace('\r', ' ')
    return text.strip()

def process_excel_to_txt(excel_path: str, target_column: str, header_data: dict = None, custom_output_name: str = None) -> str:
    """
    Versión síncrona de la lógica de conversión.
    Agrupa por TAKES y fusiona intervenciones consecutivas del mismo personaje.
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError("El archivo Excel no existe.")

    # 1. Cargar Dataframe
    df = pd.read_excel(excel_path, engine='openpyxl')
    
    # Normalizar columnas
    df.columns = df.columns.astype(str).str.upper().str.strip()
    
    col_dialogo_real = COL_DIALOGO
    target_upper = target_column.upper().strip()
    
    if target_upper in df.columns:
        col_dialogo_real = target_upper
    elif 'DIALOGO' in df.columns:
        col_dialogo_real = 'DIALOGO'
    elif 'DIÁLOGO' in df.columns:
        col_dialogo_real = 'DIÁLOGO'
    
    required = [COL_TAKE, COL_IN, COL_OUT, COL_PERSONAJE]
    missing = [c for c in required if c not in df.columns]
    if missing:
        if COL_TAKE in missing:
            return _process_simple_fallback(df, excel_path, col_dialogo_real)
        raise ValueError(f"Faltan columnas: {', '.join(missing)}")

    # Limpiar y Ordenar
    df = df.dropna(subset=[COL_TAKE])
    df[COL_TAKE] = pd.to_numeric(df[COL_TAKE], errors='coerce')
    df = df.dropna(subset=[COL_TAKE])
    df[COL_TAKE] = df[COL_TAKE].astype(int)
    df = df.sort_values(by=[COL_TAKE, COL_IN])

    # 2. Generar Cabecera
    lines = []
    
    titulo = os.path.splitext(os.path.basename(excel_path))[0]
    capitulo = "-"
    traductor = "-"
    takeo = "-"

    if header_data:
        titulo = header_data.get("product_name") or header_data.get("Título") or titulo
        capitulo = header_data.get("chapter_number") or header_data.get("Capítulo") or capitulo
        traductor = header_data.get("Traductor") or traductor
        takeo = header_data.get("Takeo") or takeo

    lines.append(f"Título: {titulo}")
    lines.append(f"Capítulo: {capitulo}")
    lines.append(f"Traductor: {traductor}")
    lines.append(f"Takeo: {takeo}")
    lines.append(f"Fecha: {get_formatted_date()}")
    lines.append("")

    # 3. Procesar Takes
    grouped = df.groupby(COL_TAKE)
    for take_num, group in grouped:
        start_tc = format_timecode(group.iloc[0][COL_IN])
        end_tc = format_timecode(group.iloc[-1][COL_OUT])
        
        lines.append(f"TAKE {take_num}")
        lines.append(start_tc)
        
        # --- LÓGICA DE FUSIÓN DE LÍNEAS ---
        last_char = None
        current_block_text = []

        for _, row in group.iterrows():
            personaje = str(row[COL_PERSONAJE]).strip().upper()
            texto = _normalize_text(row[col_dialogo_real])
            
            if not personaje or not texto:
                continue

            if personaje == last_char:
                # Mismo personaje: añadir al bloque
                current_block_text.append(texto)
            else:
                # Nuevo personaje: escribir el anterior si existe
                if last_char is not None:
                    # ' '.join une las líneas con un espacio, asegurando que no haya saltos
                    combined_text = " ".join(current_block_text)
                    lines.append(f"{last_char}: {combined_text}")
                
                # Iniciar nuevo bloque
                last_char = personaje
                current_block_text = [texto]

        # Escribir el último bloque del take
        if last_char is not None:
            combined_text = " ".join(current_block_text)
            lines.append(f"{last_char}: {combined_text}")
        # ----------------------------------
        
        lines.append(end_tc)
        lines.append("")

    # 4. Guardar
    folder = os.path.dirname(excel_path)
    
    if custom_output_name:
        if not custom_output_name.lower().endswith('.txt'):
            custom_output_name += ".txt"
        output_path = os.path.join(folder, custom_output_name)
    else:
        base_name = os.path.splitext(os.path.basename(excel_path))[0]
        output_path = os.path.join(folder, f"{base_name}.txt")

    # --- CAMBIO IMPORTANTE AQUÍ ---
    with open(output_path, "w", encoding="cp1252", errors='replace') as f:
        f.write("\n".join(lines))
    # ------------------------------
        
    return output_path

def _process_simple_fallback(df, excel_path, target_col):
    lines = []
    if COL_PERSONAJE in df.columns and target_col in df.columns:
        for _, row in df.iterrows():
            p = str(row[COL_PERSONAJE]).strip()
            t = str(row[target_col]).strip()
            if p and t and p != 'nan' and t != 'nan':
                lines.append(f"{p}\n{t}\n")
    
    output_path = excel_path.replace(".xlsx", ".txt")
    with open(output_path, "w", encoding="cp1252", errors='replace') as f:
        f.write("\n".join(lines))
    return output_path

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()