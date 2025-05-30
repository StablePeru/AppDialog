# guion_editor/widgets/custom_text_edit.py
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import pyqtSignal, Qt, QModelIndex, QTimer
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QTextCursor

class CustomTextEdit(QTextEdit):
    focusLostWithState = pyqtSignal(str, int, QModelIndex)
    editingFinished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_index = QModelIndex()
        # Inicializar a 0, ya que es una posición válida (inicio del texto).
        self._last_known_cursor_pos = 0
        self.setAcceptRichText(False) # Es bueno tenerlo explícito
        self.cursorPositionChanged.connect(self._proactive_update_cursor_pos)

    def _proactive_update_cursor_pos(self):
        self._last_known_cursor_pos = self.textCursor().position()
        # print(f"CustomTextEdit _proactive_update_cursor_pos: {self._last_known_cursor_pos}") # DEBUG

    def setEditingIndex(self, index: QModelIndex):
        self._editing_index = index

    def setPlainText(self, text: str) -> None:
        # Comprobar si el texto es realmente diferente para evitar trabajo innecesario
        # y posibles efectos secundarios de cursorPositionChanged si el texto es el mismo.
        if self.toPlainText() != text:
            super().setPlainText(text)
            # Después de setPlainText, el cursor generalmente se va al inicio.
            # Actualizamos _last_known_cursor_pos para reflejar esto.
            # cursorPositionChanged debería dispararse, pero una actualización directa es segura aquí.
            self._last_known_cursor_pos = self.textCursor().position()
        # print(f"CustomTextEdit setPlainText: text='{text}', actual cursor_pos={self.textCursor().position()}, _last_known_cursor_pos={self._last_known_cursor_pos}") # DEBUG

    def showEvent(self, event):
        super().showEvent(event)
        # Cuando el editor se muestra, nos aseguramos de que _last_known_cursor_pos
        # refleje la posición actual del cursor. Esto es especialmente útil si
        # setPlainText fue llamado cuando el widget aún no era visible.
        QTimer.singleShot(0, self._ensure_cursor_pos_on_show)

    def _ensure_cursor_pos_on_show(self):
        if self.isVisible(): # Solo si sigue visible
            # No movemos el cursor aquí, solo leemos su posición actual.
            # Esta posición debería ser el resultado de la última llamada a setPlainText
            # o la última interacción del usuario si el editor se está reutilizando.
            self._last_known_cursor_pos = self.textCursor().position()
            # print(f"CustomTextEdit _ensure_cursor_pos_on_show: {self._last_known_cursor_pos}") # DEBUG


    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)
        # cursorPositionChanged debería manejar la actualización de _last_known_cursor_pos

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        # cursorPositionChanged debería manejar la actualización de _last_known_cursor_pos

    def mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)
        # cursorPositionChanged debería manejar la actualización de _last_known_cursor_pos

    def focusOutEvent(self, event):
        # Llamar a super() primero permite que Qt complete sus procesos de pérdida de foco.
        super().focusOutEvent(event)

        current_text = self.toPlainText()
        # Usamos la _last_known_cursor_pos que fue actualizada por cursorPositionChanged
        # durante la edición o por _ensure_cursor_pos_on_show/setPlainText al inicio.
        cursor_pos_to_emit = self._last_known_cursor_pos

        # Validar que la posición del cursor esté dentro de los límites del texto actual.
        # Esto es crucial si el texto fue modificado de forma que el cursor quedó "fuera".
        if not (0 <= cursor_pos_to_emit <= len(current_text)):
            # Si es inválida, la ajustamos al final del texto actual.
            # Podría ser también al inicio (0) si se prefiere, pero el final es más seguro
            # para evitar divisiones inesperadas al inicio.
            cursor_pos_to_emit = len(current_text)
            # print(f"CustomTextEdit focusOutEvent: _last_known_cursor_pos ({self._last_known_cursor_pos}) was invalid for text length {len(current_text)}, adjusted to {cursor_pos_to_emit}") # DEBUG

        # print(f"CustomTextEdit focusOutEvent: emitting text='{current_text}', cursor_pos={cursor_pos_to_emit}, index_row={self._editing_index.row()}") # DEBUG
        self.focusLostWithState.emit(current_text, cursor_pos_to_emit, self._editing_index)
        self.editingFinished.emit(self.toPlainText()) # Emitir la señal original