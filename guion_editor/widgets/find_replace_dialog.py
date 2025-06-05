# guion_editor/widgets/find_replace_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QHBoxLayout, 
    QPushButton, QMessageBox, QCheckBox, QAbstractItemView
)
from PyQt6.QtGui import QIcon
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

        self.search_in_character = QCheckBox("Search in Character")
        # self.search_in_character.setChecked(True) # <--- Uncomment this line if you want it checked by default
        self.search_in_dialogue = QCheckBox("Search in Dialogue")
        self.search_in_dialogue.setChecked(True)

        layout.addLayout(form_layout)
        layout.addWidget(self.search_in_character)
        layout.addWidget(self.search_in_dialogue)

        button_layout = QHBoxLayout()
        icon_size = QSize(18,18)
        icon_only_button_size = QSize(32,32)

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

        self.replace_button = QPushButton(" Replace All")
        if self.get_icon:
            self.replace_button.setIcon(self.get_icon("replace_all_icon.svg"))
        self.replace_button.setIconSize(icon_size)

        self.close_button = QPushButton()
        if self.get_icon:
            self.close_button.setIcon(self.get_icon("close_dialog_icon.svg"))
        self.close_button.setIconSize(icon_size)
        self.close_button.setFixedSize(icon_only_button_size)
        self.close_button.setToolTip("Close")


        button_layout.addWidget(self.find_prev_button)
        button_layout.addWidget(self.find_next_button)
        button_layout.addWidget(self.replace_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        self.find_text_input.textChanged.connect(self.reset_search)
        self.find_next_button.clicked.connect(self.find_next)
        self.find_prev_button.clicked.connect(self.find_previous)
        self.replace_button.clicked.connect(self.replace_all)
        self.close_button.clicked.connect(self.close)

    def set_search_parameters(self, find_text: str, search_character: bool, search_dialogue: bool):
        """
        Sets the initial parameters for the find/replace dialog.
        """
        self.find_text_input.setText(find_text)
        self.search_in_character.setChecked(search_character)
        self.search_in_dialogue.setChecked(search_dialogue)
        
        # Important: Reset any previous search state when parameters are set externally
        self.reset_search() 
        if find_text:
            self.find_next() 

    def perform_search(self):
        """Realiza la búsqueda de texto en las filas de la tabla."""
        search_text = self.find_text_input.text().lower()
        self.current_search_results = []
        if not search_text:
            return
        
        model = self.table_window.pandas_model 

        print(f"--- Starting search for: '{search_text}' ---")
        print(f"Search in Character: {self.search_in_character.isChecked()}")
        print(f"Search in Dialogue: {self.search_in_dialogue.isChecked()}")

        for row in range(model.rowCount()): 
            found_in_row = False
            
            if self.search_in_character.isChecked():
                char_model_index = model.index(row, self.table_window.COL_CHARACTER_VIEW)
                character_data = model.data(char_model_index, Qt.ItemDataRole.DisplayRole)
                character_text = str(character_data).lower() if character_data is not None else ''
                
                print(f"  Row {row} [Char]: Comparing '{search_text}' with Data='{character_data}' (Processed='{character_text}')")

                if search_text in character_text:
                    print(f"    [Char] FOUND at row {row}")
                    found_in_row = True
            
            if self.search_in_dialogue.isChecked():
                dialog_model_index = model.index(row, self.table_window.COL_DIALOGUE_VIEW)
                dialogue_data = model.data(dialog_model_index, Qt.ItemDataRole.DisplayRole)
                dialog_text = str(dialogue_data).lower() if dialogue_data is not None else ''

                print(f"  Row {row} [Dialogue]: Comparing '{search_text}' with Data='{dialogue_data}' (Processed='{dialog_text}')")

                if search_text in dialog_text:
                    print(f"    [Dialogue] FOUND at row {row}")
                    found_in_row = True
            
            if found_in_row:
                self.current_search_results.append(row)
        
        print(f"--- Search finished. Results indices: {self.current_search_results} ---")


    def find_next(self):
        """Busca la siguiente ocurrencia del texto en la tabla."""
        search_text = self.find_text_input.text().lower()
        if not search_text:
            QMessageBox.information(self, "Find", "Please enter text to search.")
            return
        
        # Perform search only if results are empty or search text changed (implicitly handled by reset_search on textChanged)
        # For robustness, we could always perform_search if current_search_results is empty
        if not self.current_search_results and self.find_text_input.text(): # Only search if there's text and no prior results
            print("find_next: No current results, performing search...")
            self.perform_search()
        
        if not self.current_search_results:
            print("find_next: Still no results after search.")
            QMessageBox.information(self, "Find", "No matches found.")
            return
            
        self.current_search_index = (self.current_search_index + 1) % len(self.current_search_results)
        print(f"find_next: Selecting result index {self.current_search_index} (model row {self.current_search_results[self.current_search_index]})")
        self.select_search_result()

    def find_previous(self):
        """Busca la ocurrencia anterior del texto en la tabla."""
        search_text = self.find_text_input.text().lower()
        if not search_text:
            QMessageBox.information(self, "Find", "Please enter text to search.")
            return

        if not self.current_search_results and self.find_text_input.text():
            print("find_previous: No current results, performing search...")
            self.perform_search()

        if not self.current_search_results:
            print("find_previous: Still no results after search.")
            QMessageBox.information(self, "Find", "No matches found.")
            return
            
        self.current_search_index = (self.current_search_index - 1 + len(self.current_search_results)) % len(self.current_search_results)
        print(f"find_previous: Selecting result index {self.current_search_index} (model row {self.current_search_results[self.current_search_index]})")
        self.select_search_result()

    def select_search_result(self):
        """Selecciona el resultado de búsqueda actual en la tabla."""
        if not self.current_search_results or not (0 <= self.current_search_index < len(self.current_search_results)):
            print("select_search_result: Invalid search index or no results.")
            return

        row_to_select = self.current_search_results[self.current_search_index]
        
        self.table_window.table_view.selectRow(row_to_select) 
        
        model = self.table_window.pandas_model
        index_to_scroll_to = model.index(row_to_select, 0) 
        
        if index_to_scroll_to.isValid():
            self.table_window.table_view.scrollTo(index_to_scroll_to, QAbstractItemView.ScrollHint.EnsureVisible)
        else:
            print(f"select_search_result: Could not get valid QModelIndex for scrolling to row {row_to_select}, col 0")


    def reset_search(self):
        """Resetea el estado de la búsqueda actual."""
        print("reset_search: Clearing search results and index.")
        self.current_search_results = []
        self.current_search_index = -1

    def replace_all(self):
        """Reemplaza todas las ocurrencias del texto buscado por el texto de reemplazo."""
        find_text = self.find_text_input.text()
        replace_text = self.replace_text_input.text()
        if not find_text:
            QMessageBox.information(self, "Replace", "Please enter text to search.")
            return
        # Perform search first to identify rows for replacement if not already done
        # or if replace_all should work on a fresh search.
        # The find_and_replace method in TableWindow will do its own iteration,
        # but this ensures current_search_results is populated for the dialog's state.
        # However, find_and_replace itself handles the iteration and replacement.
        # So, calling perform_search here might be redundant if find_and_replace is robust.
        # For now, we rely on table_window.find_and_replace to do the heavy lifting.
        
        self.table_window.find_and_replace(find_text, replace_text, self.search_in_character.isChecked(), self.search_in_dialogue.isChecked())
        
        # After replacing, the search results might be invalid, so reset them.
        self.reset_search()
        # Optionally, re-perform search with the original find_text to highlight any remaining (or newly created) instances.
        # if self.find_text_input.text():
        #     self.perform_search()