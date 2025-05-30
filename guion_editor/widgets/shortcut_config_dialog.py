# guion_editor/widgets/shortcut_config_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QInputDialog, QKeySequenceEdit, QAbstractItemView
)
from PyQt6.QtGui import QKeySequence, QIcon
from PyQt6.QtCore import Qt, QSize


class ShortcutConfigDialog(QDialog):
    def __init__(self, shortcut_manager, get_icon_func=None):
        super().__init__()
        self.shortcut_manager = shortcut_manager
        self.main_window = shortcut_manager.main_window # Access MainWindow for actions
        self.get_icon = get_icon_func
        self.setWindowTitle("Configurar Shortcuts")
        self.setMinimumSize(600, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        icon_size_buttons = QSize(18, 18)

        layout.addWidget(QLabel("Seleccione una acción para cambiar su shortcut:"))

        self.action_table = QTableWidget()
        self.action_table.setColumnCount(2)
        self.action_table.setHorizontalHeaderLabels(["Acción", "Shortcut"])
        self.action_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.action_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.action_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.action_table.horizontalHeader().setStretchLastSection(True)
        self.action_table.verticalHeader().setVisible(False) # Hide vertical header

        self.populate_table()
        layout.addWidget(self.action_table)

        layout.addWidget(QLabel("Presione las teclas para asignar el nuevo shortcut:"))
        self.shortcut_edit = QKeySequenceEdit()
        self.shortcut_edit.setKeySequence(QKeySequence())
        self.shortcut_edit.keySequenceChanged.connect(self.on_key_sequence_changed)
        layout.addWidget(self.shortcut_edit)

        btn_layout = QHBoxLayout()
        self.assign_btn = QPushButton(" Asignar")
        if self.get_icon:
            self.assign_btn.setIcon(self.get_icon("assign_shortcut_icon.svg"))
            self.assign_btn.setIconSize(icon_size_buttons)
        self.assign_btn.setEnabled(False)
        self.assign_btn.clicked.connect(self.assign_shortcut)
        btn_layout.addWidget(self.assign_btn)
        
        btn_layout.addStretch() # Push save to the right

        self.save_config_btn = QPushButton(" Guardar Perfil de Shortcuts")
        if self.get_icon:
            self.save_config_btn.setIcon(self.get_icon("save_config_icon.svg"))
            self.save_config_btn.setIconSize(icon_size_buttons)
        self.save_config_btn.clicked.connect(self.save_configuration_profile) # Renamed method
        btn_layout.addWidget(self.save_config_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.selected_action_object_name = None # Store objectName of selected QAction
        self.new_shortcut_sequence = QKeySequence() # Store QKeySequence directly

        self.action_table.itemSelectionChanged.connect(self.on_action_selected)

    def populate_table(self):
        self.action_table.setRowCount(0) # Clear table
        
        # Sort actions by their display text for consistent order
        sorted_actions = sorted(self.main_window.actions.values(), key=lambda act: act.text().replace("&", ""))
        
        self.action_table.setRowCount(len(sorted_actions))
        current_shortcuts_for_profile = self.shortcut_manager.configurations.get(self.shortcut_manager.current_config, {})

        for row, action in enumerate(sorted_actions):
            display_name = action.text().replace("&", "") # Clean display name
            action_object_name = action.objectName()
            
            # Get shortcut string from the current profile in shortcut_manager
            shortcut_str = current_shortcuts_for_profile.get(action_object_name, "")
            key_sequence = QKeySequence(shortcut_str)

            action_item = QTableWidgetItem(display_name)
            action_item.setData(Qt.ItemDataRole.UserRole, action_object_name) # Store objectName

            shortcut_display_str = key_sequence.toString(QKeySequence.SequenceFormat.NativeText)
            shortcut_item = QTableWidgetItem(shortcut_display_str)

            self.action_table.setItem(row, 0, action_item)
            self.action_table.setItem(row, 1, shortcut_item)
        
        self.action_table.resizeColumnsToContents()
        if self.action_table.columnCount() > 1:
             self.action_table.horizontalHeader().setStretchLastSection(True)


    def on_action_selected(self):
        selected_items = self.action_table.selectedItems()
        if selected_items:
            # We selected a row, item at column 0 is the action name item
            action_item_in_table = self.action_table.item(selected_items[0].row(), 0)
            self.selected_action_object_name = action_item_in_table.data(Qt.ItemDataRole.UserRole)
            
            # Get the QKeySequence from the QAction itself (which should be up-to-date)
            # or from the table's display if preferred (but QAction is source of truth)
            q_action = self.main_window.actions.get(self.selected_action_object_name)
            if q_action:
                current_key_sequence = q_action.shortcut()
                self.shortcut_edit.setKeySequence(current_key_sequence)
                self.new_shortcut_sequence = current_key_sequence # Initialize with current
                self.assign_btn.setEnabled(True) # Enable if an action is selected
            else: # Should not happen if populate_table is correct
                self.selected_action_object_name = None
                self.shortcut_edit.setKeySequence(QKeySequence())
                self.new_shortcut_sequence = QKeySequence()
                self.assign_btn.setEnabled(False)
        else:
            self.selected_action_object_name = None
            self.shortcut_edit.setKeySequence(QKeySequence())
            self.new_shortcut_sequence = QKeySequence()
            self.assign_btn.setEnabled(False)

    def on_key_sequence_changed(self, key_seq: QKeySequence):
        self.new_shortcut_sequence = key_seq
        # Assign button enabled if an action is selected, regardless of key_seq emptiness (to allow clearing)
        self.assign_btn.setEnabled(self.selected_action_object_name is not None)


    def assign_shortcut(self):
        if not self.selected_action_object_name:
            QMessageBox.warning(self, "Advertencia", "Seleccione una acción primero.")
            return

        new_shortcut_str_for_conflict_check = self.new_shortcut_sequence.toString(QKeySequence.SequenceFormat.PortableText)
        if not self.new_shortcut_sequence.isEmpty(): # Only check for conflicts if new shortcut is not empty
            for obj_name, action_instance in self.main_window.actions.items():
                if obj_name == self.selected_action_object_name:
                    continue # Don't compare with itself
                
                existing_shortcut = action_instance.shortcut()
                if not existing_shortcut.isEmpty() and existing_shortcut.toString(QKeySequence.SequenceFormat.PortableText) == new_shortcut_str_for_conflict_check:
                    QMessageBox.warning(
                        self, "Advertencia de Conflicto",
                        f"El shortcut '{self.new_shortcut_sequence.toString(QKeySequence.SequenceFormat.NativeText)}' "
                        f"ya está asignado a la acción '{action_instance.text().replace('&','')}'."
                    )
                    return

        q_action_to_modify = self.main_window.actions.get(self.selected_action_object_name)
        if q_action_to_modify:
            try:
                q_action_to_modify.setShortcut(self.new_shortcut_sequence)
                
                # Update the configuration in ShortcutManager
                current_config_name = self.shortcut_manager.current_config
                # Ensure the config exists (should always, but good practice)
                if current_config_name not in self.shortcut_manager.configurations:
                    self.shortcut_manager.configurations[current_config_name] = {}
                
                # Store as string for JSON
                self.shortcut_manager.configurations[current_config_name][self.selected_action_object_name] = \
                    self.new_shortcut_sequence.toString(QKeySequence.SequenceFormat.PortableText)

                self.shortcut_manager.save_shortcuts() # Save immediately
                
                action_display_name = q_action_to_modify.text().replace('&', '')
                if not self.new_shortcut_sequence.isEmpty():
                    QMessageBox.information(self, "Éxito", f"Shortcut asignado a '{action_display_name}'.")
                else:
                    QMessageBox.information(self, "Éxito", f"Shortcut eliminado para '{action_display_name}'.")
                
                self.populate_table() # Refresh table to show new shortcut
                
                # Optionally, clear selection and edit field, or re-select
                # self.new_shortcut_sequence = QKeySequence()
                # self.shortcut_edit.setKeySequence(QKeySequence())
                # self.assign_btn.setEnabled(False)
                # self.action_table.clearSelection()
                # self.selected_action_object_name = None

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error al asignar shortcut: {str(e)}")
        else:
            QMessageBox.warning(self, "Error", f"Acción '{self.selected_action_object_name}' no encontrada.")

    def save_configuration_profile(self): # Renamed from save_configuration
        name, ok = QInputDialog.getText(self, "Guardar Perfil de Shortcuts", 
                                        "Ingrese el nombre para este perfil de shortcuts:")
        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "Nombre Inválido", "El nombre del perfil no puede estar vacío.")
                return

            if name in self.shortcut_manager.configurations:
                overwrite = QMessageBox.question(
                    self, "Confirmar Sobrescritura",
                    f"Ya existe un perfil de shortcuts llamado '{name}'. ¿Desea sobrescribirlo?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No # Default to No
                )
                if overwrite == QMessageBox.StandardButton.No:
                    return
            
            # Get the currently configured shortcuts for the *active* profile
            # These are the shortcuts that have been potentially modified by 'assign_shortcut'
            # and are stored in self.shortcut_manager.configurations[self.shortcut_manager.current_config]
            current_active_shortcuts_map = self.shortcut_manager.configurations.get(
                                                self.shortcut_manager.current_config, {}).copy()

            try:
                self.shortcut_manager.add_configuration(name, current_active_shortcuts_map) # add_configuration also saves
                QMessageBox.information(self, "Éxito", f"Perfil de shortcuts '{name}' guardado exitosamente.")
                self.shortcut_manager.current_config = name # Switch to the new/overwritten profile
                self.shortcut_manager.apply_shortcuts(name) # Apply it
                self.shortcut_manager.refresh_shortcuts_menu() # Update main menu
                self.populate_table() # Refresh dialog table if current_config changed its display
            except Exception as e: # Covers ConfigurationExistsError if add_configuration raises it again
                 QMessageBox.warning(self, "Error al Guardar", str(e))