from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QHBoxLayout, QPushButton, QMessageBox, QCheckBox
class FindReplaceDialog(QDialog):
    def __init__(self, table_window):
        """Inicializa el cuadro de diálogo de búsqueda y reemplazo."""
        super().__init__()
        self.table_window = table_window
        self.setWindowTitle("Find and Replace")
        self.current_search_results = []
        self.current_search_index = -1

        self.setup_ui()

    def setup_ui(self):
        """Configura la interfaz de usuario del cuadro de diálogo."""
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Campos de entrada de texto para buscar y reemplazar
        self.find_text_input = QLineEdit()
        self.replace_text_input = QLineEdit()
        form_layout.addRow("Find:", self.find_text_input)
        form_layout.addRow("Replace with:", self.replace_text_input)

        # Añadir opciones de búsqueda
        self.search_in_character = QCheckBox("Search in Character")
        self.search_in_dialogue = QCheckBox("Search in Dialogue")
        self.search_in_dialogue.setChecked(True)  # Buscar en Diálogo por defecto

        layout.addLayout(form_layout)
        layout.addWidget(self.search_in_character)
        layout.addWidget(self.search_in_dialogue)

        # Botones de acción
        button_layout = QHBoxLayout()
        self.find_prev_button = QPushButton("Find Previous")
        self.find_next_button = QPushButton("Find Next")
        self.replace_button = QPushButton("Replace All")
        self.close_button = QPushButton("Close")

        button_layout.addWidget(self.find_prev_button)
        button_layout.addWidget(self.find_next_button)
        button_layout.addWidget(self.replace_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        # Conectar señales de eventos
        self.find_text_input.textChanged.connect(self.reset_search)
        self.find_next_button.clicked.connect(self.find_next)
        self.find_prev_button.clicked.connect(self.find_previous)
        self.replace_button.clicked.connect(self.replace_all)
        self.close_button.clicked.connect(self.close)

    def perform_search(self):
        """Realiza la búsqueda de texto en las filas de la tabla."""
        search_text = self.find_text_input.text().lower()
        self.current_search_results = []
        if not search_text:
            return
        for row in range(self.table_window.table_widget.rowCount()):
            found_in_row = False
            # Buscar en la columna 'Character' si está seleccionado
            if self.search_in_character.isChecked():
                character_item = self.table_window.table_widget.item(row, 4)
                character_text = character_item.text().lower() if character_item else ''
                if search_text in character_text:
                    found_in_row = True
            # Buscar en la columna 'Dialogue' si está seleccionado
            if self.search_in_dialogue.isChecked():
                dialog_widget = self.table_window.table_widget.cellWidget(row, 5)
                dialog_text = dialog_widget.toPlainText().lower() if dialog_widget else ''
                if search_text in dialog_text:
                    found_in_row = True
            if found_in_row:
                self.current_search_results.append(row)

    def find_next(self):
        """Busca la siguiente ocurrencia del texto en la tabla."""
        search_text = self.find_text_input.text().lower()
        if not search_text:
            QMessageBox.information(self, "Find", "Please enter text to search.")
            return
        if not self.current_search_results:
            self.perform_search()
        if not self.current_search_results:
            QMessageBox.information(self, "Find", "No matches found.")
            return
        self.current_search_index = (self.current_search_index + 1) % len(self.current_search_results)
        self.select_search_result()

    def find_previous(self):
        """Busca la ocurrencia anterior del texto en la tabla."""
        search_text = self.find_text_input.text().lower()
        if not search_text:
            QMessageBox.information(self, "Find", "Please enter text to search.")
            return
        if not self.current_search_results:
            self.perform_search()
        if not self.current_search_results:
            QMessageBox.information(self, "Find", "No matches found.")
            return
        self.current_search_index = (self.current_search_index - 1) % len(self.current_search_results)
        self.select_search_result()

    def select_search_result(self):
        """Selecciona el resultado de búsqueda actual en la tabla."""
        row = self.current_search_results[self.current_search_index]
        self.table_window.table_widget.selectRow(row)
        self.table_window.table_widget.scrollToItem(self.table_window.table_widget.item(row, 0))

    def reset_search(self):
        """Resetea el estado de la búsqueda actual."""
        self.current_search_results = []
        self.current_search_index = -1

    def replace_all(self):
        """Reemplaza todas las ocurrencias del texto buscado por el texto de reemplazo."""
        find_text = self.find_text_input.text()
        replace_text = self.replace_text_input.text()
        if not find_text:
            QMessageBox.information(self, "Replace", "Please enter text to search.")
            return
        self.table_window.find_and_replace(find_text, replace_text, self.search_in_character.isChecked(), self.search_in_dialogue.isChecked())
