# guion_editor/utils/paths.py
import sys
import os
from pathlib import Path

def get_app_root():
    """
    Devuelve la ruta raíz de la aplicación.
    Maneja correctamente si la app está congelada (PyInstaller) o es script.
    """
    if getattr(sys, 'frozen', False):
        # Si es un ejecutable compilado (PyInstaller)
        return Path(sys._MEIPASS)
    else:
        # Si es un script normal, subimos 2 niveles desde este archivo
        # (utils -> guion_editor -> root)
        return Path(__file__).parent.parent.parent

def resource_path(relative_path: str) -> str:
    """
    Obtiene la ruta absoluta a un recurso (iconos, css),
    funcione tanto en desarrollo como compilado.
    """
    base_path = get_app_root()
    # Convertimos a string para compatibilidad con APIs de Qt que esperan str
    return str(base_path / relative_path)

def get_user_config_dir() -> Path:
    """
    Devuelve una carpeta segura para guardar configuraciones (shortcuts.json, logs).
    Usa la carpeta del usuario en lugar de rutas relativas peligrosas.
    """
    # En Windows suele ser C:\Users\TuUsuario\GuionEditor
    # En Linux/Mac usa la home.
    user_dir = Path.home() / "GuionEditorConfig"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def get_safe_save_dir(preferred_path: str = None) -> str:
    """
    Intenta usar la ruta preferida (ej. W:\...), pero si no existe,
    hace fallback a Documentos para no crashear.
    """
    if preferred_path and os.path.exists(preferred_path):
        return preferred_path
    
    # Fallback a Documentos
    docs_dir = Path.home() / "Documents" / "GuionEditorSaves"
    docs_dir.mkdir(parents=True, exist_ok=True)
    return str(docs_dir)