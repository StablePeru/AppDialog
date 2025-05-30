# main.py
import sys
import traceback
import json
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QSplitter, QDialog, QInputDialog,
    QMessageBox
)
from PyQt6.QtCore import Qt, QSize 
from PyQt6.QtGui import QAction, QKeySequence, QIcon 

from guion_editor.widgets.video_player_widget import VideoPlayerWidget
from guion_editor.widgets.table_window import TableWindow
from guion_editor.widgets.video_window import VideoWindow
from guion_editor.widgets.config_dialog import ConfigDialog
from guion_editor.widgets.shortcut_config_dialog import ShortcutConfigDialog
from guion_editor.utils.shortcut_manager import ShortcutManager
from guion_editor.utils.guion_manager import GuionManager

ICON_CACHE = {} 
ICON_BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'guion_editor', 'styles', 'icons'))

def get_icon(icon_name: str) -> QIcon:
    if icon_name in ICON_CACHE:
        return ICON_CACHE[icon_name]
    
    icon_path = os.path.join(ICON_BASE_PATH, icon_name)
    if not os.path.exists(icon_path):
        print(f"Advertencia: Icono no encontrado en {icon_path}")
        return QIcon()
    
    icon = QIcon(icon_path)
    ICON_CACHE[icon_name] = icon
    return icon

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor de Guion con Video")
        self.setGeometry(100, 100, 1600, 900)

        self.trim_value = 0
        self.font_size = 9
        self.guion_manager = GuionManager()
        self.actions = {} # Central dictionary for all actions

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        # Pass main_window reference to VideoPlayerWidget
        self.videoPlayerWidget = VideoPlayerWidget(get_icon_func=get_icon, main_window=self) 
        self.splitter.addWidget(self.videoPlayerWidget)

        self.tableWindow = TableWindow(self.videoPlayerWidget, main_window=self, guion_manager=self.guion_manager, get_icon_func=get_icon)
        self.splitter.addWidget(self.tableWindow)
        layout.addWidget(self.splitter)

        self.recent_files = self.load_recent_files()

        self.mark_out_hold_key_sequence = QKeySequence("F6") # Valor inicial por defecto
        
        self.create_all_actions() # Create all QActions first

        self.videoPlayerWidget.detach_requested.connect(self.detach_video)
        self.tableWindow.in_out_signal.connect(self.handle_set_position)
        self.videoWindow = None

        self.create_menu_bar(exclude_shortcuts=True) # Shortcuts applied by ShortcutManager
        self.shortcut_manager = ShortcutManager(self) # Initialize after actions are created
        self.create_shortcuts_menu(self.menuBar()) # Create menu for shortcut configs

        self.tableWindow.setFocus() # Give initial focus to table window

    def create_all_actions(self):
        # File Menu Actions
        self.add_managed_action("Abrir Video", self.open_video_file, "Ctrl+O", "open_video_icon.svg", "file_open_video")
        self.add_managed_action("Abrir Guion (DOCX)", self.tableWindow.open_docx_dialog, "Ctrl+G", "open_document_icon.svg", "file_open_docx")
        self.add_managed_action("Exportar Guion a Excel", self.tableWindow.export_to_excel_dialog, "Ctrl+E", "export_excel_icon.svg", "file_export_excel")
        self.add_managed_action("Importar Guion desde Excel", self.tableWindow.import_from_excel_dialog, "Ctrl+I", "import_excel_icon.svg", "file_import_excel")
        self.add_managed_action("Guardar Guion como JSON", self.tableWindow.save_to_json_dialog, "Ctrl+S", "save_json_icon.svg", "file_save_json")
        self.add_managed_action("Cargar Guion desde JSON", self.tableWindow.load_from_json_dialog, "Ctrl+D", "load_json_icon.svg", "file_load_json")

        # Edit Menu Actions
        self.add_managed_action("Agregar Línea", self.tableWindow.add_new_row, "Ctrl+N", "add_row_icon.svg", "edit_add_row")
        self.add_managed_action("Eliminar Fila", self.tableWindow.remove_row, "Ctrl+Del", "delete_row_icon.svg", "edit_delete_row")
        self.add_managed_action("Mover Arriba", self.tableWindow.move_row_up, "Alt+Up", "move_up_icon.svg", "edit_move_up")
        self.add_managed_action("Mover Abajo", self.tableWindow.move_row_down, "Alt+Down", "move_down_icon.svg", "edit_move_down")
        self.add_managed_action("Ajustar Diálogos", self.tableWindow.adjust_dialogs, None, "adjust_dialogs_icon.svg", "edit_adjust_dialogs")
        self.add_managed_action("Separar Intervención", self.tableWindow.split_intervention, "Alt+S", "split_intervention_icon.svg", "edit_split_intervention") # Changed shortcut
        self.add_managed_action("Juntar Intervenciones", self.tableWindow.merge_interventions, "Alt+M", "merge_intervention_icon.svg", "edit_merge_interventions") # Changed shortcut
        self.add_managed_action("Ver Reparto Completo", self.open_cast_window, None, "view_cast_icon.svg", "edit_view_cast")
        self.add_managed_action("Buscar y Reemplazar", self.open_find_replace_dialog, "Ctrl+F", "find_replace_icon.svg", "edit_find_replace")
        self.add_managed_action("Copiar IN/OUT a Siguiente", self.tableWindow.copy_in_out_to_next, "Ctrl+B", "copy_in_out_icon.svg", "edit_copy_in_out")
        self.add_managed_action("Incrementar Escena", self.change_scene, "Ctrl+R", "change_scene_icon.svg", "edit_increment_scene") # Added icon, was 'change_scene'

        # Config Menu Actions
        self.add_managed_action("Configuración App", self.open_config_dialog, "Ctrl+K", "settings_icon.svg", "config_app_settings")

        # Shortcuts Menu Actions (meta-actions for managing shortcuts)
        self.add_managed_action("Configurar Shortcuts", self.open_shortcut_config_dialog, None, "configure_shortcuts_icon.svg", "config_shortcuts_dialog")
        # "Cargar Configuración" (submenu) and "Eliminar Configuración" are handled slightly differently or created in create_shortcuts_menu

        # Video Player Actions (not in main menu, but configurable shortcuts)
        self.add_managed_action("Video: Reproducir/Pausar", self.videoPlayerWidget.toggle_play, "F8", None, "video_toggle_play")
        self.add_managed_action("Video: Retroceder", lambda: self.videoPlayerWidget.change_position(-5000), "F7", None, "video_rewind")
        self.add_managed_action("Video: Avanzar", lambda: self.videoPlayerWidget.change_position(5000), "F9", None, "video_forward")
        self.add_managed_action("Video: Marcar IN", self.videoPlayerWidget.mark_in, "F5", None, "video_mark_in")
        
        # Special action for "Mark OUT (Hold)" - no direct trigger, shortcut used by event handlers
        action_mark_out_hold = QAction("Video: Marcar OUT (Mantener)", self)
        action_mark_out_hold.setObjectName("video_mark_out_hold")
        action_mark_out_hold.setShortcut(QKeySequence("F6")) # Default shortcut
        self.actions["video_mark_out_hold"] = action_mark_out_hold
        self.addAction(action_mark_out_hold) # Add to window to make shortcut potentially active

    def add_managed_action(self, text: str, slot, default_shortcut: str = None, icon_name: str = None, object_name: str = None):
        if not object_name:
            # Basic generation for object_name if not provided
            object_name = text.lower().replace(" ", "_").replace("&", "").replace("/", "_").replace(":", "")
        
        action = QAction(text, self)
        action.setObjectName(object_name)
        if icon_name:
            action.setIcon(get_icon(icon_name))
        if default_shortcut:
            action.setShortcut(QKeySequence(default_shortcut))
        
        # Connect slot only if it's not None. Some actions might be placeholders for shortcuts.
        if slot:
            action.triggered.connect(slot)
        
        self.actions[object_name] = action
        self.addAction(action) # Add to main window to make shortcut potentially active
        return action

    def create_menu_bar(self, exclude_shortcuts=False):
        menuBar = self.menuBar()
        self.create_file_menu(menuBar)
        self.create_edit_menu(menuBar)
        self.create_config_menu(menuBar)
        if not exclude_shortcuts: # This part is now mainly for the "Configure Shortcuts..." dialog itself
            self.create_shortcuts_menu(menuBar)

    def create_file_menu(self, menuBar):
        fileMenu = menuBar.addMenu("&Archivo")
        fileMenu.addAction(self.actions["file_open_video"])
        fileMenu.addAction(self.actions["file_open_docx"])
        fileMenu.addSeparator()
        fileMenu.addAction(self.actions["file_export_excel"])
        fileMenu.addAction(self.actions["file_import_excel"])
        fileMenu.addSeparator()
        fileMenu.addAction(self.actions["file_save_json"])
        fileMenu.addAction(self.actions["file_load_json"])
        fileMenu.addSeparator()
        
        self.recent_files_menu = fileMenu.addMenu("Abrir Recientemente")
        self.recent_files_menu.setIcon(get_icon("history_icon.svg")) 
        self.update_recent_files_menu()

    def create_edit_menu(self, menuBar):
        editMenu = menuBar.addMenu("&Editar")
        editMenu.addAction(self.actions["edit_add_row"])
        editMenu.addAction(self.actions["edit_delete_row"])
        editMenu.addAction(self.actions["edit_move_up"])
        editMenu.addAction(self.actions["edit_move_down"])
        editMenu.addSeparator()
        editMenu.addAction(self.actions["edit_adjust_dialogs"])
        editMenu.addAction(self.actions["edit_split_intervention"])
        editMenu.addAction(self.actions["edit_merge_interventions"])
        editMenu.addSeparator()
        editMenu.addAction(self.actions["edit_view_cast"])
        editMenu.addAction(self.actions["edit_find_replace"])
        editMenu.addSeparator()
        editMenu.addAction(self.actions["edit_copy_in_out"])
        editMenu.addAction(self.actions["edit_increment_scene"])
        
    def create_config_menu(self, menuBar):
        configMenu = menuBar.addMenu("&Herramientas") # Renamed for clarity
        configMenu.addAction(self.actions["config_app_settings"])

    def create_shortcuts_menu(self, menuBar):
        # Ensure old shortcuts menu is removed if this is called multiple times (e.g., refresh)
        for action_menu_item in menuBar.actions():
            if action_menu_item.menu() and action_menu_item.menu().title() == "&Shortcuts":
                menuBar.removeAction(action_menu_item)
                break
        
        shortcutsMenu = menuBar.addMenu("&Shortcuts")
        shortcutsMenu.addAction(self.actions["config_shortcuts_dialog"])
        
        load_config_menu = shortcutsMenu.addMenu("Cargar Configuración de Shortcuts")
        load_config_menu.setIcon(get_icon("load_config_icon.svg"))
        # Populate this dynamically based on shortcut_manager.configurations
        if hasattr(self, 'shortcut_manager'): # Check if shortcut_manager is initialized
            for config_name in self.shortcut_manager.configurations.keys():
                action = QAction(config_name, self) # Icon not typical for each item here
                action.triggered.connect(lambda checked, name=config_name: self.shortcut_manager.apply_shortcuts(name))
                load_config_menu.addAction(action)
            
        # "Eliminar Configuración" is better as a direct action
        delete_config_action = self.add_managed_action(
            "Eliminar Configuración de Shortcuts", 
            self.delete_shortcut_configuration, 
            None, 
            "delete_config_icon.svg", 
            "config_delete_shortcut_profile" # New object name
        )
        shortcutsMenu.addAction(delete_config_action)
        
    def update_recent_files_menu(self):
        self.recent_files_menu.clear()
        for file_path in self.recent_files:
            action = QAction(os.path.basename(file_path), self)
            action.setIcon(get_icon("open_document_icon.svg"))
            action.setToolTip(file_path)
            action.triggered.connect(lambda checked, path=file_path: self.open_recent_file(path))
            self.recent_files_menu.addAction(action)

    def open_cast_window(self):
        from guion_editor.widgets.cast_window import CastWindow
        self.cast_window = CastWindow(self.tableWindow.pandas_model) # Pass model directly
        self.cast_window.show()

    def open_find_replace_dialog(self):
        from guion_editor.widgets.find_replace_dialog import FindReplaceDialog
        # Pass main_window (self) if FindReplaceDialog needs access to global actions or similar
        # For now, it seems to only need tableWindow and get_icon
        dialog = FindReplaceDialog(self.tableWindow, get_icon_func=get_icon)
        dialog.exec()

    def open_recent_file(self, file_path):
        if os.path.exists(file_path):
            ext = os.path.splitext(file_path.lower())[1]
            if ext in ('.mp4', '.avi', '.mkv', '.mov'): # Added .mov
                self.videoPlayerWidget.load_video(file_path)
            elif ext == '.xlsx':
                self.tableWindow.load_from_excel_path(file_path)
            elif ext == '.json':
                self.tableWindow.load_from_json_path(file_path)
            elif ext == '.docx':
                self.tableWindow.load_from_docx_path(file_path)
            else:
                QMessageBox.warning(self, "Error", "Tipo de archivo no soportado para abrir desde recientes.")
            self.add_to_recent_files(file_path) # Refresh its position
        else:
            QMessageBox.warning(self, "Error", f"El archivo reciente '{os.path.basename(file_path)}' no existe en la ruta:\n{file_path}")
            if file_path in self.recent_files:
                self.recent_files.remove(file_path)
            self.save_recent_files()
            self.update_recent_files_menu()

    def open_config_dialog(self):
        config_dialog = ConfigDialog(
            current_trim=self.trim_value,
            current_font_size=self.font_size,
            get_icon_func=get_icon
        )
        if config_dialog.exec() == QDialog.DialogCode.Accepted:
            self.trim_value, self.font_size = config_dialog.get_values()
            self.apply_font_size()

    def add_to_recent_files(self, file_path):
        abs_file_path = os.path.abspath(file_path) # Store absolute paths
        if abs_file_path in self.recent_files:
            self.recent_files.remove(abs_file_path)
        self.recent_files.insert(0, abs_file_path)
        self.recent_files = self.recent_files[:10]
        self.save_recent_files()
        self.update_recent_files_menu()

    def load_recent_files(self):
        try:
            if os.path.exists('recent_files.json'):
                with open('recent_files.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar archivos recientes: {str(e)}")
            return []

    def save_recent_files(self):
        try:
            with open('recent_files.json', 'w', encoding='utf-8') as f:
                json.dump(self.recent_files, f, indent=2) # Added indent for readability
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al guardar archivos recientes: {str(e)}")

    def apply_font_size(self):
        # This method can be simplified if TableWindow and VideoPlayerWidget handle their own font updates
        # when a "font_size_changed" signal is emitted, or by direct calls.
        self.tableWindow.apply_font_size_to_dialogs(self.font_size)
        self.videoPlayerWidget.update_fonts(self.font_size) # Assuming this method exists/is adapted

    def open_shortcut_config_dialog(self):
        dialog = ShortcutConfigDialog(self.shortcut_manager, get_icon_func=get_icon)
        dialog.exec()
        # apply_shortcuts is now called by ShortcutManager itself when changes are made and saved.
        # If not, call it here: self.shortcut_manager.apply_shortcuts(self.shortcut_manager.current_config)

    def delete_shortcut_configuration(self): # Renamed from delete_configuration
        configs = list(self.shortcut_manager.configurations.keys())
        if "default" in configs:
            configs.remove("default") # Prevent deleting default
        if not configs:
            QMessageBox.information(self, "Información", "No hay configuraciones personalizadas para eliminar.")
            return
        config_name, ok = QInputDialog.getItem(self,"Eliminar Configuración de Shortcut","Seleccione una configuración para eliminar:",configs,0,False)
        if ok and config_name:
            confirm = QMessageBox.question(self,"Confirmar",f"¿Está seguro de que desea eliminar la configuración de shortcuts '{config_name}'?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No) # Default to No
            if confirm == QMessageBox.StandardButton.Yes:
                if self.shortcut_manager.delete_configuration(config_name):
                    QMessageBox.information(self,"Éxito",f"Configuración '{config_name}' eliminada exitosamente.")
                    # The shortcut manager should refresh the menu via its reference
                    self.shortcut_manager.refresh_shortcuts_menu() 
                # else: delete_configuration already shows a message on failure.

    def open_video_file(self):
        from PyQt6.QtWidgets import QFileDialog
        file_name, _ = QFileDialog.getOpenFileName(self,"Abrir Video","","Videos (*.mp4 *.avi *.mkv *.mov);;Todos los archivos (*.*)")
        if file_name:
            self.videoPlayerWidget.load_video(file_name)
            self.add_to_recent_files(file_name)

    def detach_video(self, video_widget_instance): # video_widget_instance is self.videoPlayerWidget
        if self.videoWindow is not None: return
        try:
            # Find video_widget_instance in splitter and remove it.
            # It's usually at index 0 if it's the first one added.
            widget_index_in_splitter = -1
            for i in range(self.splitter.count()):
                if self.splitter.widget(i) == video_widget_instance:
                    widget_index_in_splitter = i
                    break
            
            if widget_index_in_splitter != -1:
                # self.videoPlayerWidget (video_widget_instance) is taken out of the splitter.
                # Its parent will be set to None implicitly by adding it to VideoWindow.
                
                self.videoWindow = VideoWindow(video_widget_instance, get_icon_func=get_icon, main_window=self)
                
                # Add relevant QActions for shortcuts to work in the detached window
                actions_for_detached_video = [
                    "video_toggle_play", "video_rewind", "video_forward",
                    "video_mark_in", "video_mark_out_hold" # Conceptual, for key events
                ]
                for action_name in actions_for_detached_video:
                    if action_name in self.actions:
                        self.videoWindow.addAction(self.actions[action_name])
                
                self.videoWindow.close_detached.connect(self.attach_video)
                self.videoWindow.show()
                self.videoPlayerWidget.setFocus() # Focus the player in the new window
            else:
                 QMessageBox.warning(self,"Error", "El widget de video a separar no se encontró en el splitter.")
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al separar el video: {str(e)}\n{traceback.format_exc()}")

    def attach_video(self):
        if self.videoWindow is None: return
        try:
            video_widget_instance = self.videoWindow.video_widget # This is self.videoPlayerWidget
            
            # Remove actions that were added for the detached state to avoid conflicts
            # or rely on Qt's parent-child action propagation. Simpler to just re-add to splitter.
            
            self.splitter.insertWidget(0, video_widget_instance) # Add it back
            video_widget_instance.setParent(self.splitter) # Explicitly set parent

            self.videoWindow.close_detached.disconnect(self.attach_video) # Disconnect to prevent issues on close
            self.videoWindow.close() 
            self.videoWindow = None
            
            total_width = self.splitter.width()
            if total_width > 0 and self.splitter.count() == 2:
                 self.splitter.setSizes([total_width // 2, total_width // 2])
            else:
                 self.splitter.setSizes([100,100]) # Fallback
            self.videoPlayerWidget.setFocus() # Focus player in main window
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al adjuntar el video: {str(e)}\n{traceback.format_exc()}")

    def handle_set_position(self, action_type_str, position_ms): # Renamed action to action_type_str
        try:
            adjusted_position = max(position_ms - self.trim_value, 0)
            self.videoPlayerWidget.set_position_public(adjusted_position)
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al establecer la posición del video: {str(e)}")

    def change_scene(self):
        self.tableWindow.change_scene()

    def closeEvent(self, event):
        if self.tableWindow.unsaved_changes:
            reply = QMessageBox.question(self,"Guardar cambios","Hay cambios sin guardar. ¿Desea exportar el guion antes de salir?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel) # Default to Cancel
            if reply == QMessageBox.StandardButton.Save:
                try:
                    if self.tableWindow.export_to_excel_dialog(): 
                        event.accept()
                    else: 
                        event.ignore() # Export was cancelled by user
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo guardar el guion: {str(e)}")
                    event.ignore()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else: # Cancel
                event.ignore()
        else:
            event.accept()

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(error_message) 
    
    # Construct a simpler message for the user
    user_message = f"Ocurrió un error inesperado:\n\nTipo: {exc_type.__name__}\nMensaje: {exc_value}\n\n"
    user_message += "Por favor, reporte este error. Puede encontrar más detalles en la consola."
    
    # Avoid creating a QMessageBox if QApplication is not running or if it's a QDialog related error during its own destruction.
    if QApplication.instance():
        try:
            # Create a detached QMessageBox to avoid issues if the main window is problematic
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Error Inesperado")
            msg_box.setText(user_message.split('\n\n')[0]) # Short summary
            msg_box.setInformativeText('\n\n'.join(user_message.split('\n\n')[1:]))
            # msg_box.setDetailedText(error_message) # This can be too much for a user
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
        except Exception as e_msgbox:
            print(f"Error al mostrar QMessageBox: {e_msgbox}") # Log msgbox error
            print("Error original:", error_message) # Ensure original error is still printed
    else:
        print("Error original (QApplication no disponible):", error_message)


def main():
    sys.excepthook = handle_exception
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.showMaximized() # Show maximized for better layout
    sys.exit(app.exec())

if __name__ == "__main__":
    main()