from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QInputDialog, QKeySequenceEdit, QAbstractItemView
)
from PyQt6.QtGui import QKeySequence, QIcon # Añadir QIcon
from PyQt6.QtCore import Qt, QSize          # Añadir QSize


class ShortcutConfigDialog(QDialog):
    def __init__(self, shortcut_manager, get_icon_func=None): # Añadir get_icon_func
        """Inicializa el diálogo de configuración de shortcuts."""
        super().__init__()
        self.shortcut_manager = shortcut_manager
        self.get_icon = get_icon_func # Guardar la función helper
        self.setWindowTitle("Configure Shortcuts")
        self.setMinimumSize(600, 400)
        self.init_ui()

    def init_ui(self):
        """Configura los elementos de la interfaz de usuario."""
        layout = QVBoxLayout()
        icon_size_buttons = QSize(18, 18) # Tamaño para iconos en botones

        # Añadir etiqueta de instrucciones
        layout.addWidget(QLabel("Seleccione una acción para cambiar su shortcut:"))

        # Crear tabla para mostrar las acciones y sus shortcuts
        self.action_table = QTableWidget()
        self.action_table.setColumnCount(2)
        self.action_table.setHorizontalHeaderLabels(["Acción", "Shortcut"])
        self.action_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.action_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.action_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.action_table.horizontalHeader().setStretchLastSection(True)

        # Llenar la tabla con las acciones disponibles
        self.populate_table()

        layout.addWidget(self.action_table)

        # Añadir etiqueta para el nuevo shortcut
        layout.addWidget(QLabel("Presione las teclas para asignar el nuevo shortcut:"))

        # Crear campo de entrada para la secuencia de teclas
        self.shortcut_edit = QKeySequenceEdit()
        self.shortcut_edit.setKeySequence(QKeySequence())
        self.shortcut_edit.keySequenceChanged.connect(self.on_key_sequence_changed)
        layout.addWidget(self.shortcut_edit)

        # Crear botones de asignar y guardar configuración
        btn_layout = QHBoxLayout()
        self.assign_btn = QPushButton(" Asignar") # Espacio para el icono
        if self.get_icon:
            self.assign_btn.setIcon(self.get_icon("assign_shortcut_icon.svg"))
            self.assign_btn.setIconSize(icon_size_buttons)
        self.assign_btn.setEnabled(False)
        self.assign_btn.clicked.connect(self.assign_shortcut)
        btn_layout.addWidget(self.assign_btn)

        self.save_config_btn = QPushButton(" Guardar Configuración") # Espacio para el icono
        if self.get_icon:
            self.save_config_btn.setIcon(self.get_icon("save_config_icon.svg"))
            self.save_config_btn.setIconSize(icon_size_buttons)
        self.save_config_btn.clicked.connect(self.save_configuration)
        btn_layout.addWidget(self.save_config_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # Inicializar variables de estado
        self.selected_action_internal = None
        self.new_shortcut = ""

        # Conectar la señal de selección de la tabla
        self.action_table.itemSelectionChanged.connect(self.on_action_selected)

    def populate_table(self):
        """Llena la tabla con las acciones y sus shortcuts actuales."""
        actions = self.shortcut_manager.main_window.actions
        self.action_table.setRowCount(len(actions))
        for row, (action_name, action) in enumerate(actions.items()):
            display_name = action_name
            shortcut = action.shortcut().toString()

            action_item = QTableWidgetItem(display_name)
            shortcut_item = QTableWidgetItem(shortcut if shortcut else "")

            action_item.setData(Qt.ItemDataRole.UserRole, action_name) 

            self.action_table.setItem(row, 0, action_item)
            self.action_table.setItem(row, 1, shortcut_item)

    def on_action_selected(self):
        selected_items = self.action_table.selectedItems()
        if selected_items:
            action_item = selected_items[0] 
            shortcut_item_candidate = self.action_table.item(action_item.row(), 1) 
            if not shortcut_item_candidate: return

            shortcut = shortcut_item_candidate.text()
            self.selected_action_internal = action_item.data(Qt.ItemDataRole.UserRole)
            self.shortcut_edit.setKeySequence(QKeySequence(shortcut))
            self.new_shortcut = shortcut
            self.assign_btn.setEnabled(bool(shortcut))
        else:
            self.selected_action_internal = None
            self.shortcut_edit.setKeySequence(QKeySequence())
            self.new_shortcut = ""
            self.assign_btn.setEnabled(False)

    def on_key_sequence_changed(self, key_seq: QKeySequence):
        if key_seq.isEmpty():
            self.assign_btn.setEnabled(False)
            self.new_shortcut = ""
        else:
            self.assign_btn.setEnabled(True)
            self.new_shortcut = key_seq.toString(QKeySequence.SequenceFormat.NativeText)

    def assign_shortcut(self):
        """Asigna un nuevo shortcut a la acción seleccionada."""
        if not self.selected_action_internal:
            QMessageBox.warning(self, "Advertencia", "Seleccione una acción primero.")
            return
        if not self.new_shortcut:
            QMessageBox.warning(self, "Advertencia", "Ingrese un shortcut válido.")
            return

        for action_name_iter, shortcut_iter in self.shortcut_manager.configurations[self.shortcut_manager.current_config].items():
            if shortcut_iter == self.new_shortcut and action_name_iter != self.selected_action_internal:
                display_conflict_action = action_name_iter.replace("&", "")
                QMessageBox.warning(
                    self,
                    "Advertencia",
                    f"El shortcut '{self.new_shortcut}' ya está asignado a '{display_conflict_action}'."
                )
                return

        action = self.shortcut_manager.main_window.actions.get(self.selected_action_internal)
        if action:
            try:
                key_seq = QKeySequence(self.new_shortcut)
                if key_seq.isEmpty() and self.new_shortcut != "": # Permite borrar un shortcut asignando una secuencia vacía si new_shortcut es explicitamente ""
                    action.setShortcut(QKeySequence()) # Borra el shortcut
                elif not key_seq.isEmpty():
                    action.setShortcut(key_seq)
                else: # Si new_shortcut es "" y key_seq es empty (porque se borró el texto del QKeySequenceEdit)
                    action.setShortcut(QKeySequence()) # Borra el shortcut
                    # QMessageBox.information(self, "Información", f"Shortcut eliminado para '{self.selected_action_internal.replace('&', '')}'.")
                    # No es necesario este mensaje si el comportamiento es simplemente borrar

                self.shortcut_manager.configurations[self.shortcut_manager.current_config][self.selected_action_internal] = self.new_shortcut if not key_seq.isEmpty() else ""
                self.shortcut_manager.save_shortcuts()
                if not key_seq.isEmpty():
                    QMessageBox.information(self, "Éxito", f"Shortcut asignado a '{self.selected_action_internal.replace('&', '')}'.")
                else:
                    QMessageBox.information(self, "Éxito", f"Shortcut eliminado para '{self.selected_action_internal.replace('&', '')}'.")

                self.new_shortcut = "" # Reset
                self.shortcut_edit.setKeySequence(QKeySequence()) # Reset
                self.assign_btn.setEnabled(False) # Disable button
                self.populate_table() # Refresh table
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error al asignar shortcut: {str(e)}")
        else:
            QMessageBox.warning(self, "Error", f"Acción '{self.selected_action_internal}' no encontrada.")

    def save_configuration(self):
        name, ok = QInputDialog.getText(self, "Guardar Configuración", "Ingrese el nombre para la configuración:")
        if ok and name:
            if name in self.shortcut_manager.configurations:
                overwrite = QMessageBox.question(
                    self, "Confirmar",
                    f"Ya existe una configuración llamada '{name}'. ¿Desea sobrescribirla?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if overwrite == QMessageBox.StandardButton.No:
                    return
            current_shortcuts = self.shortcut_manager.configurations[self.shortcut_manager.current_config].copy()
            self.shortcut_manager.configurations[name] = current_shortcuts
            self.shortcut_manager.save_shortcuts()
            QMessageBox.information(self, "Éxito", f"Configuración '{name}' guardada exitosamente.")
            # Actualizar el menú principal para reflejar la nueva configuración guardada
            self.shortcut_manager.refresh_shortcuts_menu()