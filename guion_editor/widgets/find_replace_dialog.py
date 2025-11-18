from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QHBoxLayout,
    QPushButton, QMessageBox, QCheckBox, QAbstractItemView
)
from PyQt6.QtCore import QSize, Qt
from .. import constants as C

class FindReplaceDialog(QDialog):
    def __init__(self, table_window, get_icon_func=None):
        super().__init__()
        self.table_window = table_window
        self.get_icon = get_icon_func
        self.setWindowTitle("Find and Replace")
        self.current_search_results = []
        self.current_search_index = -1
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.find_text_input = QLineEdit()
        self.replace_text_input = QLineEdit()
        form_layout.addRow("Find:", self.find_text_input)
        form_layout.addRow("Replace with:", self.replace_text_input)

        self.search_in_character = QCheckBox("Search in Character")
        self.search_in_original = QCheckBox("Búsqueda en original")
        self.search_in_original.setChecked(False)
        self.search_in_euskera = QCheckBox("Búsqueda de Euskera")
        self.search_in_euskera.setChecked(True)

        layout.addLayout(form_layout)
        layout.addWidget(self.search_in_character)
        layout.addWidget(self.search_in_original)
        layout.addWidget(self.search_in_euskera)

        button_layout = QHBoxLayout()
        icon_size = QSize(18, 18)
        icon_only_button_size = QSize(32, 32)

        self.find_prev_button = QPushButton()
        if self.get_icon:
            self.find_prev_button.setIcon(self.get_icon("find_previous_icon.svg"))
        self.find_prev_button.setIconSize(icon_size)
        self.find_prev_button.setFixedSize(icon_only_button_size)
        self.find_prev_button.setToolTip("Find Previous")

        self.find_next_button = QPushButton()
        if self.get_icon:
            self.find_next_button.setIcon(self.get_icon("find_next_icon.svg"))
        self.find_next_button.setIconSize(icon_size)
        self.find_next_button.setFixedSize(icon_only_button_size)
        self.find_next_button.setToolTip("Find Next")

        self.replace_button = QPushButton(" Replace")
        if self.get_icon:
            self.replace_button.setIcon(self.get_icon("replace_one_icon.svg"))
        self.replace_button.setIconSize(icon_size)
        self.replace_button.setToolTip("Reemplaza la coincidencia actual y busca la siguiente")

        self.replace_all_button = QPushButton(" Replace All")
        if self.get_icon:
            self.replace_all_button.setIcon(self.get_icon("replace_all_icon.svg"))
        self.replace_all_button.setIconSize(icon_size)
        self.replace_all_button.setToolTip("Reemplaza todas las coincidencias en el documento")

        self.close_button = QPushButton()
        if self.get_icon:
            self.close_button.setIcon(self.get_icon("close_dialog_icon.svg"))
        self.close_button.setIconSize(icon_size)
        self.close_button.setFixedSize(icon_only_button_size)
        self.close_button.setToolTip("Close")

        button_layout.addWidget(self.find_prev_button)
        button_layout.addWidget(self.find_next_button)
        button_layout.addWidget(self.replace_button)
        button_layout.addWidget(self.replace_all_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        self.find_text_input.textChanged.connect(self.reset_search)
        self.find_next_button.clicked.connect(self.find_next)
        self.find_prev_button.clicked.connect(self.find_previous)
        self.replace_button.clicked.connect(self.replace_and_find)
        self.replace_all_button.clicked.connect(self.replace_all)
        self.close_button.clicked.connect(self.close)

    def replace_and_find(self):
        find_text = self.find_text_input.text()
        if not find_text:
            QMessageBox.information(self, "Reemplazar", "Por favor, introduzca texto para buscar.")
            return

        if not self.current_search_results or not (0 <= self.current_search_index < len(self.current_search_results)):
            self.find_next()
            return

        replace_text = self.replace_text_input.text()
        row_to_replace = self.current_search_results[self.current_search_index]

        replaced = self.table_window.replace_in_current_match(
            row_to_replace,
            find_text,
            replace_text,
            self.search_in_character.isChecked(),
            self.search_in_original.isChecked(),
            self.search_in_euskera.isChecked()
        )

        self.find_next()

    def set_search_parameters(self, find_text: str, search_character: bool, search_dialogue: bool):
        self.find_text_input.setText(find_text)
        self.search_in_character.setChecked(search_character)
        self.search_in_original.setChecked(search_dialogue)
        self.reset_search()
        if find_text:
            self.find_next()

    def perform_search(self):
        search_text = self.find_text_input.text().lower()
        self.current_search_results = []
        if not search_text:
            return

        model = self.table_window.pandas_model
        
        # Obtener los índices de columna de la vista desde las constantes
        col_char = C.VIEW_COL_CHARACTER
        col_original = C.VIEW_COL_DIALOGUE
        col_euskera = C.VIEW_COL_EUSKERA

        for row in range(model.rowCount()):
            found_in_row = False

            if self.search_in_character.isChecked():
                idx = model.index(row, col_char)
                data = model.data(idx, Qt.ItemDataRole.DisplayRole)
                text = ("" if data is None else str(data)).lower()
                if search_text in text:
                    found_in_row = True

            if not found_in_row and self.search_in_original.isChecked():
                idx = model.index(row, col_original)
                data = model.data(idx, Qt.ItemDataRole.DisplayRole)
                text = ("" if data is None else str(data)).lower()
                if search_text in text:
                    found_in_row = True

            if not found_in_row and self.search_in_euskera.isChecked():
                idx = model.index(row, col_euskera)
                data = model.data(idx, Qt.ItemDataRole.DisplayRole)
                text = ("" if data is None else str(data)).lower()
                if search_text in text:
                    found_in_row = True

            if found_in_row:
                self.current_search_results.append(row)

    def find_next(self):
        search_text = self.find_text_input.text().lower()
        if not search_text:
            QMessageBox.information(self, "Find", "Please enter text to search.")
            return

        if not self.current_search_results and self.find_text_input.text():
            self.perform_search()

        if not self.current_search_results:
            QMessageBox.information(self, "Find", "No matches found.")
            return

        self.current_search_index = (self.current_search_index + 1) % len(self.current_search_results)
        self.select_search_result()

    def find_previous(self):
        search_text = self.find_text_input.text().lower()
        if not search_text:
            QMessageBox.information(self, "Find", "Please enter text to search.")
            return

        if not self.current_search_results and self.find_text_input.text():
            self.perform_search()

        if not self.current_search_results:
            QMessageBox.information(self, "Find", "No matches found.")
            return

        self.current_search_index = (self.current_search_index - 1 + len(self.current_search_results)) % len(self.current_search_results)
        self.select_search_result()

    def select_search_result(self):
        if not self.current_search_results or not (0 <= self.current_search_index < len(self.current_search_results)):
            return

        row_to_select = self.current_search_results[self.current_search_index]
        self.table_window.table_view.selectRow(row_to_select)

        model = self.table_window.pandas_model
        index_to_scroll_to = model.index(row_to_select, 0)
        if index_to_scroll_to.isValid():
            self.table_window.table_view.scrollTo(index_to_scroll_to, QAbstractItemView.ScrollHint.EnsureVisible)

    def reset_search(self):
        self.current_search_results = []
        self.current_search_index = -1

    def replace_all(self):
        find_text = self.find_text_input.text()
        replace_text = self.replace_text_input.text()
        if not find_text:
            QMessageBox.information(self, "Replace", "Please enter text to search.")
            return
            
        self.table_window.find_and_replace(
            find_text,
            replace_text,
            self.search_in_character.isChecked(),
            self.search_in_original.isChecked(),
            self.search_in_euskera.isChecked()
        )
        self.reset_search()