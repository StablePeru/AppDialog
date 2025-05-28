import json
import os
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QShortcut, QKeySequence

# Ruta relativa correcta a shortcuts.json
CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shortcuts.json'))

class ConfigurationExistsError(Exception):
    """Excepción personalizada para configuraciones duplicadas."""
    pass

class ShortcutManager:
    def __init__(self, main_window):
        """
        Inicializa el gestor de atajos, cargando configuraciones desde un archivo JSON.
        Si el archivo no existe, se crea una configuración predeterminada.
        """
        self.main_window = main_window
        self.configurations = {}
        self.current_config = 'default'
        self.shortcuts = {}  # Diccionario para almacenar los atajos creados
        self.load_shortcuts()

    def load_shortcuts(self):
        """
        Carga los atajos desde el archivo de configuración JSON.
        Si el archivo no existe o se produce un error, se crea una configuración predeterminada.
        """
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.current_config = data.get("current_config", "default")
                    self.configurations = data.get("configs", {})
            except Exception as e:
                QMessageBox.warning(self.main_window, "Error", f"Error al cargar shortcuts: {str(e)}")
                self.configurations = {}
        else:
            self.create_default_config()

        self.apply_shortcuts(self.current_config)

    def create_default_config(self):
        """
        Crea una configuración predeterminada con atajos comunes y la guarda en un archivo JSON.
        """
        self.configurations = {
            "default": {
                "&Abrir Video": "Ctrl+O",
                "&Abrir Guion": "Ctrl+G",
                "&Exportar Guion a Excel": "Ctrl+E",
                "&Importar Guion desde Excel": "Ctrl+I",
                "&Guardar Guion como JSON": "Ctrl+S",
                "&Cargar Guion desde JSON": "Ctrl+D",
                "&Agregar Línea": "Ctrl+N",
                "&Eliminar Fila": "Ctrl+Del",
                "Mover &Arriba": "Alt+Up",
                "Mover &Abajo": "Alt+Down",
                "&Separar Intervención": "Alt+I",
                "&Juntar Intervenciones": "Alt+J",
                "&Configuración": "Ctrl+K",
                "Pausar/Reproducir": "Ctrl+Up",
                "Retroceder": "Ctrl+Left",
                "Avanzar": "Ctrl+Right",
                "Copiar IN/OUT a Siguiente": "Ctrl+B",
                "change_scene": "Ctrl+R"
            }
        }
        self.current_config = "default"
        self.save_shortcuts()

    def save_shortcuts(self):
        """
        Guarda las configuraciones de atajos en un archivo JSON.
        """
        data = {
            "current_config": self.current_config,
            "configs": self.configurations
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self.main_window, "Error", f"Error al guardar shortcuts: {str(e)}")

    def apply_shortcuts(self, config_name):
        """
        Aplica los atajos según la configuración seleccionada.
        Si la configuración no existe, muestra una advertencia.
        """
        if config_name not in self.configurations:
            return
        
        self.current_config = config_name
        shortcuts_config = self.configurations[config_name]
        
        # Desconectar shortcuts anteriores
        for q_shortcut_obj in self.shortcuts.values():
            if q_shortcut_obj:
                try:
                    q_shortcut_obj.setEnabled(False)
                    q_shortcut_obj.activated.disconnect()
                except RuntimeError:
                    pass 
        self.shortcuts.clear()

        for action_name, shortcut_str in shortcuts_config.items():
            action = self.main_window.actions.get(action_name)
            if action:
                try:
                    action.setShortcut(shortcut_str)
                except Exception as e:
                    # Silenciosamente ignorar o usar print para depuración si es estrictamente necesario
                    # print(f"Error al asignar shortcut '{shortcut_str}' a la acción '{action_name}': {e}")
                    pass
            elif action_name == "change_scene":
                key_seq = QKeySequence(shortcut_str)
                if "change_scene" in self.main_window.actions:
                    self.main_window.actions["change_scene"].setShortcut(key_seq)
                else:
                    try:
                        shortcut_obj = QShortcut(key_seq, self.main_window)
                        shortcut_obj.activated.connect(self.main_window.change_scene)
                        self.shortcuts[action_name] = shortcut_obj
                    except Exception as e:
                        # print(f"Error al crear QShortcut para '{action_name}' con '{shortcut_str}': {e}")
                        pass
            # else: No mostrar warnings en producción limpia

    def add_configuration(self, name, shortcuts):
        """
        Añade una nueva configuración de atajos.
        Si el nombre ya existe, lanza una excepción personalizada.
        """
        if name in self.configurations:
            raise ConfigurationExistsError(f"Ya existe una configuración con el nombre '{name}'.")
        self.configurations[name] = shortcuts
        self.save_shortcuts()
        return True

    def delete_configuration(self, name):
        """
        Elimina una configuración de atajos, excepto la predeterminada.
        Después de eliminar, actualiza el menú de shortcuts.
        """
        if name == "default":
            QMessageBox.warning(self.main_window, "Error", "No se puede eliminar la configuración 'default'.")
            return False
        if name in self.configurations:
            del self.configurations[name]
            self.save_shortcuts()
            self.refresh_shortcuts_menu()
            return True
        QMessageBox.warning(self.main_window, "Error", f"Configuración '{name}' no encontrada.")
        return False

    def refresh_shortcuts_menu(self):
        """
        Actualiza el menú de shortcuts en la interfaz para reflejar los cambios.
        """
        menuBar = self.main_window.menuBar()
        for action in menuBar.actions():
            if action.menu() and action.menu().title() == "&Shortcuts":
                menuBar.removeAction(action)
                break
        self.main_window.create_shortcuts_menu(menuBar)

    def update_configuration(self, name, shortcuts):
        """
        Actualiza una configuración de atajos existente.
        Si la configuración no existe, muestra un mensaje de error.
        """
        if name not in self.configurations:
            QMessageBox.warning(self.main_window, "Error", f"Configuración '{name}' no encontrada.")
            return False
        self.configurations[name] = shortcuts
        self.save_shortcuts()
        return True