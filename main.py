# main.py
import sys
import traceback
import json
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QSplitter, QDialog, QInputDialog,
    QMessageBox, QFileDialog
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

STYLES_BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'guion_editor', 'styles'))

def load_stylesheet_content(filename: str) -> str:
    css_path = os.path.join(STYLES_BASE_PATH, filename)
    if not os.path.exists(css_path):
        print(f"Advertencia: Stylesheet no encontrado en {css_path}")
        return ""
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error al cargar stylesheet {filename}: {e}")
        return ""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor de Guion con Video")
        self.setGeometry(100, 100, 1600, 900)

        self.trim_value = 0
        self.font_size = 9
        self.guion_manager = GuionManager()
        self.actions = {} 

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.videoPlayerWidget = VideoPlayerWidget(get_icon_func=get_icon, main_window=self)
        self.splitter.addWidget(self.videoPlayerWidget)

        self.tableWindow = TableWindow(self.videoPlayerWidget, main_window=self, guion_manager=self.guion_manager, get_icon_func=get_icon)
        self.splitter.addWidget(self.tableWindow)
        layout.addWidget(self.splitter)

        # Establecer referencia de TableWindow en VideoPlayerWidget para subtítulos
        self.videoPlayerWidget.set_table_window_reference(self.tableWindow)


        self.recent_files = self.load_recent_files()
        self.mark_out_hold_key_sequence = QKeySequence("F6")
        self.create_all_actions()

        self.videoPlayerWidget.detach_requested.connect(self.detach_video)
        self.tableWindow.in_out_signal.connect(self.handle_set_position)
        self.videoWindow = None

        self.create_menu_bar(exclude_shortcuts=True)
        self.shortcut_manager = ShortcutManager(self)
        self.create_shortcuts_menu(self.menuBar())

        self.tableWindow.setFocus()
        self._update_initial_undo_redo_actions_state()


    def _update_initial_undo_redo_actions_state(self):
        if hasattr(self.tableWindow, 'undo_stack'):
            if "edit_undo" in self.actions:
                 self.actions["edit_undo"].setEnabled(self.tableWindow.undo_stack.canUndo())
            if "edit_redo" in self.actions:
                 self.actions["edit_redo"].setEnabled(self.tableWindow.undo_stack.canRedo())

    def create_all_actions(self):
        # File Menu Actions
        self.add_managed_action("Abrir Video", self.open_video_file, "Ctrl+O", "open_video_icon.svg", "file_open_video")
        self.add_managed_action("Cargar M+E (Audio)", self.load_me_audio_file, "Ctrl+Shift+M", "load_audio_icon.svg", "file_load_me")
        self.add_managed_action("Abrir Guion (DOCX)", self.tableWindow.open_docx_dialog, "Ctrl+G", "open_document_icon.svg", "file_open_docx")
        self.add_managed_action("Exportar Guion a Excel", self.tableWindow.export_to_excel_dialog, "Ctrl+E", "export_excel_icon.svg", "file_export_excel")
        self.add_managed_action("Importar Guion desde Excel", self.tableWindow.import_from_excel_dialog, "Ctrl+I", "import_excel_icon.svg", "file_import_excel")
        self.add_managed_action("Guardar Guion como JSON", self.tableWindow.save_to_json_dialog, "Ctrl+S", "save_json_icon.svg", "file_save_json")
        self.add_managed_action("Cargar Guion desde JSON", self.tableWindow.load_from_json_dialog, "Ctrl+D", "load_json_icon.svg", "file_load_json") # Nota: Ctrl+L estaba en shortcut_manager, lo cambio a Ctrl+D para evitar conflicto con abrir recientes o algo así

        # Edit Menu Actions
        self.add_managed_action("Deshacer", self.undo_action, "Ctrl+Z", "undo_icon.svg", "edit_undo")
        self.add_managed_action("Rehacer", self.redo_action, "Ctrl+Y", "redo_icon.svg", "edit_redo") # Ctrl+Y es más común para rehacer

        self.add_managed_action("Agregar Línea", self.tableWindow.add_new_row, "Ctrl+N", "add_row_icon.svg", "edit_add_row")
        self.add_managed_action("Eliminar Fila", self.tableWindow.remove_row, "Ctrl+Del", "delete_row_icon.svg", "edit_delete_row")
        self.add_managed_action("Mover Arriba", self.tableWindow.move_row_up, "Alt+Up", "move_up_icon.svg", "edit_move_up")
        self.add_managed_action("Mover Abajo", self.tableWindow.move_row_down, "Alt+Down", "move_down_icon.svg", "edit_move_down")
        self.add_managed_action("Ajustar Diálogos", self.tableWindow.adjust_dialogs, None, "adjust_dialogs_icon.svg", "edit_adjust_dialogs")
        self.add_managed_action("Separar Intervención", self.tableWindow.split_intervention, "Alt+S", "split_intervention_icon.svg", "edit_split_intervention")
        self.add_managed_action("Juntar Intervenciones", self.tableWindow.merge_interventions, "Alt+M", "merge_intervention_icon.svg", "edit_merge_interventions")
        self.add_managed_action("Ver Reparto Completo", self.open_cast_window, None, "view_cast_icon.svg", "edit_view_cast")
        self.add_managed_action("Buscar y Reemplazar", self.open_find_replace_dialog, "Ctrl+F", "find_replace_icon.svg", "edit_find_replace")
        self.add_managed_action("Copiar IN/OUT a Siguiente", self.tableWindow.copy_in_out_to_next, "Ctrl+B", "copy_in_out_icon.svg", "edit_copy_in_out")
        self.add_managed_action("Incrementar Escena", self.change_scene, "Ctrl+R", "change_scene_icon.svg", "edit_increment_scene")

        # Config Menu Actions
        self.add_managed_action("Configuración App", self.open_config_dialog, "Ctrl+K", "settings_icon.svg", "config_app_settings")

        # Shortcuts Menu Actions
        self.add_managed_action("Configurar Shortcuts", self.open_shortcut_config_dialog, None, "configure_shortcuts_icon.svg", "config_shortcuts_dialog")

        # Video Player Actions
        self.add_managed_action("Video: Reproducir/Pausar", self.videoPlayerWidget.toggle_play, "F8", None, "video_toggle_play")
        self.add_managed_action("Video: Retroceder", lambda: self.videoPlayerWidget.change_position(-5000), "F7", None, "video_rewind")
        self.add_managed_action("Video: Avanzar", lambda: self.videoPlayerWidget.change_position(5000), "F9", None, "video_forward")
        self.add_managed_action("Video: Marcar IN", self.videoPlayerWidget.mark_in, "F5", None, "video_mark_in")

        action_mark_out_hold = QAction("Video: Marcar OUT (Mantener)", self)
        action_mark_out_hold.setObjectName("video_mark_out_hold")
        action_mark_out_hold.setShortcut(QKeySequence("F6")) # Default, pero gestionado por ShortcutManager
        self.actions["video_mark_out_hold"] = action_mark_out_hold
        self.addAction(action_mark_out_hold) # Necesario para que el shortcut global funcione

    def add_managed_action(self, text: str, slot, default_shortcut: str = None, icon_name: str = None, object_name: str = None):
        if not object_name: # Generar object_name si no se provee
            object_name = text.lower().replace("&", "").replace(" ", "_").replace("/", "_").replace(":", "").replace("(", "").replace(")", "")

        action = QAction(text, self)
        action.setObjectName(object_name)
        if icon_name:
            action.setIcon(get_icon(icon_name))
        
        # El shortcut se establecerá por ShortcutManager, pero podemos tener un default visual aquí
        if default_shortcut: 
            action.setShortcut(QKeySequence(default_shortcut)) # Será sobrescrito por ShortcutManager

        if slot:
            action.triggered.connect(slot)

        self.actions[object_name] = action
        # self.addAction(action) # No agregar directamente a QMainWindow si es para menús, se añaden a los menús.
                                # Pero si son shortcuts globales sin menú, sí es necesario.
                                # Para "video_mark_out_hold" se hizo, para otros no porque están en menús.
                                # Por consistencia y para que los shortcuts siempre funcionen incluso si el menú no está visible,
                                # es buena práctica añadir todas las acciones que tienen shortcuts a la ventana.
        if default_shortcut: # Solo añadir a la ventana si tiene shortcut y no es solo de menú
            self.addAction(action)
        return action

    def create_menu_bar(self, exclude_shortcuts=False):
        menuBar = self.menuBar()
        menuBar.clear() # Limpiar menú existente si se llama múltiples veces (ej. por ShortcutManager)
        self.create_file_menu(menuBar)
        self.create_edit_menu(menuBar)
        self.create_config_menu(menuBar)
        if not exclude_shortcuts:
            self.create_shortcuts_menu(menuBar)

    def create_file_menu(self, menuBar):
        fileMenu = menuBar.addMenu("&Archivo")
        fileMenu.addAction(self.actions["file_open_video"])
        fileMenu.addAction(self.actions["file_load_me"])
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
        if "edit_undo" in self.actions: editMenu.addAction(self.actions["edit_undo"])
        if "edit_redo" in self.actions: editMenu.addAction(self.actions["edit_redo"])
        editMenu.addSeparator()

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
        configMenu = menuBar.addMenu("&Herramientas") # Cambiado de Config a Herramientas
        configMenu.addAction(self.actions["config_app_settings"])

    def create_shortcuts_menu(self, menuBar):
        # Eliminar menú de shortcuts si ya existe para evitar duplicados al refrescar
        for action_menu_item in menuBar.actions():
            if action_menu_item.menu() and action_menu_item.menu().title() == "&Shortcuts":
                menuBar.removeAction(action_menu_item)
                break # Asumimos que solo hay uno

        shortcutsMenu = menuBar.addMenu("&Shortcuts")
        shortcutsMenu.addAction(self.actions["config_shortcuts_dialog"])

        load_config_menu = shortcutsMenu.addMenu("Cargar Configuración de Shortcuts")
        load_config_menu.setIcon(get_icon("load_config_icon.svg"))
        if hasattr(self, 'shortcut_manager'): # Asegurar que shortcut_manager exista
            for config_name in self.shortcut_manager.configurations.keys():
                action = QAction(config_name, self)
                action.triggered.connect(lambda checked, name=config_name: self.shortcut_manager.apply_shortcuts(name))
                load_config_menu.addAction(action)
        
        # "Eliminar Configuración" debería estar dentro del menú de Shortcuts
        # El objeto "config_delete_shortcut_profile" ya se crea en create_all_actions
        if "config_delete_shortcut_profile" in self.actions:
            shortcutsMenu.addAction(self.actions["config_delete_shortcut_profile"])
        else: # Si no existe, crearla específicamente para el menú (menos ideal que esté en create_all_actions)
            delete_config_action = self.add_managed_action(
                "Eliminar Configuración de Shortcuts",
                self.delete_shortcut_configuration,
                None,
                "delete_config_icon.svg",
                "config_delete_shortcut_profile"
            )
            shortcutsMenu.addAction(delete_config_action)


    def update_recent_files_menu(self):
        if not hasattr(self, 'recent_files_menu') or not self.recent_files_menu:
            # Podría pasar si se llama antes de que el menú esté completamente creado
            return
            
        self.recent_files_menu.clear()
        for file_path in self.recent_files:
            action = QAction(os.path.basename(file_path), self)
            action.setIcon(get_icon("open_document_icon.svg")) # O un icono de archivo genérico
            action.setToolTip(file_path)
            action.triggered.connect(lambda checked, path=file_path: self.open_recent_file(path))
            self.recent_files_menu.addAction(action)

    def open_cast_window(self):
        from guion_editor.widgets.cast_window import CastWindow
        self.cast_window = CastWindow(self.tableWindow.pandas_model, parent_main_window=self)
        self.cast_window.show()

    def open_find_replace_dialog(self):
        from guion_editor.widgets.find_replace_dialog import FindReplaceDialog
        dialog = FindReplaceDialog(self.tableWindow, get_icon_func=get_icon)
        dialog.exec()

    def open_recent_file(self, file_path):
        if os.path.exists(file_path):
            ext = os.path.splitext(file_path.lower())[1]
            if ext in ('.mp4', '.avi', '.mkv', '.mov'):
                self.videoPlayerWidget.load_video(file_path)
            elif ext == '.xlsx':
                self.tableWindow.load_from_excel_path(file_path)
            elif ext == '.json':
                self.tableWindow.load_from_json_path(file_path)
            elif ext == '.docx':
                self.tableWindow.load_from_docx_path(file_path)
            else:
                QMessageBox.warning(self, "Error", "Tipo de archivo no soportado para abrir desde recientes.")
            self.add_to_recent_files(file_path) # Actualizar orden incluso si ya estaba
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

    def load_me_audio_file(self):
        if self.videoPlayerWidget.media_player.source().isEmpty():
            QMessageBox.information(self, "Cargar M+E", "Por favor, cargue primero un archivo de video.")
            return

        file_name, _ = QFileDialog.getOpenFileName(self, "Cargar Audio M+E", "", "Archivos de Audio (*.wav *.mp3);;Todos los archivos (*.*)")
        if file_name:
            self.videoPlayerWidget.load_me_file(file_name)
            self.add_to_recent_files(file_name) # También añadir M+E a recientes


    def add_to_recent_files(self, file_path):
        abs_file_path = os.path.abspath(file_path) # Normalizar path
        if abs_file_path in self.recent_files:
            self.recent_files.remove(abs_file_path)
        self.recent_files.insert(0, abs_file_path)
        self.recent_files = self.recent_files[:10] # Limitar a 10 recientes
        self.save_recent_files()
        self.update_recent_files_menu()

    def load_recent_files(self):
        try:
            # Guardar recent_files.json en el directorio del script main.py
            base_dir = os.path.dirname(os.path.abspath(__file__))
            recent_files_path = os.path.join(base_dir, 'recent_files.json')

            if os.path.exists(recent_files_path):
                with open(recent_files_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar archivos recientes: {str(e)}")
            return []

    def save_recent_files(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            recent_files_path = os.path.join(base_dir, 'recent_files.json')

            with open(recent_files_path, 'w', encoding='utf-8') as f:
                json.dump(self.recent_files, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al guardar archivos recientes: {str(e)}")


    def apply_font_size(self):
        self.tableWindow.apply_font_size_to_dialogs(self.font_size)
        self.videoPlayerWidget.update_fonts(self.font_size)

    def open_shortcut_config_dialog(self):
        dialog = ShortcutConfigDialog(self.shortcut_manager, get_icon_func=get_icon)
        dialog.exec()

    def delete_shortcut_configuration(self):
        configs = list(self.shortcut_manager.configurations.keys())
        if "default" in configs:
            configs.remove("default") # No permitir borrar 'default'
        
        if not configs:
            QMessageBox.information(self, "Información", "No hay configuraciones personalizadas para eliminar.")
            return

        config_name, ok = QInputDialog.getItem(self, 
                                               "Eliminar Configuración de Shortcut", 
                                               "Seleccione una configuración para eliminar:", 
                                               configs, 0, False)
        if ok and config_name:
            confirm = QMessageBox.question(self, "Confirmar", 
                                           f"¿Está seguro de que desea eliminar la configuración de shortcuts '{config_name}'?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No) # Default a No
            if confirm == QMessageBox.StandardButton.Yes:
                if self.shortcut_manager.delete_configuration(config_name):
                    QMessageBox.information(self, "Éxito", f"Configuración '{config_name}' eliminada exitosamente.")
                    # El refresh del menú ya lo hace delete_configuration si tiene éxito.
                # else: El propio shortcut_manager mostrará un error si falla.


    def open_video_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, 
                                                   "Abrir Video", "", 
                                                   "Videos (*.mp4 *.avi *.mkv *.mov);;Todos los archivos (*.*)")
        if file_name:
            self.videoPlayerWidget.load_video(file_name)
            self.add_to_recent_files(file_name)

    def detach_video(self, video_widget_instance):
        if self.videoWindow is not None: # Ya está separado
            return
        try:
            widget_index_in_splitter = -1
            for i in range(self.splitter.count()):
                if self.splitter.widget(i) == video_widget_instance:
                    widget_index_in_splitter = i
                    break
            
            # El widget de video se quita del splitter al reparentarlo a VideoWindow
            # No es necesario llamara a video_widget_instance.setParent(None) explícitamente
            # ya que QWidget lo hace cuando se añade a un nuevo layout/padre.

            if widget_index_in_splitter != -1:
                # video_widget_instance ya es self.videoPlayerWidget
                self.videoWindow = VideoWindow(video_widget_instance, get_icon_func=get_icon, main_window=self)
                
                # Pasar acciones relevantes a la ventana flotante
                actions_for_detached_video = [
                    "video_toggle_play", "video_rewind", "video_forward", 
                    "video_mark_in", "video_mark_out_hold" 
                ]
                for action_name in actions_for_detached_video:
                    if action_name in self.actions:
                        self.videoWindow.addAction(self.actions[action_name])

                self.videoWindow.close_detached.connect(self.attach_video)
                self.videoWindow.show()
                # self.videoPlayerWidget.setFocus() # La ventana flotante debería manejar su foco
            else:
                 QMessageBox.warning(self,"Error", "El widget de video a separar no se encontró en el splitter.")
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al separar el video: {str(e)}\n{traceback.format_exc()}")


    def attach_video(self):
        if self.videoWindow is None: # No está separado
            return
        try:
            video_widget_instance = self.videoWindow.video_widget # Es self.videoPlayerWidget
            
            # Quitar las acciones que se pasaron a la ventana flotante para evitar duplicados
            # Esto puede ser opcional si los shortcuts no entran en conflicto o si se gestionan bien
            actions_for_detached_video = [
                "video_toggle_play", "video_rewind", "video_forward",
                "video_mark_in", "video_mark_out_hold"
            ]
            for action_name in actions_for_detached_video:
                if action_name in self.actions:
                    self.videoWindow.removeAction(self.actions[action_name])

            self.splitter.insertWidget(0, video_widget_instance) # Volver a añadir al splitter
            # video_widget_instance.setParent(self.splitter) # insertWidget ya hace esto

            self.videoWindow.close_detached.disconnect(self.attach_video)
            # self.videoWindow.close() # No es necesario, closeEvent ya se ha gestionado
            self.videoWindow = None # Liberar referencia

            # Restaurar tamaños del splitter
            total_width = self.splitter.width()
            if total_width > 0 and self.splitter.count() == 2: # Asegurar que hay 2 widgets
                 self.splitter.setSizes([total_width // 2, total_width // 2])
            else: # Fallback si algo va mal
                 self.splitter.setSizes([100,100]) # O un tamaño por defecto
            
            self.videoPlayerWidget.setFocus() # Devolver foco al player en la ventana principal
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al adjuntar el video: {str(e)}\n{traceback.format_exc()}")


    def handle_set_position(self, action_type_str, position_ms):
        try:
            adjusted_position = max(position_ms - self.trim_value, 0)
            self.videoPlayerWidget.set_position_public(adjusted_position)
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al establecer la posición del video: {str(e)}")

    def change_scene(self):
        self.tableWindow.change_scene()

    def undo_action(self):
        if self.tableWindow and hasattr(self.tableWindow, 'undo_stack'):
            self.tableWindow.undo_stack.undo()

    def redo_action(self):
        if self.tableWindow and hasattr(self.tableWindow, 'undo_stack'):
            self.tableWindow.undo_stack.redo()

    def closeEvent(self, event):
        if hasattr(self.tableWindow, 'undo_stack') and not self.tableWindow.undo_stack.isClean():
            reply = QMessageBox.question(self, 
                                         "Guardar cambios", 
                                         "Hay cambios sin guardar. ¿Desea guardar el guion antes de salir?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel) # Default a Cancelar
            if reply == QMessageBox.StandardButton.Save:
                saved_successfully = False
                # Intentar guardar al path actual si existe, sino pedir uno nuevo
                if self.tableWindow.current_script_path and self.tableWindow.current_script_path.endswith(".json"):
                    # Aquí deberíamos llamar a un método "save_current_json_script" que no pide diálogo si ya hay path
                    # Por ahora, save_to_json_dialog pedirá confirmación si ya existe.
                    self.guion_manager.save_to_json(self.tableWindow.current_script_path, self.tableWindow.pandas_model.dataframe(), self.tableWindow._get_header_data_from_ui())
                    saved_successfully = True # Asumimos que si no hay excepción, se guardó.
                elif self.tableWindow.current_script_path and self.tableWindow.current_script_path.endswith(".xlsx"):
                    self.guion_manager.save_to_excel(self.tableWindow.current_script_path, self.tableWindow.pandas_model.dataframe(), self.tableWindow._get_header_data_from_ui())
                    saved_successfully = True
                else: # No hay path actual o no es tipo conocido, pedir diálogo
                    saved_successfully = self.tableWindow.save_to_json_dialog() # O export_to_excel_dialog()

                if saved_successfully:
                    event.accept()
                else: # El usuario canceló el diálogo de guardar o hubo un error
                    event.ignore() 
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else: # Cancel
                event.ignore()
        else:
            event.accept()
            
    def get_icon_func_for_dialogs(self):
        return get_icon

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(error_message) # Siempre imprimir en consola

    user_message = f"Ocurrió un error inesperado:\n\nTipo: {exc_type.__name__}\nMensaje: {exc_value}\n\n"
    user_message += "Por favor, reporte este error. Puede encontrar más detalles en la consola."

    # Intentar mostrar el error en un QMessageBox si la app está corriendo
    if QApplication.instance():
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Error Inesperado")
            # Mostrar solo la parte principal del mensaje en el texto, el resto como informativo
            msg_box.setText(user_message.split('\n\n')[0]) 
            msg_box.setInformativeText('\n\n'.join(user_message.split('\n\n')[1:]))
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
        except Exception as e_msgbox: # Si falla el QMessageBox
            print(f"Error al mostrar QMessageBox: {e_msgbox}")
            print("Error original:", error_message) # Imprimir el error original de nuevo
    else: # Si QApplication no existe, solo imprimir en consola
        print("Error original (QApplication no disponible):", error_message)


def main():
    sys.excepthook = handle_exception # Configurar el manejador de excepciones global
    app = QApplication(sys.argv)

    main_css_content = load_stylesheet_content("main.css")
    if main_css_content:
        app.setStyleSheet(main_css_content)
    else:
        print("No se pudo cargar main.css globalmente.")


    mainWindow = MainWindow()
    mainWindow.showMaximized()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()