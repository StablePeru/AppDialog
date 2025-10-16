# main.py
import sys
import traceback
import json
import os
# -> NUEVO: Importar time para obtener la fecha de modificación del archivo
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QSplitter, QDialog, QInputDialog,
    QMessageBox, QFileDialog
)
# -> MODIFICADO: Importar QTimer para el autoguardado y QSettings para la persistencia
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings
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
    # -> NUEVO: Constante para el archivo de recuperación
    RECOVERY_FILE_NAME = "autosave_recovery.json"
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor de Guion con Video")
        self.setGeometry(100, 100, 1600, 900)

        self.trim_value = 0
        self.font_size = 9
        self.line_length = 60
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

        # -> NUEVO: Comprobar si hay un archivo de recuperación al iniciar
        self._check_for_recovery_file()
        # -> NUEVO: Configurar y arrancar el temporizador de autoguardado
        self._setup_autosave()

        # -> INICIO: NUEVO BLOQUE PARA RESTAURAR LA CONFIGURACIÓN
        self._load_settings()
        # -> FIN: NUEVO BLOQUE


    # -> NUEVO: Método para obtener la ruta del archivo de recuperación
    def _get_recovery_file_path(self) -> str:
        """Devuelve la ruta completa al archivo de recuperación."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, self.RECOVERY_FILE_NAME)

    # -> NUEVO: Método para configurar el temporizador de autoguardado
    def _setup_autosave(self):
        """Configura e inicia el QTimer para el autoguardado."""
        self.autosave_timer = QTimer(self)
        # Guardar cada 2 minutos (120000 milisegundos)
        self.autosave_timer.setInterval(120000) 
        self.autosave_timer.timeout.connect(self._perform_autosave)
        self.autosave_timer.start()
        print("Autoguardado activado (cada 2 minutos si hay cambios).")

    # -> NUEVO: Método que realiza el autoguardado
    def _perform_autosave(self):
        """Guarda el estado actual en el archivo de recuperación si hay cambios."""
        # Solo autoguarda si hay cambios sin guardar en el stack
        if hasattr(self.tableWindow, 'undo_stack') and not self.tableWindow.undo_stack.isClean():
            recovery_path = self._get_recovery_file_path()
            try:
                current_df = self.tableWindow.pandas_model.dataframe()
                header_data = self.tableWindow._get_header_data_from_ui()
                self.guion_manager.save_to_json(recovery_path, current_df, header_data)
                # Opcional: mostrar un mensaje en la barra de estado
                if self.statusBar():
                    self.statusBar().showMessage("Progreso autoguardado.", 3000)
            except Exception as e:
                print(f"Error durante el autoguardado: {e}")

    # -> NUEVO: Método para comprobar y ofrecer la recuperación
    def _check_for_recovery_file(self):
        """Comprueba si existe un archivo de recuperación y pregunta al usuario si desea restaurarlo."""
        recovery_path = self._get_recovery_file_path()
        if os.path.exists(recovery_path):
            try:
                last_modified_timestamp = os.path.getmtime(recovery_path)
                last_modified_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_modified_timestamp))
                
                reply = QMessageBox.question(self,
                                             "Recuperar Sesión",
                                             f"Se ha encontrado un archivo de recuperación de una sesión anterior no guardada.\n"
                                             f"Última modificación: {last_modified_str}\n\n"
                                             "¿Desea restaurar el trabajo?",
                                             QMessageBox.StandardButton.Restore | QMessageBox.StandardButton.Discard,
                                             QMessageBox.StandardButton.Restore)

                if reply == QMessageBox.StandardButton.Restore:
                    self.tableWindow.load_from_json_path(recovery_path)
                    # Importante: Marcar el estado como "sucio" porque este trabajo recuperado
                    # aún no ha sido guardado permanentemente por el usuario.
                    self.tableWindow.undo_stack.setClean(False)
                    QMessageBox.information(self, "Éxito", "El guion ha sido restaurado desde la última copia autoguardada.")
                else:
                    # Si el usuario descarta, eliminamos el archivo para no volver a preguntar.
                    self._delete_recovery_file()
            except Exception as e:
                QMessageBox.warning(self, "Error de Recuperación", f"No se pudo procesar el archivo de recuperación: {e}")
                self._delete_recovery_file()
                
    # -> NUEVO: Método para eliminar el archivo de recuperación
    def _delete_recovery_file(self):
        """Elimina el archivo de autoguardado de forma segura."""
        recovery_path = self._get_recovery_file_path()
        try:
            if os.path.exists(recovery_path):
                os.remove(recovery_path)
        except OSError as e:
            print(f"Error al eliminar el archivo de recuperación: {e}")


    def _update_initial_undo_redo_actions_state(self):
        if hasattr(self.tableWindow, 'undo_stack'):
            if "edit_undo" in self.actions:
                 self.actions["edit_undo"].setEnabled(self.tableWindow.undo_stack.canUndo())
            if "edit_redo" in self.actions:
                 self.actions["edit_redo"].setEnabled(self.tableWindow.undo_stack.canRedo())

    # -> INICIO: NUEVO MÉTODO PARA GUARDAR DIRECTAMENTE
    def save_script_directly(self):
        """Guarda el guion actual directamente en la carpeta predefinida sin diálogo."""
        TARGET_DIR = r"W:\Z_JSON\SinSubir"

        if self.tableWindow.pandas_model.dataframe().empty:
            QMessageBox.information(self, "Guardar", "No hay datos para guardar.")
            return False

        try:
            if not os.path.exists(TARGET_DIR):
                os.makedirs(TARGET_DIR)
                if self.statusBar():
                    self.statusBar().showMessage(f"Directorio creado: {TARGET_DIR}", 4000)
        except OSError as e:
            QMessageBox.critical(self, "Error de Directorio",
                                 f"No se pudo crear el directorio de destino:\n{TARGET_DIR}\n\nError: {e}")
            return False

        filename = self.tableWindow._generate_default_filename("json")
        full_path = os.path.join(TARGET_DIR, filename)

        if os.path.exists(full_path) and full_path != self.tableWindow.current_script_path:
            reply = QMessageBox.question(self, "Confirmar Sobrescritura",
                                         f"El archivo '{filename}' ya existe en el destino.\n"
                                         "¿Desea sobrescribirlo?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return False
        try:
            df = self.tableWindow.pandas_model.dataframe()
            header = self.tableWindow._get_header_data_from_ui()
            self.guion_manager.save_to_json(full_path, df, header)

            self.tableWindow.current_script_path = full_path
            self.tableWindow.current_script_name = filename
            self.tableWindow.undo_stack.setClean()
            self._delete_recovery_file()

            if self.statusBar():
                self.statusBar().showMessage(f"Guion guardado en: {full_path}", 5000)
            
            self.add_to_recent_files(full_path)
            
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error al Guardar",
                                 f"Ocurrió un error al guardar el archivo:\n{full_path}\n\nError: {e}")
            return False
    # -> FIN: NUEVO MÉTODO

    def create_all_actions(self):
        # File Menu Actions
        self.add_managed_action("Abrir Video", self.open_video_file, "Ctrl+O", "open_video_icon.svg", "file_open_video")
        self.add_managed_action("Cargar M+E (Audio)", self.load_me_audio_file, "Ctrl+Shift+M", "load_audio_icon.svg", "file_load_me")
        self.add_managed_action("Abrir Guion (DOCX)", self.tableWindow.open_docx_dialog, "Ctrl+G", "open_document_icon.svg", "file_open_docx")
        # -> MODIFICADO: Apuntar a los nuevos métodos wrapper en MainWindow
        self.add_managed_action("Exportar Guion a Excel", self.export_script_to_excel, "Ctrl+E", "export_excel_icon.svg", "file_export_excel")
        self.add_managed_action("Importar Guion desde Excel", self.tableWindow.import_from_excel_dialog, "Ctrl+I", "import_excel_icon.svg", "file_import_excel")
        
        # -> MODIFICADO: La acción de Guardar (Ctrl+S) ahora guarda directamente. El texto también cambia.
        self.add_managed_action("Guardar Guion", self.save_script_directly, "Ctrl+S", "save_json_icon.svg", "file_save_json")
        # -> NUEVO: Añadir una acción "Guardar como..." que abre el diálogo de siempre.
        self.add_managed_action("Guardar Guion como... (JSON)", self.save_script_as_json, "Ctrl+Shift+S", None, "file_save_json_as")

        self.add_managed_action("Cargar Guion desde JSON", self.tableWindow.load_from_json_dialog, "Ctrl+D", "load_json_icon.svg", "file_load_json")

        # Edit Menu Actions
        self.add_managed_action("Deshacer", self.undo_action, "Ctrl+Z", "undo_icon.svg", "edit_undo")
        self.add_managed_action("Rehacer", self.redo_action, "Ctrl+Y", "redo_icon.svg", "edit_redo")

        self.add_managed_action("Agregar Línea", self.tableWindow.add_new_row, "Ctrl+N", "add_row_icon.svg", "edit_add_row")
        self.add_managed_action("Eliminar Fila", self.tableWindow.remove_row, "Ctrl+Del", "delete_row_icon.svg", "edit_delete_row")
        self.add_managed_action("Marcar/Desmarcar Fila", self.tableWindow.toggle_bookmark, "Ctrl+M", "bookmark_icon.svg", "edit_toggle_bookmark")
        self.add_managed_action("Mover Arriba", self.tableWindow.move_row_up, "Alt+Up", "move_up_icon.svg", "edit_move_up")
        self.add_managed_action("Mover Abajo", self.tableWindow.move_row_down, "Alt+Down", "move_down_icon.svg", "edit_move_down")
        self.add_managed_action("Ajustar Diálogos", self.call_adjust_dialogs, None, "adjust_dialogs_icon.svg", "edit_adjust_dialogs")
        self.add_managed_action("Desplazar Timecodes (IN/OUT)...", self.tableWindow.open_shift_timecodes_dialog, "Ctrl+Shift+T", "shift_timecode_icon.svg", "edit_shift_timecodes")
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
        action_mark_out_hold.setShortcut(QKeySequence("F6"))
        self.actions["video_mark_out_hold"] = action_mark_out_hold
        self.addAction(action_mark_out_hold)

    # -> NUEVO: Métodos wrapper para guardar que eliminan el archivo de recuperación
    def save_script_as_json(self):
        """Llama al diálogo de guardado y elimina el archivo de recuperación si tiene éxito."""
        if self.tableWindow.save_to_json_dialog():
            self._delete_recovery_file()

    def export_script_to_excel(self):
        """Llama al diálogo de exportación y elimina el archivo de recuperación si tiene éxito."""
        if self.tableWindow.export_to_excel_dialog():
            self._delete_recovery_file()
            
    def add_managed_action(self, text: str, slot, default_shortcut: str = None, icon_name: str = None, object_name: str = None):
        if not object_name:
            object_name = text.lower().replace("&", "").replace(" ", "_").replace("/", "_").replace(":", "").replace("(", "").replace(")", "")

        action = QAction(text, self)
        action.setObjectName(object_name)
        if icon_name:
            action.setIcon(get_icon(icon_name))
        
        if default_shortcut: 
            action.setShortcut(QKeySequence(default_shortcut))

        if slot:
            action.triggered.connect(slot)

        self.actions[object_name] = action
        if default_shortcut:
            self.addAction(action)
        return action
    
    def call_adjust_dialogs(self, checked=None):
        """
        Llama al ajuste de diálogos en TableWindow pasándole la longitud de línea configurada.
        Acepta un argumento 'checked' del signal 'clicked' pero no lo usa.
        """
        if self.tableWindow:
            self.tableWindow.adjust_dialogs(self.line_length)

    def create_menu_bar(self, exclude_shortcuts=False):
        menuBar = self.menuBar()
        menuBar.clear()
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
        # -> MODIFICADO: Añadir las dos opciones de guardado
        fileMenu.addAction(self.actions["file_save_json"])
        if "file_save_json_as" in self.actions:
            fileMenu.addAction(self.actions["file_save_json_as"])
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
        if "edit_toggle_bookmark" in self.actions:
            editMenu.addAction(self.actions["edit_toggle_bookmark"])
        editMenu.addAction(self.actions["edit_move_up"])
        editMenu.addAction(self.actions["edit_move_down"])
        editMenu.addSeparator()
        editMenu.addAction(self.actions["edit_adjust_dialogs"])
        if "edit_shift_timecodes" in self.actions:
            editMenu.addAction(self.actions["edit_shift_timecodes"])
        editMenu.addAction(self.actions["edit_split_intervention"])
        editMenu.addAction(self.actions["edit_merge_interventions"])
        editMenu.addSeparator()
        editMenu.addAction(self.actions["edit_view_cast"])
        editMenu.addAction(self.actions["edit_find_replace"])
        editMenu.addSeparator()
        editMenu.addAction(self.actions["edit_copy_in_out"])
        editMenu.addAction(self.actions["edit_increment_scene"])

    def create_config_menu(self, menuBar):
        configMenu = menuBar.addMenu("&Herramientas")
        configMenu.addAction(self.actions["config_app_settings"])

    def create_shortcuts_menu(self, menuBar):
        for action_menu_item in menuBar.actions():
            if action_menu_item.menu() and action_menu_item.menu().title() == "&Shortcuts":
                menuBar.removeAction(action_menu_item)
                break

        shortcutsMenu = menuBar.addMenu("&Shortcuts")
        shortcutsMenu.addAction(self.actions["config_shortcuts_dialog"])

        load_config_menu = shortcutsMenu.addMenu("Cargar Configuración de Shortcuts")
        load_config_menu.setIcon(get_icon("load_config_icon.svg"))
        if hasattr(self, 'shortcut_manager'):
            for config_name in self.shortcut_manager.configurations.keys():
                action = QAction(config_name, self)
                action.triggered.connect(lambda checked, name=config_name: self.shortcut_manager.apply_shortcuts(name))
                load_config_menu.addAction(action)
        
        if "config_delete_shortcut_profile" in self.actions:
            shortcutsMenu.addAction(self.actions["config_delete_shortcut_profile"])
        else:
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
            return
            
        self.recent_files_menu.clear()
        for file_path in self.recent_files:
            action = QAction(os.path.basename(file_path), self)
            action.setIcon(get_icon("open_document_icon.svg"))
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
            self.add_to_recent_files(file_path)
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
            current_line_length=self.line_length,
            get_icon_func=get_icon
        )
        if config_dialog.exec() == QDialog.DialogCode.Accepted:
            self.trim_value, self.font_size, self.line_length = config_dialog.get_values()
            self.apply_font_size()

    def load_me_audio_file(self):
        if self.videoPlayerWidget.media_player.source().isEmpty():
            QMessageBox.information(self, "Cargar M+E", "Por favor, cargue primero un archivo de video.")
            return

        file_name, _ = QFileDialog.getOpenFileName(self, "Cargar Audio M+E", "", "Archivos de Audio (*.wav *.mp3);;Todos los archivos (*.*)")
        if file_name:
            self.videoPlayerWidget.load_me_file(file_name)
            self.add_to_recent_files(file_name)

    def add_to_recent_files(self, file_path):
        abs_file_path = os.path.abspath(file_path)
        if abs_file_path in self.recent_files:
            self.recent_files.remove(abs_file_path)
        self.recent_files.insert(0, abs_file_path)
        self.recent_files = self.recent_files[:10]
        self.save_recent_files()
        self.update_recent_files_menu()

    def load_recent_files(self):
        try:
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
            configs.remove("default")
        
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
                                           QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                if self.shortcut_manager.delete_configuration(config_name):
                    QMessageBox.information(self, "Éxito", f"Configuración '{config_name}' eliminada exitosamente.")

    def open_video_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, 
                                                   "Abrir Video", "", 
                                                   "Videos (*.mp4 *.avi *.mkv *.mov);;Todos los archivos (*.*)")
        if file_name:
            self.videoPlayerWidget.load_video(file_name)
            self.add_to_recent_files(file_name)

    def detach_video(self, video_widget_instance):
        if self.videoWindow is not None:
            return
        try:
            widget_index_in_splitter = -1
            for i in range(self.splitter.count()):
                if self.splitter.widget(i) == video_widget_instance:
                    widget_index_in_splitter = i
                    break
            
            if widget_index_in_splitter != -1:
                self.videoWindow = VideoWindow(video_widget_instance, get_icon_func=get_icon, main_window=self)
                
                actions_for_detached_video = [
                    "video_toggle_play", "video_rewind", "video_forward", 
                    "video_mark_in", "video_mark_out_hold" 
                ]
                for action_name in actions_for_detached_video:
                    if action_name in self.actions:
                        self.videoWindow.addAction(self.actions[action_name])

                self.videoWindow.close_detached.connect(self.attach_video)
                self.videoWindow.show()
            else:
                 QMessageBox.warning(self,"Error", "El widget de video a separar no se encontró en el splitter.")
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al separar el video: {str(e)}\n{traceback.format_exc()}")


    def attach_video(self):
        if self.videoWindow is None:
            return
        try:
            video_widget_instance = self.videoWindow.video_widget
            
            actions_for_detached_video = [
                "video_toggle_play", "video_rewind", "video_forward",
                "video_mark_in", "video_mark_out_hold"
            ]
            for action_name in actions_for_detached_video:
                if action_name in self.actions:
                    self.videoWindow.removeAction(self.actions[action_name])

            self.splitter.insertWidget(0, video_widget_instance)
            self.videoWindow.close_detached.disconnect(self.attach_video)
            self.videoWindow = None

            total_width = self.splitter.width()
            if total_width > 0 and self.splitter.count() == 2:
                 self.splitter.setSizes([total_width // 2, total_width // 2])
            else:
                 self.splitter.setSizes([100,100])
            
            self.videoPlayerWidget.setFocus()
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

    # -> INICIO: NUEVOS MÉTODOS PARA GUARDAR/RESTAURAR LA CONFIGURACIÓN
    def _load_settings(self):
        """Carga la configuración de la aplicación al iniciar."""
        # El primer argumento es el nombre de tu compañía/organización, el segundo es el nombre de la app.
        # Esto determina dónde se guarda el archivo de configuración en el sistema del usuario.
        settings = QSettings("TuEmpresa", "EditorDeGuion")

        # Restaurar geometría y estado de la ventana (tamaño, posición, maximizado)
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Restaurar estado del splitter (la división entre video y tabla)
        splitter_state = settings.value("splitter_state")
        if splitter_state:
            self.splitter.restoreState(splitter_state)

        # Restaurar estado de las columnas de la tabla (orden, anchos, columnas ocultas)
        column_state = settings.value("column_state")
        if column_state:
            self.tableWindow.table_view.horizontalHeader().restoreState(column_state)

        # Restaurar valores de configuración
        self.font_size = settings.value("font_size", 9, type=int)
        self.line_length = settings.value("line_length", 60, type=int)
        self.trim_value = settings.value("trim_value", 0, type=int)
        
        # Aplicar la fuente cargada
        self.apply_font_size()

    def _save_settings(self):
        """Guarda la configuración de la aplicación al cerrar."""
        settings = QSettings("TuEmpresa", "EditorDeGuion")
        
        # Guardar geometría y estado de la ventana
        settings.setValue("geometry", self.saveGeometry())
        
        # Guardar estado del splitter
        settings.setValue("splitter_state", self.splitter.saveState())
        
        # Guardar estado de las columnas de la tabla
        settings.setValue("column_state", self.tableWindow.table_view.horizontalHeader().saveState())
        
        # Guardar valores de configuración
        settings.setValue("font_size", self.font_size)
        settings.setValue("line_length", self.line_length)
        settings.setValue("trim_value", self.trim_value)
    # -> FIN: NUEVOS MÉTODOS

    def closeEvent(self, event):
        def save_and_accept():
            """Función auxiliar para guardar ajustes y aceptar el evento."""
            self._save_settings()
            self._delete_recovery_file()
            event.accept()

        if hasattr(self.tableWindow, 'undo_stack') and not self.tableWindow.undo_stack.isClean():
            reply = QMessageBox.question(self,
                                         "Guardar cambios",
                                         "Hay cambios sin guardar. ¿Desea guardar el guion antes de salir?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                saved_successfully = False
                # Si ya tiene una ruta, guarda sobreescribiendo en esa ruta
                if self.tableWindow.current_script_path:
                    if self.tableWindow.current_script_path.endswith(".json"):
                        self.guion_manager.save_to_json(self.tableWindow.current_script_path, self.tableWindow.pandas_model.dataframe(), self.tableWindow._get_header_data_from_ui())
                        saved_successfully = True
                    elif self.tableWindow.current_script_path.endswith(".xlsx"):
                        self.guion_manager.save_to_excel(self.tableWindow.current_script_path, self.tableWindow.pandas_model.dataframe(), self.tableWindow._get_header_data_from_ui())
                        saved_successfully = True
                    else:
                        # Si es un tipo de archivo desconocido (ej. cargado de .docx), usa el guardado directo por defecto
                        saved_successfully = self.save_script_directly()
                else:
                    # Si no tiene ruta, es un guion nuevo, así que usa el guardado directo
                    saved_successfully = self.save_script_directly()

                if saved_successfully:
                    save_and_accept()
                else:
                    event.ignore()
            elif reply == QMessageBox.StandardButton.Discard:
                save_and_accept()
            else: # Cancel
                event.ignore()
        else:
            save_and_accept()
            
    def get_icon_func_for_dialogs(self):
        return get_icon

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(error_message)

    user_message = f"Ocurrió un error inesperado:\n\nTipo: {exc_type.__name__}\nMensaje: {exc_value}\n\n"
    user_message += "Por favor, reporte este error. Puede encontrar más detalles en la consola."

    if QApplication.instance():
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Error Inesperado")
            msg_box.setText(user_message.split('\n\n')[0]) 
            msg_box.setInformativeText('\n\n'.join(user_message.split('\n\n')[1:]))
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
        except Exception as e_msgbox:
            print(f"Error al mostrar QMessageBox: {e_msgbox}")
            print("Error original:", error_message)
    else:
        print("Error original (QApplication no disponible):", error_message)


def main():
    sys.excepthook = handle_exception
    app = QApplication(sys.argv)

    main_css_content = load_stylesheet_content("main.css")
    if main_css_content:
        app.setStyleSheet(main_css_content)
    else:
        print("No se pudo cargar main.css globalmente.")


    mainWindow = MainWindow()
    # mainWindow.showMaximized() # Quitado para probar mejor el guardado de geometría
    mainWindow.show() # Usar show() normal para que la geometría se guarde/restaure correctamente
    sys.exit(app.exec())

if __name__ == "__main__":
    main()