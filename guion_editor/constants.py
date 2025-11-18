# guion_editor/constants.py

# Importamos todas las constantes de lógica pura
from .constants_logic import *

# --- Constantes Específicas de la Interfaz Gráfica (UI) ---

# --- Identificadores Especiales para el Modelo de la Tabla ---
ROW_NUMBER_COL_IDENTIFIER = "__ROW_NUMBER__"
DURATION_COL_IDENTIFIER = "__DURATION__"

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
