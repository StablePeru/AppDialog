# guion_editor/widgets/custom_text_edit.py
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import pyqtSignal, Qt, QModelIndex # Añadido QModelIndex por si se necesita

class CustomTextEdit(QTextEdit):
    # Señal que emite el texto y la posición del cursor cuando el widget pierde el foco
    focusLostWithState = pyqtSignal(str, int, QModelIndex) # texto, posicion_cursor, index_de_la_celda
    # La señal original, si aún la necesitas en otro lugar
    editingFinished = pyqtSignal(str)


    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_index = QModelIndex() # Para almacenar el índice que este editor está manejando

    def setEditingIndex(self, index: QModelIndex):
        """Guarda el QModelIndex que este editor está actualmente manejando."""
        self._editing_index = index

    def focusOutEvent(self, event):
        # Emitir la señal con el texto actual y la posición del cursor ANTES de llamar a super
        current_text = self.toPlainText()
        cursor_pos = self.textCursor().position()
        self.focusLostWithState.emit(current_text, cursor_pos, self._editing_index)
        
        super().focusOutEvent(event)
        self.editingFinished.emit(self.toPlainText()) # Emitir la señal original también