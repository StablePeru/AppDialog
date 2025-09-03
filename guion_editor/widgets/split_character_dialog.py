# guion_editor/widgets/split_character_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox
)
import re

class SplitCharacterDialog(QDialog):
    def __init__(self, original_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Separar Personaje")
        
        self.name1_edit = QLineEdit()
        self.name2_edit = QLineEdit()
        
        self._prefill_names(original_name)
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.addRow("Nombre del Personaje 1:", self.name1_edit)
        form_layout.addRow("Nombre del Personaje 2:", self.name2_edit)
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _prefill_names(self, original_name: str):
        """Intenta adivinar los dos nombres buscando separadores comunes."""
        # Busca separadores como '/', '-', '_', o incluso múltiples espacios
        parts = re.split(r'\s*[/_-]\s*|\s{2,}', original_name, 1)
        
        if len(parts) == 2:
            self.name1_edit.setText(parts[0].strip())
            self.name2_edit.setText(parts[1].strip())
        else:
            self.name1_edit.setText(original_name)

    def get_names(self) -> tuple[str, str] | None:
        """Devuelve los dos nombres si el diálogo es aceptado."""
        if self.result() == QDialog.DialogCode.Accepted:
            name1 = self.name1_edit.text().strip()
            name2 = self.name2_edit.text().strip()
            if name1 and name2:
                return name1, name2
        return None