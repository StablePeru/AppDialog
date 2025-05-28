# setup.py
import sys
import os
from cx_Freeze import setup, Executable

# 1) Opcional: leer la versión de la app desde un lugar central.
VERSION = "1.0"

# 2) Dependiendo de si quieres consola o no, ajusta "base"
#    Si es una app gráfica en Windows, para ocultar consola usa "Win32GUI".
base = None
if sys.platform == "win32":
    base = "Win32GUI"

# 3) Define las opciones de compilación:
build_exe_options = {
    # 'packages': ...        # Si necesitas forzar la inclusión de algún paquete en concreto
    # 'excludes': ...        # Si quieres excluir librerías no usadas
    'include_files': [
        # (ruta_origen, ruta_destino_en_build)

        # Incluimos la carpeta con los estilos CSS
        ("guion_editor/styles/main.css",      "guion_editor/styles/main.css"),
        ("guion_editor/styles/table_styles.css", "guion_editor/styles/table_styles.css"),

        # Si tienes otros ficheros .json, .docx, etc., añádelos del mismo modo.
        # Por ejemplo:
        # ("guion_editor/utils/shortcuts.json", "guion_editor/utils/shortcuts.json"),
    ]
}

# 4) Define el/los ejecutables:
executables = [
    Executable(
        script="main.py",  # Punto de entrada
        base=base,
        target_name="DialogApp.exe"     # Nombre final del ejecutable
        # icon="icono.ico"             # Si quieres definir icono en Windows
    )
]

# 5) Llama a setup
setup(
    name="DialogAppIngeos",
    version=VERSION,
    description="Aplicación de edición de guiones con PyQt5",
    options={"build_exe": build_exe_options},
    executables=executables
)
