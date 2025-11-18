# guion_editor/utils/dialog_utils.py
import re
from docx import Document
from .. import constants as C
import logging

def ajustar_dialogo(dialogo, max_chars=60):
    # ... (código sin cambios)
    lineas_ajustadas = []
    for linea_original in dialogo.split('\n'):
        palabras = linea_original.split()
        if not palabras:
            lineas_ajustadas.append("")
            continue

        linea_actual = ""
        for palabra in palabras:
            if not linea_actual:
                linea_actual = palabra
            elif contar_caracteres(linea_actual + " " + palabra) <= max_chars:
                linea_actual += " " + palabra
            else:
                lineas_ajustadas.append(linea_actual)
                linea_actual = palabra
        
        lineas_ajustadas.append(linea_actual)

    return "\n".join(lineas_ajustadas)

def contar_caracteres(dialogo):
    # ... (código sin cambios)
    dialogo_limpio = re.sub(r'\([^)]*\)', '', dialogo)
    return len(dialogo_limpio)

def es_nombre_personaje(texto):
    # ... (código sin cambios)
    if '.' in texto or ',' in texto:
        return False
    palabras = texto.split()
    if len(palabras) > 3:
        return False
    return texto.upper() == texto

def leer_guion(docx_file):
    # ... (código sin cambios)
    try:
        doc = Document(docx_file)
        guion = []
        personaje_actual = None
        dialogo_acumulado = []
        
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        
        i = 0
        while i < len(paragraphs):
            texto = paragraphs[i]
            
            if es_nombre_personaje(texto):
                if personaje_actual:
                    guardar_dialogo(guion, personaje_actual, dialogo_acumulado)
                
                personaje_actual = texto
                dialogo_acumulado = []
                
                if i + 1 < len(paragraphs):
                    siguiente_texto = paragraphs[i + 1]
                    if not es_nombre_personaje(siguiente_texto):
                        dialogo_acumulado.append(siguiente_texto)
                        i += 2
                        continue
                
                i += 1
            else:
                if personaje_actual:
                    dialogo_acumulado.append(texto)
                i += 1
        
        if personaje_actual:
            guardar_dialogo(guion, personaje_actual, dialogo_acumulado)
        
        return guion
    
    except Exception as e:
        logging.error(f"Error al leer el guion DOCX: {e}", exc_info=True)
        return []

def guardar_dialogo(guion, personaje, dialogo_acumulado):
    # ... (código sin cambios)
    texto_completo = " ".join(dialogo_acumulado) if dialogo_acumulado else ""
    dialogo_ajustado = ajustar_dialogo(texto_completo)
    guion.append({
        C.COL_IN: '00:00:00:00',
        C.COL_OUT: '00:00:00:00',
        C.COL_PERSONAJE: personaje,
        C.COL_DIALOGO: dialogo_ajustado
    })

def tc_to_frames(tc: str, fps: int) -> int | None:
    # ... (código sin cambios)
    tc = str(tc).strip()
    if not tc or tc.lower() == "nan":
        return None
    parts = tc.split(":")
    if len(parts) != 4:
        return None
    try:
        h, m, s, f = [int(p) for p in parts]
        return ((h * 3600 + m * 60 + s) * fps) + f
    except (ValueError, TypeError):
        return None

def frames_to_tc(frames: int, fps: int) -> str:
    # ... (código sin cambios)
    if frames is None:
        return ""
    if frames < 0:
        frames = 0
    
    s_total, f = divmod(frames, fps)
    h, s_rem = divmod(s_total, 3600)
    m, s = divmod(s_rem, 60)
    
    h_str = f"{h:02d}" if h < 100 else str(h)
    return f"{h_str}:{m:02d}:{s:02d}:{f:02d}"