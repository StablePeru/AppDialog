# main.py
import sys
import traceback
import json
import os
import time
import subprocess
import logging

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QSplitter, QDialog, QInputDialog,
    QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings, QEvent
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QDragEnterEvent, QDropEvent

from guion_editor.widgets.video_player_widget import VideoPlayerWidget
from guion_editor.widgets.table_window import TableWindow
from guion_editor.widgets.video_window import VideoWindow
from guion_editor.widgets.config_dialog import ConfigDialog
from guion_editor.widgets.shortcut_config_dialog import ShortcutConfigDialog
from guion_editor.utils.shortcut_manager import ShortcutManager
from guion_editor.utils.guion_manager import GuionManager
from guion_editor.widgets.advanced_srt_export_dialog import AdvancedSrtExportDialog
from guion_editor import constants as C
from guion_editor.utils.paths import resource_path, get_safe_save_dir, get_user_config_dir

ICON_CACHE = {}
# Apuntamos a la carpeta de iconos usando la ruta relativa desde la raíz del proyecto
ICON_BASE_PATH = resource_path(os.path.join('guion_editor', 'styles', 'icons'))
STYLES_BASE_PATH = resource_path(os.path.join('guion_editor', 'styles'))

def setup_logging():
    log_dir = get_user_config_dir()
    log_file_path = os.path.join(log_dir, 'guion_editor.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("Logging configurado y aplicación iniciada.")

def get_icon(icon_name: str) -> QIcon:
    if icon_name in ICON_CACHE:
        return ICON_CACHE[icon_name]

    icon_path = os.path.join(ICON_BASE_PATH, icon_name)
    if not os.path.exists(icon_path):
        logging.warning(f"Icono no encontrado en {icon_path}")
        return QIcon()

    icon = QIcon(icon_path)
    ICON_CACHE[icon_name] = icon
    return icon


def load_stylesheet_content(filename: str) -> str:
    css_path = os.path.join(STYLES_BASE_PATH, filename)
    if not os.path.exists(css_path):
        logging.warning(f"Stylesheet no encontrado en {css_path}")
        return ""
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error al cargar stylesheet {filename}: {e}")
        return ""

class MainWindow(QMainWindow):
    AUTOSAVE_INTERVAL_MS = 120000
    RECOVERY_DIR = get_safe_save_dir(r"W:\Z_JSON\Backup")
    SAVE_DIR = get_safe_save_dir(r"W:\Z_JSON\SinSubir")
    SUBS_DIR = get_safe_save_dir(r"W:\Z_JSON\Subs")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor de Guion con Video")
        self.setGeometry(100, 100, 1600, 900)
        
        self.setAcceptDrops(True)

        self.trim_value = 0
        self.font_size = 9
        self.line_length = 60
        self.guion_manager = GuionManager()
        self.actions = {} 
        self.find_replace_dialog_instance = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.videoPlayerWidget = VideoPlayerWidget(get_icon_func=get_icon, main_window=self)
        
        self.videoPlayerWidget.setAcceptDrops(True)
        self.videoPlayerWidget.installEventFilter(self)
        
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
        self.videoPlayerWidget.media_player.positionChanged.connect(self.tableWindow.sync_with_video_position)
        self.videoWindow = None

        self.create_menu_bar(exclude_shortcuts=True)
        self.shortcut_manager = ShortcutManager(self)
        self.create_shortcuts_menu(self.menuBar())

        self.tableWindow.setFocus()
        self._update_initial_undo_redo_actions_state()

        self._check_for_recovery_file()
        self._setup_autosave()
        self._load_settings()

    def _setup_autosave(self):
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(self.AUTOSAVE_INTERVAL_MS)  
        self.autosave_timer.timeout.connect(self._perform_autosave)
        self.autosave_timer.start()
        logging.info(f"Autoguardado activado (cada {self.AUTOSAVE_INTERVAL_MS / 60000:.0f} minutos si hay cambios).")

    def _perform_autosave(self):
        TARGET_DIR = self.RECOVERY_DIR

        if hasattr(self.tableWindow, 'undo_stack') and not self.tableWindow.undo_stack.isClean():
            try:
                base_filename = self.tableWindow._generate_default_filename("json")
                autosave_filename = f"auto_{base_filename}"
                recovery_path = os.path.join(TARGET_DIR, autosave_filename)

                if not os.path.exists(TARGET_DIR):
                    os.makedirs(TARGET_DIR)

                current_df = self.tableWindow.pandas_model.dataframe()
                header_data = self.tableWindow._get_header_data_from_ui()
                self.guion_manager.save_to_json(recovery_path, current_df, header_data)
                
                if self.statusBar():
                    self.statusBar().showMessage(f"Progreso autoguardado en {autosave_filename}", 3000)
            
            except (OSError, IOError) as e:
                logging.error(f"Error de sistema de archivos durante el autoguardado: {e}")
                if self.statusBar():
                    self.statusBar().showMessage(f"Fallo en el autoguardado: {e}", 5000)
            except Exception as e:
                logging.error(f"Error inesperado durante el autoguardado: {e}", exc_info=True)

    def _check_for_recovery_file(self):
        TARGET_DIR = self.RECOVERY_DIR
        if not os.path.exists(TARGET_DIR):
            return

        try:
            recovery_files = [f for f in os.listdir(TARGET_DIR) if f.startswith("auto_") and f.endswith(".json")]

            if not recovery_files:
                return

            chosen_file_to_restore = None
            if len(recovery_files) == 1:
                chosen_file_to_restore = recovery_files[0]
                reply = QMessageBox.question(self,
                             "Recuperar Sesión",
                             f"Se ha encontrado un archivo de recuperación:\n\n{chosen_file_to_restore}\n\n"
                             "¿Desea restaurar este trabajo?",
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Discard,
                             QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Discard:
                    chosen_file_to_restore = None
            else:
                item, ok = QInputDialog.getItem(self, "Múltiples Archivos de Recuperación",
                                                "Se encontraron varios archivos autoguardados.\n"
                                                "Por favor, seleccione uno para restaurar o cancele para ignorarlos:",
                                                recovery_files, 0, False)
                if ok and item:
                    chosen_file_to_restore = item

            if chosen_file_to_restore:
                recovery_path = os.path.join(TARGET_DIR, chosen_file_to_restore)
                self.tableWindow.load_from_json_path(recovery_path)
                self.tableWindow.undo_stack.setClean(False)
                QMessageBox.information(self, "Éxito", f"El guion '{chosen_file_to_restore}' ha sido restaurado.")
                
                try:
                    os.remove(recovery_path)
                except OSError as e:
                    logging.error(f"No se pudo eliminar el archivo de recuperación restaurado '{recovery_path}': {e}")

        except Exception as e:
            logging.error("Error al procesar el archivo de recuperación.", exc_info=True)
            QMessageBox.warning(self, "Error de Recuperación", f"No se pudo procesar el archivo de recuperación: {e}")
                
    def _delete_recovery_file(self):
        TARGET_DIR = self.RECOVERY_DIR
        try:
            base_filename = self.tableWindow._generate_default_filename("json")
            autosave_filename = f"auto_{base_filename}"
            recovery_path = os.path.join(TARGET_DIR, autosave_filename)
            
            if os.path.exists(recovery_path):
                os.remove(recovery_path)
                logging.info(f"Archivo de recuperación eliminado: {recovery_path}")
        except OSError as e:
            logging.error(f"Error al eliminar el archivo de recuperación: {e}")


    def _update_initial_undo_redo_actions_state(self):
        if hasattr(self.tableWindow, 'undo_stack'):
            if C.ACT_EDIT_UNDO in self.actions:
                 self.actions[C.ACT_EDIT_UNDO].setEnabled(self.tableWindow.undo_stack.canUndo())
            if C.ACT_EDIT_REDO in self.actions:
                 self.actions[C.ACT_EDIT_REDO].setEnabled(self.tableWindow.undo_stack.canRedo())

    # --- MÉTODO MODIFICADO PARA SOPORTAR CARPETA SUBS ---
    def save_script_directly(self):
        # Determinamos el directorio basado en el nombre del archivo actual
        current_name = self.tableWindow.current_script_name or ""
        
        if "_SUB" in current_name:
            TARGET_DIR = self.SUBS_DIR
        else:
            TARGET_DIR = self.SAVE_DIR

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
        
        # Si estamos en modo SUB y el nombre generado no tiene _SUB, forzarlo
        if TARGET_DIR == self.SUBS_DIR and "_SUB" not in filename:
             name_part, ext_part = os.path.splitext(filename)
             filename = f"{name_part}_SUB{ext_part}"

        full_path = os.path.join(TARGET_DIR, filename)

        if os.path.exists(full_path) and full_path != self.tableWindow.current_script_path:
            reply = QMessageBox.question(self, "Confirmar Sobrescritura",
                                         f"El archivo '{filename}' ya existe en el destino.\n"
                                         "¿Desea sobrescribirlo?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return False
        
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
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
            logging.error(f"Error al guardar el archivo en {full_path}", exc_info=True)
            QMessageBox.critical(self, "Error al Guardar",
                                 f"Ocurrió un error al guardar el archivo:\n{full_path}\n\nError: {e}")
            return False
        finally:
            QApplication.restoreOverrideCursor()

    # --- NUEVO MÉTODO PARA GENERAR VERSIÓN SUB ---
    def create_sub_version_and_clean(self):
        """
        1. Pregunta qué columna determina si la fila se borra.
        2. Obtiene una versión limpia del guion (sin paréntesis).
        3. Elimina filas basándose en la columna elegida.
        4. Guarda esa versión como un NUEVO archivo Excel con sufijo _SUB en la carpeta SUBS.
        5. Carga ese nuevo archivo en el editor.
        """
        if self.tableWindow.pandas_model.dataframe().empty:
            QMessageBox.information(self, "Crear Versión SUB", "No hay datos para procesar.")
            return

        # Opciones para el usuario
        options = [
            "AMBAS (Solo borrar si las dos están vacías)",
            "EUSKERA (Borrar si Euskera queda vacío)",
            "DIÁLOGO (Borrar si Diálogo queda vacío)"
        ]

        item, ok = QInputDialog.getItem(
            self, 
            "Generar Versión SUB", 
            "Se limpiarán paréntesis en TODAS las columnas.\n\n"
            "¿Qué criterio usar para ELIMINAR la fila entera?", 
            options, 
            0, 
            False
        )
        
        if not ok:
            return

        # Determinar el modo interno basado en la selección
        mode = "AMBAS"
        if "EUSKERA" in item:
            mode = "EUSKERA"
        elif "DIÁLOGO" in item:
            mode = "DIALOGO"

        # 1. Obtener datos limpios con el modo seleccionado
        clean_df = self.tableWindow.get_cleaned_dataframe_for_subs(cleanup_mode=mode)
        header_data = self.tableWindow._get_header_data_from_ui()

        # 2. Preparar ruta y nombre
        try:
            if not os.path.exists(self.SUBS_DIR):
                os.makedirs(self.SUBS_DIR)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear la carpeta Subs:\n{e}")
            return

        base_name = self.tableWindow._generate_default_filename("xlsx")
        name_root, ext = os.path.splitext(base_name)
        
        if name_root.endswith("_SUB"):
            new_filename = f"{name_root}{ext}"
        else:
            new_filename = f"{name_root}_SUB{ext}"
            
        new_path = os.path.join(self.SUBS_DIR, new_filename)

        # 3. Guardar el nuevo Excel
        try:
            self.guion_manager.save_to_excel(new_path, clean_df, header_data)
            logging.info(f"Versión SUB creada en: {new_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error al Guardar", f"No se pudo crear el archivo _SUB:\n{e}")
            return

        # 4. Cargar el nuevo archivo
        self.tableWindow.load_from_excel_path(new_path)
        
        QMessageBox.information(self, "Éxito", f"Se ha creado y cargado la versión de subtítulos:\n\n{new_filename}\n\nUbicación: {self.SUBS_DIR}")

    def create_all_actions(self):
        # File Menu
        self.add_managed_action("Abrir Video", self.open_video_file, "Ctrl+O", "open_video_icon.svg", C.ACT_FILE_OPEN_VIDEO)
        self.add_managed_action("Cargar M+E (Audio)", self.load_me_audio_file, "Ctrl+Shift+M", "load_audio_icon.svg", C.ACT_FILE_LOAD_ME)
        self.add_managed_action("Abrir Guion (DOCX)", self.tableWindow.open_docx_dialog, "Ctrl+G", "open_document_icon.svg", C.ACT_FILE_OPEN_DOCX)
        self.add_managed_action("Exportar Guion a Excel", self.export_script_to_excel, "Ctrl+E", "export_excel_icon.svg", C.ACT_FILE_EXPORT_EXCEL)
        self.add_managed_action("Exportar a Subtítulos (SRT)...", self.export_to_srt, None, "export_srt_icon.svg", C.ACT_FILE_EXPORT_SRT)
        self.add_managed_action("Importar Guion desde Excel", self.tableWindow.import_from_excel_dialog, "Ctrl+I", "import_excel_icon.svg", C.ACT_FILE_IMPORT_EXCEL)
        
        self.add_managed_action("Guardar Guion", self.save_script_directly, "Ctrl+S", "save_json_icon.svg", C.ACT_FILE_SAVE_JSON)
        self.add_managed_action("Guardar Guion como... (JSON)", self.save_script_as_json, "Ctrl+Shift+S", None, C.ACT_FILE_SAVE_JSON_AS)
        self.add_managed_action("Cargar Guion desde JSON", self.tableWindow.load_from_json_dialog, "Ctrl+D", "load_json_icon.svg", C.ACT_FILE_LOAD_JSON)

        # Edit Menu (Usando constantes C.ACT_...)
        self.add_managed_action("Deshacer", self.undo_action, "Ctrl+Z", "undo_icon.svg", C.ACT_EDIT_UNDO)
        self.add_managed_action("Rehacer", self.redo_action, "Ctrl+Y", "redo_icon.svg", C.ACT_EDIT_REDO)
        self.add_managed_action("Agregar Línea", self.tableWindow.add_new_row, "Ctrl+N", "add_row_icon.svg", C.ACT_EDIT_ADD_ROW)
        self.add_managed_action("Eliminar Fila", self.tableWindow.remove_row, "Ctrl+Del", "delete_row_icon.svg", C.ACT_EDIT_DELETE_ROW)
        self.add_managed_action("Marcar/Desmarcar Fila", self.tableWindow.toggle_bookmark, "Ctrl+M", "bookmark_icon.svg", C.ACT_EDIT_TOGGLE_BOOKMARK)
        self.add_managed_action("Mover Arriba", self.tableWindow.move_row_up, "Alt+Up", "move_up_icon.svg", C.ACT_EDIT_MOVE_UP)
        self.add_managed_action("Mover Abajo", self.tableWindow.move_row_down, "Alt+Down", "move_down_icon.svg", C.ACT_EDIT_MOVE_DOWN)
        self.add_managed_action("Ajustar Diálogos", self.call_adjust_dialogs, None, "adjust_dialogs_icon.svg", C.ACT_EDIT_ADJUST_DIALOGS)
        self.add_managed_action("Desplazar Timecodes (IN/OUT)...", self.tableWindow.open_shift_timecodes_dialog, "Ctrl+Shift+T", "shift_timecode_icon.svg", C.ACT_EDIT_SHIFT_TIMECODES)
        self.add_managed_action("Separar Intervención", self.tableWindow.split_intervention, "Alt+S", "split_intervention_icon.svg", C.ACT_EDIT_SPLIT_INTERVENTION)
        self.add_managed_action("Juntar Intervenciones", self.tableWindow.merge_interventions, "Alt+M", "merge_intervention_icon.svg", C.ACT_EDIT_MERGE_INTERVENTIONS)
        self.add_managed_action("Ver Reparto Completo", self.open_cast_window, None, "view_cast_icon.svg", C.ACT_EDIT_VIEW_CAST)
        self.add_managed_action("Buscar y Reemplazar", self.open_find_replace_dialog, "Ctrl+F", "find_replace_icon.svg", C.ACT_EDIT_FIND_REPLACE)
        self.add_managed_action("Copiar IN/OUT a Siguiente", self.tableWindow.copy_in_out_to_next, "Ctrl+B", "copy_in_out_icon.svg", C.ACT_EDIT_COPY_IN_OUT)
        self.add_managed_action("Incrementar Escena", self.change_scene, "Ctrl+R", "change_scene_icon.svg", C.ACT_EDIT_INCREMENT_SCENE)

        # Config Menu
        self.add_managed_action("Configuración App", self.open_config_dialog, "Ctrl+K", "settings_icon.svg", C.ACT_CONFIG_APP)
        self.add_managed_action("Optimizar Takes (Takeo)...", self.open_takeo_dialog, None, "takeo_icon.svg", C.ACT_TOOLS_TAKEO)
        self.add_managed_action("Generar Versión SUB (Limpiar () y Vacíos)", self.create_sub_version_and_clean, None, "clean_subs_icon.svg", C.ACT_TOOLS_CREATE_SUB)
        self.add_managed_action("Conversor Excel a TXT...", self.launch_xlsx_converter, None, "convert_icon.svg", C.ACT_TOOLS_XLSX_CONVERTER)
        self.add_managed_action("Reiniciar Todas las Escenas a '1'", self.tableWindow.reset_all_scenes, None, "reset_scenes_icon.svg", C.ACT_TOOLS_RESET_SCENES)
        self.add_managed_action("Reiniciar Todos los Tiempos a Cero", self.tableWindow.reset_all_timecodes, None, "reset_timecodes_icon.svg", C.ACT_TOOLS_RESET_TIMECODES)
        self.add_managed_action("Copiar IN a OUT anterior", self.tableWindow.copy_in_to_previous_out, None, "copy_in_out_prev_icon.svg", C.ACT_TOOLS_COPY_IN_OUT_PREV)

        # Shortcuts Menu
        self.add_managed_action("Configurar Shortcuts", self.open_shortcut_config_dialog, None, "configure_shortcuts_icon.svg", C.ACT_SHORTCUTS_DIALOG)

        # Video Player Actions
        self.add_managed_action("Video: Reproducir/Pausar", self.videoPlayerWidget.toggle_play, "F8", None, C.ACT_VIDEO_TOGGLE_PLAY)
        self.add_managed_action("Video: Retroceder", lambda: self.videoPlayerWidget.change_position(-5000), "F7", None, C.ACT_VIDEO_REWIND)
        self.add_managed_action("Video: Avanzar", lambda: self.videoPlayerWidget.change_position(5000), "F9", None, C.ACT_VIDEO_FORWARD)
        self.add_managed_action("Video: Marcar IN", self.videoPlayerWidget.mark_in, "F5", None, C.ACT_VIDEO_MARK_IN)

        action_mark_out_hold = QAction("Video: Marcar OUT (Mantener)", self)
        action_mark_out_hold.setObjectName(C.ACT_VIDEO_MARK_OUT_HOLD)
        action_mark_out_hold.setShortcut(QKeySequence("F6"))
        self.actions[C.ACT_VIDEO_MARK_OUT_HOLD] = action_mark_out_hold
        self.addAction(action_mark_out_hold)

    def save_script_as_json(self):
        if self.tableWindow.save_to_json_dialog():
            self._delete_recovery_file()

    def export_script_to_excel(self):
        excel_export_successful = self.tableWindow.export_to_excel_dialog()
        if excel_export_successful:
            logging.info("Exportación a Excel exitosa. Realizando guardado automático a JSON...")
            self.save_script_directly()

    def export_to_srt(self):
        if self.tableWindow.pandas_model.dataframe().empty:
            QMessageBox.information(self, "Exportar a SRT", "No hay datos en el guion para exportar.")
            return

        # Usamos el nuevo diálogo avanzado que incluye la lógica de tu programa externo
        dialog = AdvancedSrtExportDialog(self.tableWindow, get_icon_func=get_icon, parent=self)
        dialog.exec()
            
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
            
            # --- Acciones Principales (Usando las nuevas Constantes) ---
            fileMenu.addAction(self.actions[C.ACT_FILE_OPEN_VIDEO])
            fileMenu.addAction(self.actions[C.ACT_FILE_LOAD_ME])
            fileMenu.addAction(self.actions[C.ACT_FILE_OPEN_DOCX])
            
            fileMenu.addSeparator()
            
            fileMenu.addAction(self.actions[C.ACT_FILE_EXPORT_EXCEL])
            if C.ACT_FILE_EXPORT_SRT in self.actions:
                fileMenu.addAction(self.actions[C.ACT_FILE_EXPORT_SRT])
            fileMenu.addAction(self.actions[C.ACT_FILE_IMPORT_EXCEL])
            
            fileMenu.addSeparator()
            
            fileMenu.addAction(self.actions[C.ACT_FILE_SAVE_JSON])
            if C.ACT_FILE_SAVE_JSON_AS in self.actions:
                fileMenu.addAction(self.actions[C.ACT_FILE_SAVE_JSON_AS])
            fileMenu.addAction(self.actions[C.ACT_FILE_LOAD_JSON])

            # --- SECCIÓN DE RECIENTES (Esto es lo que faltaba) ---
            fileMenu.addSeparator()

            # Creamos el submenú
            self.recent_files_menu = fileMenu.addMenu("Abrir Recientemente")
            self.recent_files_menu.setIcon(get_icon("history_icon.svg"))
            
            # Llamamos a la función que lo rellena con la lista
            self.update_recent_files_menu()

    def create_edit_menu(self, menuBar):
        editMenu = menuBar.addMenu("&Editar")
        if C.ACT_EDIT_UNDO in self.actions: editMenu.addAction(self.actions[C.ACT_EDIT_UNDO])
        if C.ACT_EDIT_REDO in self.actions: editMenu.addAction(self.actions[C.ACT_EDIT_REDO])
        editMenu.addSeparator()

        editMenu.addAction(self.actions[C.ACT_EDIT_ADD_ROW])
        editMenu.addAction(self.actions[C.ACT_EDIT_DELETE_ROW])
        if C.ACT_EDIT_TOGGLE_BOOKMARK in self.actions:
            editMenu.addAction(self.actions[C.ACT_EDIT_TOGGLE_BOOKMARK])
        editMenu.addAction(self.actions[C.ACT_EDIT_MOVE_UP])
        editMenu.addAction(self.actions[C.ACT_EDIT_MOVE_DOWN])
        editMenu.addSeparator()
        editMenu.addAction(self.actions[C.ACT_EDIT_ADJUST_DIALOGS])
        if C.ACT_EDIT_SHIFT_TIMECODES in self.actions:
            editMenu.addAction(self.actions[C.ACT_EDIT_SHIFT_TIMECODES])
        editMenu.addAction(self.actions[C.ACT_EDIT_SPLIT_INTERVENTION])
        editMenu.addAction(self.actions[C.ACT_EDIT_MERGE_INTERVENTIONS])
        editMenu.addSeparator()
        editMenu.addAction(self.actions[C.ACT_EDIT_VIEW_CAST])
        editMenu.addAction(self.actions[C.ACT_EDIT_FIND_REPLACE])
        editMenu.addSeparator()
        editMenu.addAction(self.actions[C.ACT_EDIT_COPY_IN_OUT])
        editMenu.addAction(self.actions[C.ACT_EDIT_INCREMENT_SCENE])

    def create_config_menu(self, menuBar):
        configMenu = menuBar.addMenu("&Herramientas")
        configMenu.addAction(self.actions[C.ACT_CONFIG_APP])
        configMenu.addSeparator()
        configMenu.addAction(self.actions[C.ACT_TOOLS_TAKEO])
        configMenu.addAction(self.actions[C.ACT_TOOLS_CREATE_SUB])
        configMenu.addAction(self.actions[C.ACT_TOOLS_XLSX_CONVERTER])
        configMenu.addSeparator()
        configMenu.addAction(self.actions[C.ACT_TOOLS_RESET_SCENES])
        configMenu.addAction(self.actions[C.ACT_TOOLS_RESET_TIMECODES])
        configMenu.addAction(self.actions[C.ACT_TOOLS_COPY_IN_OUT_PREV])


    def create_shortcuts_menu(self, menuBar):
        for action_menu_item in menuBar.actions():
            if action_menu_item.menu() and action_menu_item.menu().title() == "&Shortcuts":
                menuBar.removeAction(action_menu_item)
                break

        shortcutsMenu = menuBar.addMenu("&Shortcuts")
        shortcutsMenu.addAction(self.actions[C.ACT_SHORTCUTS_DIALOG])

        load_config_menu = shortcutsMenu.addMenu("Cargar Configuración de Shortcuts")
        load_config_menu.setIcon(get_icon("load_config_icon.svg"))
        if hasattr(self, 'shortcut_manager'):
            for config_name in self.shortcut_manager.configurations.keys():
                action = QAction(config_name, self)
                action.triggered.connect(lambda checked, name=config_name: self.shortcut_manager.apply_shortcuts(name))
                load_config_menu.addAction(action)
        
        if C.ACT_SHORTCUTS_DELETE in self.actions:
            shortcutsMenu.addAction(self.actions[C.ACT_SHORTCUTS_DELETE])
        else:
            delete_config_action = self.add_managed_action(
                "Eliminar Configuración de Shortcuts",
                self.delete_shortcut_configuration,
                None,
                "delete_config_icon.svg",
                C.ACT_SHORTCUTS_DELETE
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
        self.cast_window = CastWindow(self.tableWindow.pandas_model, parent_main_window=self, parent=self)
        self.cast_window.show()

    def open_find_replace_dialog(self):
        from guion_editor.widgets.find_replace_dialog import FindReplaceDialog
        
        if self.find_replace_dialog_instance is None:
            self.find_replace_dialog_instance = FindReplaceDialog(self.tableWindow, get_icon_func=get_icon)
        
        self.find_replace_dialog_instance.show()
        self.find_replace_dialog_instance.activateWindow()
        self.find_replace_dialog_instance.raise_()

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
            recent_files_path = os.path.join(get_user_config_dir(), 'recent_files.json')

            if os.path.exists(recent_files_path):
                with open(recent_files_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar archivos recientes: {str(e)}")
            return []

    def save_recent_files(self):
        try:
            recent_files_path = os.path.join(get_user_config_dir(), 'recent_files.json')

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
            logging.error("Error al separar el video", exc_info=True)
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
            logging.error("Error al adjuntar el video", exc_info=True)
            QMessageBox.warning(self,"Error",f"Error al adjuntar el video: {str(e)}\n{traceback.format_exc()}")


    def handle_set_position(self, action_type_str, position_ms):
        try:
            adjusted_position = max(position_ms - self.trim_value, 0)
            self.videoPlayerWidget.set_position_public(adjusted_position)
        except Exception as e:
            logging.warning(f"Error al establecer la posición del video: {str(e)}")
            QMessageBox.warning(self,"Error",f"Error al establecer la posición del video: {str(e)}")

    def change_scene(self):
        self.tableWindow.change_scene()

    def open_takeo_dialog(self):
        if self.tableWindow.pandas_model.dataframe().empty:
            QMessageBox.information(self, "Optimizar Takes", "No hay datos en el guion para optimizar.")
            return
            
        from guion_editor.widgets.takeo_dialog import TakeoDialog
        dialog = TakeoDialog(self.tableWindow, get_icon_func=get_icon, parent=self)
        dialog.exec()

    def launch_xlsx_converter(self):
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                
                # --- CAMBIO AQUÍ: Apuntamos a la nueva ubicación dentro de widgets ---
                converter_script = os.path.join(current_dir, 'guion_editor', 'widgets', 'xlsx_converter', 'main.py')
                # ---------------------------------------------------------------------

                if not os.path.exists(converter_script):
                    QMessageBox.critical(
                        self, "Error",
                        f"No se encontró el script del conversor en:\n{converter_script}"
                    )
                    return

                python_executable = sys.executable
                subprocess.Popen([python_executable, converter_script])
                if self.statusBar():
                    self.statusBar().showMessage("Lanzando conversor de Excel...", 3000)
                    
            except Exception as e:
                logging.error("No se pudo iniciar el conversor.", exc_info=True)
                QMessageBox.critical(self, "Error al Lanzar", f"No se pudo iniciar el conversor: {e}")

    def undo_action(self):
        if self.tableWindow and hasattr(self.tableWindow, 'undo_stack'):
            self.tableWindow.undo_stack.undo()

    def redo_action(self):
        if self.tableWindow and hasattr(self.tableWindow, 'undo_stack'):
            self.tableWindow.undo_stack.redo()

    def _load_settings(self):
        settings = QSettings("TuEmpresa", "EditorDeGuion")
        
        geometry = settings.value(C.SETTING_GEOMETRY)
        if geometry: self.restoreGeometry(geometry)

        splitter_state = settings.value(C.SETTING_SPLITTER_STATE)
        if splitter_state: self.splitter.restoreState(splitter_state)

        column_state = settings.value(C.SETTING_COLUMN_STATE)
        if column_state: self.tableWindow.table_view.horizontalHeader().restoreState(column_state)

        self.font_size = settings.value(C.SETTING_FONT_SIZE, 9, type=int)
        self.line_length = settings.value(C.SETTING_LINE_LENGTH, 60, type=int)
        self.trim_value = settings.value(C.SETTING_TRIM_VALUE, 0, type=int)
        
        ui_states = {
            C.SETTING_UI_LINK_OUT_IN: settings.value(C.SETTING_UI_LINK_OUT_IN, True, type=bool),
            C.SETTING_UI_SYNC_VIDEO: settings.value(C.SETTING_UI_SYNC_VIDEO, True, type=bool)
        }
        self.tableWindow.set_ui_states(ui_states)
        self.apply_font_size()

    # --- EN _save_settings ---
    def _save_settings(self):
        settings = QSettings("TuEmpresa", "EditorDeGuion")
        
        settings.setValue(C.SETTING_GEOMETRY, self.saveGeometry())
        settings.setValue(C.SETTING_SPLITTER_STATE, self.splitter.saveState())
        settings.setValue(C.SETTING_COLUMN_STATE, self.tableWindow.table_view.horizontalHeader().saveState())
        
        settings.setValue(C.SETTING_FONT_SIZE, self.font_size)
        settings.setValue(C.SETTING_LINE_LENGTH, self.line_length)
        settings.setValue(C.SETTING_TRIM_VALUE, self.trim_value)
        
        ui_states = self.tableWindow.get_ui_states()
        if C.SETTING_UI_LINK_OUT_IN in ui_states: # Nota: get_ui_states devuelve keys que debemos mapear si no coinciden
             # En tableWindow.get_ui_states usabas "link_out_in_enabled" hardcoded.
             # Lo ideal es cambiar tableWindow para que use las constantes también.
             pass
        # Por simplicidad, asumimos que TableWindow se actualiza en el paso 3.
        # Aquí guardamos los valores que nos devuelve
        for key, value in ui_states.items():
            settings.setValue(key, value)


    def closeEvent(self, event):
        def save_and_accept():
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
                if self.tableWindow.current_script_path:
                    if self.tableWindow.current_script_path.endswith(".json"):
                        self.guion_manager.save_to_json(self.tableWindow.current_script_path, self.tableWindow.pandas_model.dataframe(), self.tableWindow._get_header_data_from_ui())
                        saved_successfully = True
                    elif self.tableWindow.current_script_path.endswith(".xlsx"):
                        self.guion_manager.save_to_excel(self.tableWindow.current_script_path, self.tableWindow.pandas_model.dataframe(), self.tableWindow._get_header_data_from_ui())
                        saved_successfully = True
                    else:
                        saved_successfully = self.save_script_directly()
                else:
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

    def eventFilter(self, source, event: QEvent) -> bool:
            """
            Intercepta eventos destinados a otros widgets. En este caso,
            capturamos los eventos de Drag/Drop para el videoPlayerWidget.
            """
            if source is self.videoPlayerWidget:
                if event.type() == QEvent.Type.DragEnter:
                    drag_event = QDragEnterEvent(event)
                    self.dragEnterEvent(drag_event)
                    return True 
                
                elif event.type() == QEvent.Type.Drop:
                    drop_event = QDropEvent(event)
                    self.dropEvent(drop_event)
                    return True 

            return super().eventFilter(source, event)


    def dragEnterEvent(self, event: QDragEnterEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            if len(mime_data.urls()) == 1:
                file_path = mime_data.urls()[0].toLocalFile()
                _, extension = os.path.splitext(file_path.lower())
                
                video_exts = ['.mp4', '.mov', '.avi', '.mkv']
                script_exts = ['.json', '.xlsx', '.docx']
                
                if extension in video_exts or extension in script_exts:
                    event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls() and len(mime_data.urls()) == 1:
            file_path = mime_data.urls()[0].toLocalFile()
            _, extension = os.path.splitext(file_path.lower())

            logging.info(f"Archivo soltado en la aplicación: {file_path}")
            
            video_exts = ['.mp4', '.mov', '.avi', '.mkv']
            script_exts = {
                '.json': self.tableWindow.load_from_json_path,
                '.xlsx': self.tableWindow.load_from_excel_path,
                '.docx': self.tableWindow.load_from_docx_path,
            }
            
            try:
                if extension in video_exts:
                    self.videoPlayerWidget.load_video(file_path)
                    self.add_to_recent_files(file_path)
                    event.acceptProposedAction()
                elif extension in script_exts:
                    load_function = script_exts[extension]
                    load_function(file_path)
                    event.acceptProposedAction()
            except Exception as e:
                logging.error(f"Error al procesar el archivo soltado: {file_path}", exc_info=True)
                QMessageBox.critical(self, "Error al Abrir", f"No se pudo cargar el archivo arrastrado:\n{e}")

def handle_exception(exc_type, exc_value, exc_traceback):
    logging.critical("Excepción no controlada en el hilo principal:", exc_info=(exc_type, exc_value, exc_traceback))

    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    user_message = f"Ocurrió un error inesperado:\n\nTipo: {exc_type.__name__}\nMensaje: {exc_value}\n\n"
    user_message += "Se ha guardado un registro detallado del error en el archivo 'guion_editor.log'."

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
            logging.error(f"No se pudo mostrar el QMessageBox de error: {e_msgbox}")


def main():
    setup_logging()
    sys.excepthook = handle_exception
    app = QApplication(sys.argv)

    main_css_content = load_stylesheet_content("main.css")
    if main_css_content:
        app.setStyleSheet(main_css_content)
    else:
        logging.error("No se pudo cargar main.css globalmente.")


    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()