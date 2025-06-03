# guion_editor/utils/shortcut_manager.py

import json
import os
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QShortcut, QKeySequence

# CONFIG_FILE debe apuntar a la raíz del proyecto si main.py está allí.
# Si main.py está en un subdirectorio, ajusta el path.
CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'shortcuts.json'))
if not os.path.exists(CONFIG_FILE): # Fallback si la estructura es diferente (ej. main.py está en la raíz)
    alt_config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'shortcuts.json'))
    if os.path.exists(alt_config_file_path):
        CONFIG_FILE = alt_config_file_path
    # else: Podrías añadir más fallbacks o un error si no se encuentra


class ConfigurationExistsError(Exception):
    pass

class ShortcutManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.configurations = {}
        self.current_config = 'default'
        self.load_shortcuts()

    def load_shortcuts(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.current_config = data.get("current_config", "default")
                    self.configurations = data.get("configs", {})
                    # Asegurarse de que la configuración 'default' exista y tenga las entradas necesarias
                    if "default" not in self.configurations or \
                       "edit_undo" not in self.configurations["default"] or \
                       "edit_redo" not in self.configurations["default"]:
                        self.create_default_config() # Crea o actualiza 'default'
                        # Si 'default' existía pero le faltaban claves, las fusionamos
                        # Si no existía, se crea de nuevo.
                        # Guardamos solo si se creó/modificó significativamente 'default'.
                        # Esta lógica podría refinarse para fusionar solo las claves faltantes.
                        existing_default = self.configurations.get("default", {})
                        default_template = self._get_default_config_template()
                        
                        updated = False
                        for key, value in default_template.items():
                            if key not in existing_default:
                                existing_default[key] = value
                                updated = True
                        
                        if updated or "default" not in self.configurations:
                             self.configurations["default"] = existing_default # Asegura que 'default' esté completo
                             self.save_shortcuts()


            except json.JSONDecodeError:
                QMessageBox.warning(self.main_window, "Error de Configuración",
                                    f"El archivo de shortcuts '{os.path.basename(CONFIG_FILE)}' está corrupto o malformado. Se creará uno nuevo con valores predeterminados.")
                self.create_default_config() # Sobrescribe con la plantilla completa
                self.save_shortcuts()
            except Exception as e:
                QMessageBox.warning(self.main_window, "Error", f"Error al cargar shortcuts: {str(e)}. Se usarán valores predeterminados.")
                self.create_default_config() # Sobrescribe
                self.save_shortcuts()
        else:
            self.create_default_config() # El archivo no existe, se crea con la plantilla completa
            self.save_shortcuts()

        self.apply_shortcuts(self.current_config)

    def _get_default_config_template(self):
        """Retorna la plantilla de configuración por defecto."""
        return {
            # File Menu
            "file_open_video": "Ctrl+O",
            "file_load_me": "Ctrl+Shift+M",
            "file_open_docx": "Ctrl+G",
            "file_export_excel": "Ctrl+E",
            "file_import_excel": "Ctrl+I",
            "file_save_json": "Ctrl+S",
            "file_load_json": "Ctrl+L",
            # Edit Menu
            "edit_undo": "Ctrl+Z",  # <--- AÑADIDO/ACTUALIZADO
            "edit_redo": "Ctrl+Shift+Z",  # <--- AÑADIDO/ACTUALIZADO (Ctrl+Y también es común)
            "edit_add_row": "Ctrl+N",
            "edit_delete_row": "Ctrl+Del",
            "edit_move_up": "Alt+Up",
            "edit_move_down": "Alt+Down",
            "edit_adjust_dialogs": "",
            "edit_split_intervention": "Alt+S",
            "edit_merge_interventions": "Alt+M",
            "edit_view_cast": "",
            "edit_find_replace": "Ctrl+F",
            "edit_copy_in_out": "Ctrl+B",
            "edit_increment_scene": "Ctrl+R",
            # Config Menu (Tools)
            "config_app_settings": "Ctrl+K",
            # Video Player (no están en el menú, pero son configurables)
            "video_toggle_play": "F8",
            "video_rewind": "F7",
            "video_forward": "F9",
            "video_mark_in": "F5",
            "video_mark_out_hold": "F6",
            # Shortcut management itself
            "config_shortcuts_dialog": "",
            "config_delete_shortcut_profile": ""
        }

    def create_default_config(self):
        """Crea o sobrescribe la configuración 'default' completa y la establece como actual."""
        self.configurations["default"] = self._get_default_config_template()
        self.current_config = "default"
        # No llama a save_shortcuts() aquí, se espera que el llamador lo haga si es necesario.

    def save_shortcuts(self):
        data = {
            "current_config": self.current_config,
            "configs": self.configurations
        }
        try:
            # Asegurarse de que la carpeta de config exista si es necesario (si CONFIG_FILE incluye subdirectorios)
            config_dir = os.path.dirname(CONFIG_FILE)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self.main_window, "Error", f"Error al guardar shortcuts: {str(e)}")

    def apply_shortcuts(self, config_name):
        if config_name not in self.configurations:
            QMessageBox.warning(self.main_window, "Advertencia", f"Configuración de shortcuts '{config_name}' no encontrada. Usando 'default'.")
            config_name = "default"
            if "default" not in self.configurations:
                 self.create_default_config()
                 # No es necesario guardar aquí, ya que apply_shortcuts no modifica el archivo, solo aplica.
        
        self.current_config = config_name
        # Obtener la configuración. Si la clave no existe en la config, get() devolverá "" (para shortcut_str)
        shortcuts_config = self.configurations.get(config_name, {})

        for action_object_name, action in self.main_window.actions.items():
            # Obtener el shortcut_str del perfil actual.
            # Si la acción no está definida en el perfil, usar "" (sin atajo).
            shortcut_str = shortcuts_config.get(action_object_name, "")

            if action_object_name == "video_mark_out_hold":
                self.main_window.mark_out_hold_key_sequence = QKeySequence(shortcut_str)
                action.setShortcut(QKeySequence())
            else:
                try:
                    action.setShortcut(QKeySequence(shortcut_str))
                except Exception as e:
                    print(f"Error al aplicar shortcut '{shortcut_str}' a la acción '{action.objectName()}': {e}")
        
        if hasattr(self.main_window, 'videoPlayerWidget'):
            self.main_window.videoPlayerWidget.update_key_listeners()
        if hasattr(self.main_window, 'tableWindow'):
            self.main_window.tableWindow.update_key_listeners()
        if hasattr(self.main_window, 'videoWindow') and self.main_window.videoWindow:
            self.main_window.videoWindow.update_key_listeners()

    def add_configuration(self, name, shortcuts_dict):
        if name in self.configurations:
            # Esto debería ser manejado por la lógica de "Sobrescribir" en el diálogo
            # Si llegamos aquí, es un error o un intento de añadir duplicado sin confirmación.
             QMessageBox.warning(self.main_window, "Error", f"Ya existe una configuración con el nombre '{name}'.")
             return False # Indicar fallo
        self.configurations[name] = shortcuts_dict
        self.save_shortcuts()
        self.refresh_shortcuts_menu()
        return True

    def delete_configuration(self, name):
        if name == "default":
            QMessageBox.warning(self.main_window, "Error", "No se puede eliminar la configuración 'default'.")
            return False
        if name in self.configurations:
            del self.configurations[name]
            if self.current_config == name:
                self.current_config = "default"
                self.apply_shortcuts("default") # Aplicar default si el actual fue borrado
            self.save_shortcuts()
            self.refresh_shortcuts_menu()
            return True
        QMessageBox.warning(self.main_window, "Error", f"Configuración '{name}' no encontrada.")
        return False

    def refresh_shortcuts_menu(self):
        self.main_window.create_shortcuts_menu(self.main_window.menuBar())

    def update_configuration(self, name, shortcuts_dict):
        """Actualiza una configuración existente. Usado por ShortcutConfigDialog al asignar."""
        if name not in self.configurations:
            # Si se llama para una config que no existe, es un error de lógica.
            # El diálogo debería guardar como nueva config o el usuario debería seleccionar una existente.
            # No crearemos una nueva config aquí; eso lo hace add_configuration.
            QMessageBox.warning(self.main_window, "Error Interno", f"Intento de actualizar configuración no existente '{name}'.")
            return False
            
        self.configurations[name] = shortcuts_dict
        self.save_shortcuts()
        if name == self.current_config:
            self.apply_shortcuts(name) # Re-aplicar si la configuración activa cambió
        # self.refresh_shortcuts_menu() # No siempre necesario aquí, a menos que el nombre pudiera cambiar.
        return True