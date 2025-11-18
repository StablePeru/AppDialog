# guion_editor/constants.py

# --- Constantes Globales ---
FPS = 25.0

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
COL_REPARTO = 'REPARTO' # Usado en CastWindow/exportación

# --- Identificadores Especiales para el Modelo de la Tabla ---
# Se usan en el mapeo de columnas de la vista pero no son columnas reales del DataFrame
ROW_NUMBER_COL_IDENTIFIER = "__ROW_NUMBER__"
DURATION_COL_IDENTIFIER = "__DURATION__"

# --- Lista Ordenada de Columnas para el DataFrame ---
DF_COLUMN_ORDER = [
    COL_ID, COL_SCENE, COL_IN, COL_OUT, COL_PERSONAJE,
    COL_DIALOGO, COL_EUSKERA, COL_OHARRAK, COL_BOOKMARK
]

# --- Índices de Columnas de la Vista (TableWindow) ---
VIEW_COL_NUM_INTERV = 0
VIEW_COL_ID = 1
VIEW_COL_SCENE = 2
VIEW_COL_IN = 3
VIEW_COL_OUT = 4
VIEW_COL_DURATION = 5
VIEW_COL_CHARACTER = 6
VIEW_COL_DIALOGUE = 7
VIEW_COL_EUSKERA = 8
VIEW_COL_OHARRAK = 9
VIEW_COL_BOOKMARK = 10

# --- Nombres de las Columnas de la Vista (TableWindow) ---
VIEW_COLUMN_NAMES = ["Nº", "ID", "SCENE", "IN", "OUT", "DURACIÓN", "PERSONAJE", "DIÁLOGO", "EUSKERA", "OHARRAK", "BOOKMARK"]