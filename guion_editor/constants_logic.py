# guion_editor/constants_logic.py

# --- Constantes Globales de Lógica ---
# --- Constantes Globales de Lógica ---
FPS = 25.0
DEFAULT_TIMECODE = "00:00:00:00"
DEFAULT_SCENE = "1"
MAX_INTERVENTION_DURATION_MS = 30000  # 30 segundos
DEFAULT_LINE_LENGTH = 60

# --- Regex Patterns ---
# Captura texto entre paréntesis, incluyendo posibles espacios anteriores
REGEX_PARENTHETICALS = r'\s*\(.*?\)'


# --- Nombres de Columnas del DataFrame ---
COL_ID = 'ID'
COL_SCENE = 'SCENE'
COL_IN = 'IN'
COL_OUT = 'OUT'
COL_PERSONAJE = 'PERSONAJE'
COL_DIALOGO = 'DIÁLOGO'
COL_EUSKERA = 'EUSKERA'
COL_OHARRAK = 'OHARRAK'
COL_BOOKMARK = 'BOOKMARK'
COL_REPARTO = 'REPARTO'

# --- Lista Ordenada de Columnas para el DataFrame ---
DF_COLUMN_ORDER = [
    COL_ID, COL_SCENE, COL_IN, COL_OUT, COL_PERSONAJE,
    COL_DIALOGO, COL_EUSKERA, COL_OHARRAK, COL_BOOKMARK
]