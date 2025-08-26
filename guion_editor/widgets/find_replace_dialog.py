from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QHBoxLayout,
    QPushButton, QMessageBox, QCheckBox, QAbstractItemView
)
from PyQt6.QtCore import QSize, Qt

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

        # ——— Cajas de selección ———
        self.search_in_character = QCheckBox("Search in Character")
        # self.search_in_character.setChecked(True)

        # Renombrada y desactivada por defecto
        self.search_in_original = QCheckBox("Búsqueda en original")
        self.search_in_original.setChecked(False)

        # Nueva casilla: Euskera (activada por defecto)
        self.search_in_euskera = QCheckBox("Búsqueda de Euskera")
        self.search_in_euskera.setChecked(True)

        layout.addLayout(form_layout)
        layout.addWidget(self.search_in_character)
        layout.addWidget(self.search_in_original)
        layout.addWidget(self.search_in_euskera)

        # ——— Botonera ———
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

        # -> INICIO: BOTONES DE REEMPLAZO MODIFICADOS
        self.replace_button = QPushButton(" Replace")
        if self.get_icon:
            self.replace_button.setIcon(self.get_icon("replace_one_icon.svg")) # Sugerencia de nuevo icono
        self.replace_button.setIconSize(icon_size)
        self.replace_button.setToolTip("Reemplaza la coincidencia actual y busca la siguiente")

        self.replace_all_button = QPushButton(" Replace All")
        if self.get_icon:
            self.replace_all_button.setIcon(self.get_icon("replace_all_icon.svg"))
        self.replace_all_button.setIconSize(icon_size)
        self.replace_all_button.setToolTip("Reemplaza todas las coincidencias en el documento")
        # -> FIN: BOTONES DE REEMPLAZO MODIFICADOS

        self.close_button = QPushButton()
        if self.get_icon:
            self.close_button.setIcon(self.get_icon("close_dialog_icon.svg"))
        self.close_button.setIconSize(icon_size)
        self.close_button.setFixedSize(icon_only_button_size)
        self.close_button.setToolTip("Close")

        button_layout.addWidget(self.find_prev_button)
        button_layout.addWidget(self.find_next_button)
        button_layout.addWidget(self.replace_button)      # -> AÑADIDO
        button_layout.addWidget(self.replace_all_button)  # -> RENOMBRADO
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        self.find_text_input.textChanged.connect(self.reset_search)
        self.find_next_button.clicked.connect(self.find_next)
        self.find_prev_button.clicked.connect(self.find_previous)
        self.replace_button.clicked.connect(self.replace_and_find) # -> AÑADIDO
        self.replace_all_button.clicked.connect(self.replace_all) # -> RENOMBRADO
        self.close_button.clicked.connect(self.close)

    # -> INICIO: NUEVO MÉTODO
    def replace_and_find(self):
        """Reemplaza la coincidencia actual y busca la siguiente."""
        find_text = self.find_text_input.text()
        if not find_text:
            QMessageBox.information(self, "Reemplazar", "Por favor, introduzca texto para buscar.")
            return

        if not self.current_search_results or not (0 <= self.current_search_index < len(self.current_search_results)):
            self.find_next()
            return

        replace_text = self.replace_text_input.text()
        row_to_replace = self.current_search_results[self.current_search_index]

        # Llama a un nuevo método en table_window que se encarga de reemplazar en la fila actual
        replaced = self.table_window.replace_in_current_match(
            row_to_replace,
            find_text,
            replace_text,
            self.search_in_character.isChecked(),
            self.search_in_original.isChecked(),
            self.search_in_euskera.isChecked()
        )

        # Después de reemplazar, simplemente busca el siguiente
        self.find_next()
    # -> FIN: NUEVO MÉTODO

    def set_search_parameters(self, find_text: str, search_character: bool, search_dialogue: bool):
        """
        Compatibilidad hacia atrás:
        - search_dialogue ahora controla 'Búsqueda en original'.
        - 'Búsqueda de Euskera' queda según su valor por defecto (True),
          a menos que quieras añadir un 4º parámetro opcional en el futuro.
        """
        self.find_text_input.setText(find_text)
        self.search_in_character.setChecked(search_character)
        self.search_in_original.setChecked(search_dialogue)
        # self.search_in_euskera mantiene su estado por defecto (True)

        self.reset_search()
        if find_text:
            self.find_next()

    def perform_search(self):
        """Realiza la búsqueda en las columnas seleccionadas."""
        search_text = self.find_text_input.text().lower()
        self.current_search_results = []
        if not search_text:
            return

        model = self.table_window.pandas_model

        print(f"--- Starting search for: '{search_text}' ---")
        print(f"Search in Character: {self.search_in_character.isChecked()}")
        print(f"Búsqueda en original: {self.search_in_original.isChecked()}")
        print(f"Búsqueda de Euskera: {self.search_in_euskera.isChecked()}")

        col_char = getattr(self.table_window, "COL_CHARACTER_VIEW", None)
        col_original = getattr(self.table_window, "COL_DIALOGUE_VIEW", None)
        col_euskera = getattr(self.table_window, "COL_EUSKERA_VIEW", None)

        for row in range(model.rowCount()):
            found_in_row = False

            if self.search_in_character.isChecked() and col_char is not None:
                idx = model.index(row, col_char)
                data = model.data(idx, Qt.ItemDataRole.DisplayRole)
                text = ("" if data is None else str(data)).lower()
                if search_text in text:
                    found_in_row = True

            if self.search_in_original.isChecked() and col_original is not None:
                idx = model.index(row, col_original)
                data = model.data(idx, Qt.ItemDataRole.DisplayRole)
                text = ("" if data is None else str(data)).lower()
                if search_text in text:
                    found_in_row = True

            if self.search_in_euskera.isChecked():
                if col_euskera is None:
                    # Evita crasheos si aún no definiste la constante en TableWindow
                    if row == 0:
                        print("⚠️  COL_EUSKERA_VIEW no definido en TableWindow; se omite búsqueda en Euskera.")
                else:
                    idx = model.index(row, col_euskera)
                    data = model.data(idx, Qt.ItemDataRole.DisplayRole)
                    text = ("" if data is None else str(data)).lower()
                    if search_text in text:
                        found_in_row = True

            if found_in_row:
                self.current_search_results.append(row)

        print(f"--- Search finished. Results indices: {self.current_search_results} ---")

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
        """Reemplaza según las casillas activas (incluyendo Euskera si tu TableWindow lo soporta)."""
        find_text = self.find_text_input.text()
        replace_text = self.replace_text_input.text()
        if not find_text:
            QMessageBox.information(self, "Replace", "Please enter text to search.")
            return

        # Intento con nuevo flag de Euskera; si tu método aún no lo acepta, hago fallback.
        try:
            self.table_window.find_and_replace(
                find_text,
                replace_text,
                self.search_in_character.isChecked(),
                self.search_in_original.isChecked(),
                self.search_in_euskera.isChecked()
            )
        except TypeError:
            # Compatibilidad con implementación previa (sin Euskera)
            self.table_window.find_and_replace(
                find_text,
                replace_text,
                self.search_in_character.isChecked(),
                self.search_in_original.isChecked()
            )

        self.reset_search()