from PyQt6.QtWidgets import QTextEdit  # CAMBIO
from PyQt6.QtCore import pyqtSignal, Qt # CAMBIO


class CustomTextEdit(QTextEdit):
    # Señal personalizada que emite el texto final cuando el widget pierde el foco
    editingFinished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    # Maneja el evento cuando el widget pierde el foco
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # Emite la señal con el texto actual cuando se pierde el foco
        self.editingFinished.emit(self.toPlainText())