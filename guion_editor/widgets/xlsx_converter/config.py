# config.py
# Definición de constantes de configuración

HEADER_DEFAULTS = {
    "Título": "Título nombre",
    "Capítulo": "Capítulo nombre",
    "Traductor": "Traductor nombre",
    "Takeo": "Takeo nombre"
}

# Nombres EXACTOS de las columnas en el Excel
# Asegúrate de que tu Excel de entrada tenga estos nombres
COL_TAKE = 'TAKE'
COL_IN = 'IN'
COL_OUT = 'OUT'
COL_PERSONAJE = 'PERSONAJE'
COL_DIALOGO = 'EUSKERA'  # O 'DIALOGO', se buscará dinámicamente si es necesario

# Ruta del icono (relativa al script principal o main_window.py)
ICON_PATH = "icon.ico"