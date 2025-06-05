import os
from PyQt6.QtGui import QAction

class MenuManager:
    def __init__(self, main_window):
        """
        Initializes the MenuManager.

        Args:
            main_window: The main window instance.
        """
        self.main_window = main_window

    def create_menu_bar(self, exclude_shortcuts=False):
        """
        Creates the main menu bar for the application.

        Populates the menu bar with File, Edit, Config, and (optionally) Shortcuts menus.

        Args:
            exclude_shortcuts (bool, optional): If True, the shortcuts menu is not
                                                added directly by this function.
                                                Defaults to False.
        """
        menuBar = self.main_window.menuBar()
        self.create_file_menu(menuBar)
        self.create_edit_menu(menuBar)
        self.create_config_menu(menuBar)
        if not exclude_shortcuts:
            self.create_shortcuts_menu(menuBar)

    def create_file_menu(self, menuBar):
        """
        Creates and populates the 'File' menu.
        """
        fileMenu = menuBar.addMenu("&Archivo")
        fileMenu.addAction(self.main_window.actions["file_open_video"])
        fileMenu.addAction(self.main_window.actions["file_load_me"])
        fileMenu.addAction(self.main_window.actions["file_open_docx"])
        fileMenu.addSeparator()
        fileMenu.addAction(self.main_window.actions["file_export_excel"])
        fileMenu.addAction(self.main_window.actions["file_import_excel"])
        fileMenu.addSeparator()
        fileMenu.addAction(self.main_window.actions["file_save_json"])
        fileMenu.addAction(self.main_window.actions["file_load_json"])
        fileMenu.addSeparator()

        self.main_window.recent_files_menu = fileMenu.addMenu("Abrir Recientemente")
        self.main_window.recent_files_menu.setIcon(self.main_window.get_icon_proxy("history_icon.svg"))
        self.update_recent_files_menu()

    def create_edit_menu(self, menuBar):
        """
        Creates and populates the 'Edit' menu.
        """
        editMenu = menuBar.addMenu("&Editar")
        if "edit_undo" in self.main_window.actions: editMenu.addAction(self.main_window.actions["edit_undo"])
        if "edit_redo" in self.main_window.actions: editMenu.addAction(self.main_window.actions["edit_redo"])
        editMenu.addSeparator()

        editMenu.addAction(self.main_window.actions["edit_add_row"])
        editMenu.addAction(self.main_window.actions["edit_delete_row"])
        editMenu.addAction(self.main_window.actions["edit_move_up"])
        editMenu.addAction(self.main_window.actions["edit_move_down"])
        editMenu.addSeparator()
        editMenu.addAction(self.main_window.actions["edit_adjust_dialogs"])
        editMenu.addAction(self.main_window.actions["edit_split_intervention"])
        editMenu.addAction(self.main_window.actions["edit_merge_interventions"])
        editMenu.addSeparator()
        editMenu.addAction(self.main_window.actions["edit_view_cast"])
        editMenu.addAction(self.main_window.actions["edit_find_replace"])
        editMenu.addSeparator()
        editMenu.addAction(self.main_window.actions["edit_copy_in_out"])
        editMenu.addAction(self.main_window.actions["edit_increment_scene"])

    def create_config_menu(self, menuBar):
        """
        Creates and populates the 'Config' menu.
        """
        configMenu = menuBar.addMenu("&Herramientas")
        configMenu.addAction(self.main_window.actions["config_app_settings"])

    def create_shortcuts_menu(self, menuBar):
        """
        Creates and populates the 'Shortcuts' menu.
        """
        for action_menu_item in menuBar.actions():
            if action_menu_item.menu() and action_menu_item.menu().title() == "&Shortcuts":
                menuBar.removeAction(action_menu_item)
                break

        shortcutsMenu = menuBar.addMenu("&Shortcuts")
        shortcutsMenu.addAction(self.main_window.actions["config_shortcuts_dialog"])

        load_config_menu = shortcutsMenu.addMenu("Cargar Configuración de Shortcuts")
        load_config_menu.setIcon(self.main_window.get_icon_proxy("load_config_icon.svg"))
        if hasattr(self.main_window, 'shortcut_manager') and self.main_window.shortcut_manager:
            for config_name in self.main_window.shortcut_manager.configurations.keys():
                action = QAction(config_name, self.main_window) # Parent is main_window
                action.triggered.connect(lambda checked, name=config_name: self.main_window.shortcut_manager.apply_shortcuts(name))
                load_config_menu.addAction(action)

        delete_config_action = self.main_window.add_managed_action(
            "Eliminar Configuración de Shortcuts",
            self.main_window.delete_shortcut_configuration,
            None,
            "delete_config_icon.svg",
            "config_delete_shortcut_profile"
        )
        shortcutsMenu.addAction(delete_config_action)

    def update_recent_files_menu(self):
        """
        Updates the 'Open Recent' submenu in the File menu.
        """
        if not hasattr(self.main_window, 'recent_files_menu') or not self.main_window.recent_files_menu:
            return # Menu might not be created yet or already removed
            
        self.main_window.recent_files_menu.clear()
        for file_path in self.main_window.recent_files:
            action = QAction(os.path.basename(file_path), self.main_window) # Parent is main_window
            action.setIcon(self.main_window.get_icon_proxy("open_document_icon.svg"))
            action.setToolTip(file_path)
            action.triggered.connect(lambda checked, path=file_path: self.main_window.open_recent_file(path))
            self.main_window.recent_files_menu.addAction(action)
