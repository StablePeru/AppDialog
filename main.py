# main.py
import sys
import traceback
import json
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QSplitter, QDialog, QInputDialog,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence

from guion_editor.widgets.video_player_widget import VideoPlayerWidget
from guion_editor.widgets.table_window import TableWindow
from guion_editor.widgets.video_window import VideoWindow
from guion_editor.widgets.config_dialog import ConfigDialog
from guion_editor.widgets.shortcut_config_dialog import ShortcutConfigDialog
from guion_editor.utils.shortcut_manager import ShortcutManager
from guion_editor.utils.guion_manager import GuionManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor de Guion con Video")
        self.setGeometry(100, 100, 1600, 900)

        self.trim_value = 0
        self.font_size = 9

        self.guion_manager = GuionManager()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.videoPlayerWidget = VideoPlayerWidget()
        self.splitter.addWidget(self.videoPlayerWidget)

        self.tableWindow = TableWindow(self.videoPlayerWidget, main_window=self, guion_manager=self.guion_manager)
        self.splitter.addWidget(self.tableWindow)
        layout.addWidget(self.splitter)

        self.actions = {}
        self.recent_files = self.load_recent_files()
        self.create_video_actions()

        action_copy_in_out = QAction("Copiar IN/OUT a Siguiente", self)
        action_copy_in_out.triggered.connect(self.tableWindow.copy_in_out_to_next)
        self.addAction(action_copy_in_out)
        self.actions["Copiar IN/OUT a Siguiente"] = action_copy_in_out

        self.videoPlayerWidget.detach_requested.connect(self.detach_video)
        self.tableWindow.in_out_signal.connect(self.handle_set_position)
        self.videoWindow = None

        if "change_scene" not in self.actions:
            self.actions["change_scene"] = QAction("Change Scene Internal", self)
            self.actions["change_scene"].triggered.connect(self.change_scene)
            self.addAction(self.actions["change_scene"])

        self.create_menu_bar(exclude_shortcuts=True)
        self.shortcut_manager = ShortcutManager(self)
        self.create_shortcuts_menu(self.menuBar())

    def create_menu_bar(self, exclude_shortcuts=False):
        menuBar = self.menuBar()
        self.create_file_menu(menuBar)
        self.create_edit_menu(menuBar)
        self.create_config_menu(menuBar)
        if not exclude_shortcuts:
            self.create_shortcuts_menu(menuBar)

    def create_file_menu(self, menuBar):
        fileMenu = menuBar.addMenu("&Archivo")
        actions_data = [
            ("&Abrir Video", self.open_video_file, "Ctrl+O"),
            ("&Abrir Guion (DOCX)", self.tableWindow.open_docx_dialog, "Ctrl+G"),
            ("&Exportar Guion a Excel", self.tableWindow.export_to_excel_dialog, "Ctrl+E"),
            ("&Importar Guion desde Excel", self.tableWindow.import_from_excel_dialog, "Ctrl+I"),
            ("&Guardar Guion como JSON", self.tableWindow.save_to_json_dialog, "Ctrl+S"),
            ("&Cargar Guion desde JSON", self.tableWindow.load_from_json_dialog, "Ctrl+D"),
        ]
        for name, slot, shortcut_str in actions_data:
            action = self.create_action(name, slot, shortcut_str)
            fileMenu.addAction(action)
            self.actions[name] = action

        self.recent_files_menu = fileMenu.addMenu("Abrir Recientemente")
        self.update_recent_files_menu()

    def create_edit_menu(self, menuBar):
        editMenu = menuBar.addMenu("&Editar")
        actions_data = [
            ("&Agregar Línea", self.tableWindow.add_new_row, "Ctrl+N"),
            ("&Eliminar Fila", self.tableWindow.remove_row, "Ctrl+Del"),
            ("Mover &Arriba", self.tableWindow.move_row_up, "Alt+Up"),
            ("Mover &Abajo", self.tableWindow.move_row_down, "Alt+Down"),
            ("&Ajustar Diálogos", self.tableWindow.adjust_dialogs, None),
            ("&Separar Intervención", self.tableWindow.split_intervention, "Alt+I"),
            ("&Juntar Intervenciones", self.tableWindow.merge_interventions, "Alt+J"),
        ]

        view_cast_action = self.create_action("Ver Reparto Completo", self.open_cast_window)
        editMenu.addAction(view_cast_action)
        self.actions["Ver Reparto Completo"] = view_cast_action

        find_replace_action = self.create_action("Buscar y Reemplazar", self.open_find_replace_dialog)
        editMenu.addAction(find_replace_action)
        self.actions["Buscar y Reemplazar"] = find_replace_action

        for name, slot, shortcut_str in actions_data:
            action = self.create_action(name, slot, shortcut_str)
            editMenu.addAction(action)
            self.actions[name] = action

    def create_config_menu(self, menuBar):
        configMenu = menuBar.addMenu("&Configuración")
        openConfigAction = self.create_action("&Configuración", self.open_config_dialog)
        configMenu.addAction(openConfigAction)
        self.actions["&Configuración"] = openConfigAction

    def create_shortcuts_menu(self, menuBar):
        for action_menu_item in menuBar.actions():
            if action_menu_item.menu() and action_menu_item.menu().title() == "&Shortcuts":
                menuBar.removeAction(action_menu_item)
                break
        shortcutsMenu = menuBar.addMenu("&Shortcuts")
        configure_shortcuts_action = self.create_action("&Configurar Shortcuts", self.open_shortcut_config_dialog)
        shortcutsMenu.addAction(configure_shortcuts_action)
        self.actions["&Configurar Shortcuts"] = configure_shortcuts_action
        load_config_menu = shortcutsMenu.addMenu("Cargar Configuración")
        for config_name in self.shortcut_manager.configurations.keys():
            action = self.create_action(
                config_name,
                lambda checked, name=config_name: self.shortcut_manager.apply_shortcuts(name)
            )
            load_config_menu.addAction(action)
        delete_config_action = self.create_action("Eliminar Configuración", self.delete_configuration)
        shortcutsMenu.addAction(delete_config_action)
        self.actions["Eliminar Configuración"] = delete_config_action

    def update_recent_files_menu(self):
        self.recent_files_menu.clear()
        for file_path in self.recent_files:
            action = QAction(os.path.basename(file_path), self)
            action.setToolTip(file_path)
            action.triggered.connect(lambda checked, path=file_path: self.open_recent_file(path))
            self.recent_files_menu.addAction(action)

    def create_action(self, name, slot, shortcut_str=None):
        action = QAction(name, self)
        if shortcut_str:
            action.setShortcut(QKeySequence(shortcut_str))
        action.triggered.connect(slot)
        return action
    
    def create_video_actions(self):
        play_pause_action = self.create_action("Pausar/Reproducir", self.videoPlayerWidget.toggle_play)
        self.addAction(play_pause_action)
        self.actions["Pausar/Reproducir"] = play_pause_action
        rewind_action = self.create_action("Retroceder", lambda: self.videoPlayerWidget.change_position(-5000))
        self.addAction(rewind_action)
        self.actions["Retroceder"] = rewind_action
        forward_action = self.create_action("Avanzar", lambda: self.videoPlayerWidget.change_position(5000))
        self.addAction(forward_action)
        self.actions["Avanzar"] = forward_action

    def open_cast_window(self):
        from guion_editor.widgets.cast_window import CastWindow
        self.cast_window = CastWindow(self.tableWindow)
        self.cast_window.show()

    def open_find_replace_dialog(self):
        from guion_editor.widgets.find_replace_dialog import FindReplaceDialog
        from PyQt6.QtWidgets import QFileDialog # CAMBIO
        dialog = FindReplaceDialog(self.tableWindow)
        dialog.exec() # CAMBIO

    def open_recent_file(self, file_path):
        if os.path.exists(file_path):
            ext = file_path.lower().split('.')[-1]
            if ext in ('mp4', 'avi', 'mkv'):
                self.videoPlayerWidget.load_video(file_path)
            elif ext == 'xlsx':
                self.tableWindow.load_from_excel_path(file_path)
            elif ext == 'json':
                self.tableWindow.load_from_json_path(file_path)
            elif ext == 'docx':
                self.tableWindow.load_from_docx_path(file_path)
            else:
                QMessageBox.warning(self, "Error", "Tipo de archivo no soportado para abrir desde recientes.")
        else:
            QMessageBox.warning(self, "Error", f"El archivo reciente '{file_path}' no existe.")
            if file_path in self.recent_files:
                self.recent_files.remove(file_path)
            self.save_recent_files()
            self.update_recent_files_menu()

    def open_config_dialog(self):
        config_dialog = ConfigDialog(
            current_trim=self.trim_value,
            current_font_size=self.font_size
        )
        if config_dialog.exec() == QDialog.DialogCode.Accepted: # CAMBIO
            self.trim_value, self.font_size = config_dialog.get_values()
            self.apply_font_size()

    def add_to_recent_files(self, file_path):
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
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
                json.dump(self.recent_files, f)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al guardar archivos recientes: {str(e)}")

    def apply_font_size(self):
        font = self.tableWindow.table_widget.font()
        font.setPointSize(self.font_size)
        self.tableWindow.table_widget.setFont(font)
        header = self.tableWindow.table_widget.horizontalHeader()
        header_font = header.font()
        header_font.setPointSize(self.font_size)
        header.setFont(header_font)
        self.tableWindow.apply_font_size_to_dialogs(self.font_size)
        self.videoPlayerWidget.update_fonts(self.font_size)

    def open_shortcut_config_dialog(self):
        dialog = ShortcutConfigDialog(self.shortcut_manager)
        dialog.exec() # CAMBIO
        self.shortcut_manager.apply_shortcuts(self.shortcut_manager.current_config)

    def delete_configuration(self):
        configs = list(self.shortcut_manager.configurations.keys())
        if "default" in configs:
            configs.remove("default")
        if not configs:
            QMessageBox.information(self, "Información", "No hay configuraciones para eliminar.")
            return
        config, ok = QInputDialog.getItem(self,"Eliminar Configuración","Seleccione una configuración para eliminar:",configs,0,False)
        if ok and config:
            confirm = QMessageBox.question(self,"Confirmar",f"¿Está seguro de que desea eliminar la configuración '{config}'?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, # CAMBIO
                                           QMessageBox.StandardButton.Save) # CAMBIO
            if confirm == QMessageBox.StandardButton.Yes: # CAMBIO
                if self.shortcut_manager.delete_configuration(config):
                    QMessageBox.information(self,"Éxito",f"Configuración '{config}' eliminada exitosamente.")
                    self.create_shortcuts_menu(menuBar=self.menuBar())

    def open_video_file(self):
        from PyQt6.QtWidgets import QFileDialog # CAMBIO: Import específico
        file_name, _ = QFileDialog.getOpenFileName(self,"Abrir Video","","Videos (*.mp4 *.avi *.mkv);;Todos los archivos (*.*)")
        if file_name:
            self.videoPlayerWidget.load_video(file_name)
            self.add_to_recent_files(file_name)

    def detach_video(self, video_widget_ref):
        if self.videoWindow is not None: return
        try:
            if self.splitter.widget(0) == video_widget_ref:
                self.videoWindow = VideoWindow(video_widget_ref)
                self.videoWindow.close_detached.connect(self.attach_video)
                self.videoWindow.show()
            else:
                 QMessageBox.warning(self,"Error", "El widget a separar no es el esperado.")
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al detachar el video: {str(e)}")

    def attach_video(self):
        if self.videoWindow is None: return
        try:
            video_widget = self.videoWindow.video_widget
            self.splitter.insertWidget(0, video_widget)
            self.videoWindow.close() 
            self.videoWindow = None
            total_width = self.splitter.width()
            if total_width > 0:
                 self.splitter.setSizes([total_width // 2, total_width // 2])
            else:
                 self.splitter.setSizes([100,100])
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al adjuntar el video: {str(e)}")

    def handle_set_position(self, action, position_ms):
        try:
            adjusted_position = max(position_ms - self.trim_value, 0)
            self.videoPlayerWidget.set_position_public(adjusted_position)
        except Exception as e:
            QMessageBox.warning(self,"Error",f"Error al establecer la posición del video: {str(e)}")

    def change_scene(self):
        self.tableWindow.change_scene()

    def increment_scenes_from_row(self, start_row): 
        # Este método parece no estar siendo utilizado activamente y podría ser obsoleto
        # o necesitar una revisión si se planea usar.
        total_rows = self.tableWindow.table_widget.rowCount()
        for row in range(start_row, total_rows):
            scene_item = self.tableWindow.table_widget.item(row, 0) 
            if scene_item:
                try:
                    current_scene = int(scene_item.text())
                    scene_item.setText(str(current_scene + 1))
                except ValueError:
                    # Considerar mostrar un error al usuario o loggear
                    pass # Silenciosamente ignorar si no es un número

    def closeEvent(self, event):
        if self.tableWindow.unsaved_changes:
            reply = QMessageBox.question(self,"Guardar cambios","Hay cambios sin guardar. ¿Desea exportar el guion antes de salir?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, # CAMBIO
                                         QMessageBox.StandardButton.Save) # CAMBIO
            if reply == QMessageBox.StandardButton.Save: # CAMBIO
                try:
                    if self.tableWindow.export_to_excel_dialog(): 
                        event.accept()
                    else: 
                        event.ignore()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo guardar el guion: {str(e)}")
                    event.ignore()
            elif reply == QMessageBox.StandardButton.Discard: # CAMBIO
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
    # En producción, podrías escribir esto a un archivo de log en lugar de imprimirlo
    print(error_message) 
    QMessageBox.critical(None, "Error Inesperado", "Ocurrió un error inesperado. Consulte la consola o los logs para más detalles.")

def main():
    sys.excepthook = handle_exception
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()