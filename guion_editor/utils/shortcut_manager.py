import json
import os
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QShortcut, QKeySequence

# CONFIG_FILE debe apuntar a la raíz del proyecto si main.py está allí.
# Si main.py está en un subdirectorio, ajusta el path.
# Asumiendo que main.py está en la raíz del proyecto:
CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'shortcuts.json'))
if not os.path.exists(CONFIG_FILE): # Fallback si la estructura es diferente
    CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'shortcuts.json'))


class ConfigurationExistsError(Exception):
    pass

class ShortcutManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.configurations = {}
        self.current_config = 'default'
        # self.shortcuts QShortcut objects are largely managed by QAction now
        self.load_shortcuts()

    def load_shortcuts(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.current_config = data.get("current_config", "default")
                    self.configurations = data.get("configs", {})
                    if not self.configurations or "default" not in self.configurations:
                        # If file is corrupt or default is missing, recreate
                        self.create_default_config()
                        self.save_shortcuts() # Save the newly created default
            except json.JSONDecodeError: # Handle case where JSON is malformed
                QMessageBox.warning(self.main_window, "Error de Configuración", 
                                    f"El archivo de shortcuts '{os.path.basename(CONFIG_FILE)}' está corrupto o malformado. Se creará uno nuevo con valores predeterminados.")
                self.create_default_config()
                self.save_shortcuts()
            except Exception as e:
                QMessageBox.warning(self.main_window, "Error", f"Error al cargar shortcuts: {str(e)}. Se usarán valores predeterminados.")
                self.create_default_config()
        else:
            self.create_default_config()
            self.save_shortcuts() # Save the newly created default

        self.apply_shortcuts(self.current_config)

    def create_default_config(self):
        self.configurations = {
            "default": {
                # File Menu
                "file_open_video": "Ctrl+O",
                "file_load_me": "Ctrl+Shift+M",
                "file_open_docx": "Ctrl+G",
                "file_export_excel": "Ctrl+E",
                "file_import_excel": "Ctrl+I",
                "file_save_json": "Ctrl+S",
                "file_load_json": "Ctrl+L", # Changed from Ctrl+D to avoid conflict
                # Edit Menu
                "edit_add_row": "Ctrl+N",
                "edit_delete_row": "Ctrl+Del",
                "edit_move_up": "Alt+Up",
                "edit_move_down": "Alt+Down",
                "edit_adjust_dialogs": "", # No default shortcut, can be set by user
                "edit_split_intervention": "Alt+S",
                "edit_merge_interventions": "Alt+M",
                "edit_view_cast": "",
                "edit_find_replace": "Ctrl+F",
                "edit_copy_in_out": "Ctrl+B",
                "edit_increment_scene": "Ctrl+R",
                # Config Menu
                "config_app_settings": "Ctrl+K",
                # Video Player
                "video_toggle_play": "F8",
                "video_rewind": "F7",
                "video_forward": "F9",
                "video_mark_in": "F5",
                "video_mark_out_hold": "F6", # Conceptual, handled by key events
                # Shortcut management itself typically doesn't have shortcuts
                "config_shortcuts_dialog": "", 
                "config_delete_shortcut_profile": ""
            }
        }
        self.current_config = "default"

    def save_shortcuts(self):
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
        if config_name not in self.configurations:
            QMessageBox.warning(self.main_window, "Advertencia", f"Configuración de shortcuts '{config_name}' no encontrada. Usando 'default'.")
            config_name = "default"
            if "default" not in self.configurations: # Should not happen if load_shortcuts is robust
                 self.create_default_config() # Critical fallback
        
        self.current_config = config_name
        shortcuts_config = self.configurations[config_name]
        
        # Iterate over all actions defined in MainWindow
        for action_object_name, action in self.main_window.actions.items():
            shortcut_str = shortcuts_config.get(action_object_name, "")
            
            if action_object_name == "video_mark_out_hold":
                self.main_window.mark_out_hold_key_sequence = QKeySequence(shortcut_str)
                # ¡IMPORTANTE! No le asignamos el shortcut al QAction directamente
                # para que no intercepte el evento de teclado globalmente.
                # El QAction sigue existiendo para ser listado en el diálogo de config.
                action.setShortcut(QKeySequence()) # Asignar una secuencia vacía
            else:
                try:
                    action.setShortcut(QKeySequence(shortcut_str))
                except Exception as e:
                    print(f"Error al aplicar shortcut '{shortcut_str}' a la acción '{action.objectName()}': {e}")
        
        # Notify relevant widgets if they need to update internal key listeners
        if hasattr(self.main_window, 'videoPlayerWidget'):
            self.main_window.videoPlayerWidget.update_key_listeners()
        if hasattr(self.main_window, 'tableWindow'):
            self.main_window.tableWindow.update_key_listeners()
        if hasattr(self.main_window, 'videoWindow') and self.main_window.videoWindow:
            self.main_window.videoWindow.update_key_listeners()


    def add_configuration(self, name, shortcuts_dict):
        if name in self.configurations:
            raise ConfigurationExistsError(f"Ya existe una configuración con el nombre '{name}'.")
        self.configurations[name] = shortcuts_dict # shortcuts_dict is a_config[action_obj_name] = shortcut_str
        self.save_shortcuts()
        self.refresh_shortcuts_menu() # Refresh menu to show new config
        return True

    def delete_configuration(self, name):
        if name == "default":
            QMessageBox.warning(self.main_window, "Error", "No se puede eliminar la configuración 'default'.")
            return False
        if name in self.configurations:
            del self.configurations[name]
            if self.current_config == name: # If current config is deleted, revert to default
                self.current_config = "default"
                self.apply_shortcuts("default")
            self.save_shortcuts()
            self.refresh_shortcuts_menu()
            return True
        QMessageBox.warning(self.main_window, "Error", f"Configuración '{name}' no encontrada.")
        return False

    def refresh_shortcuts_menu(self):
        # This will re-create the shortcuts menu part in MainWindow
        self.main_window.create_shortcuts_menu(self.main_window.menuBar())

    def update_configuration(self, name, shortcuts_dict):
        if name not in self.configurations:
            # This case should ideally be handled by "Save As" logic in ShortcutConfigDialog
            # or by ensuring 'name' exists (e.g., when editing an existing config)
            # For now, let's assume 'name' exists if we are "updating"
            # A more robust approach might be:
            # self.configurations[name] = shortcuts_dict
            # self.save_shortcuts()
            # return True
            QMessageBox.warning(self.main_window, "Error", f"Configuración '{name}' no encontrada para actualizar.")
            return False
        
        self.configurations[name] = shortcuts_dict
        self.save_shortcuts()
        if name == self.current_config: # If current config updated, re-apply
            self.apply_shortcuts(name)
        self.refresh_shortcuts_menu() # In case name changed, etc. (though name doesn't change here)
        return True