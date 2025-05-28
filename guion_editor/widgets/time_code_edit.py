
from PyQt6.QtWidgets import QLineEdit, QMessageBox # CAMBIO
from PyQt6.QtCore import Qt, QMimeData             # CAMBIO
from PyQt6.QtGui import QFont, QKeyEvent           # CAMBIO


class TimeCodeEdit(QLineEdit):
    def __init__(self, parent=None, initial_time_code="00:00:00:00"):
        super().__init__(parent)
        self.setFixedWidth(120)
        # Qt.AlignCenter -> Qt.AlignmentFlag.AlignCenter en PyQt6 para setAlignment
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Arial", 12))
        self.setStyleSheet("font-size: 16px;")
        self.setMaxLength(11)
        self.setReadOnly(False)
        self.setText(initial_time_code)

        self.digits = [int(c) for c in initial_time_code if c.isdigit()]
        if len(self.digits) != 8:
            self.digits = [0] * 8
            self.update_display()

        self.edit_mode = False
        self.typed_digits = []
        self.original_digits = self.digits.copy()

    def keyPressEvent(self, event: QKeyEvent):
        # Qt.Key_Backspace -> Qt.Key.Key_Backspace (Key es un enum dentro de Qt)
        if event.text().isdigit():
            new_digit = int(event.text())
            if not self.edit_mode:
                self.edit_mode = True
                self.typed_digits = []
                self.original_digits = self.digits.copy()

            if len(self.typed_digits) < 8:
                self.typed_digits.append(new_digit)
            else:
                self.typed_digits.pop(0)
                self.typed_digits.append(new_digit)

            final_digits = self.original_digits[:8 - len(self.typed_digits)] + self.typed_digits
            self.digits = final_digits
            self.update_display()
            self.textChanged.emit(self.text())

        elif event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete): # CAMBIO
            if self.edit_mode and self.typed_digits:
                self.typed_digits.pop()
                final_digits = self.original_digits[:8 - len(self.typed_digits)] + self.typed_digits
                self.digits = final_digits
                self.update_display()
                self.textChanged.emit(self.text())
            else:
                super().keyPressEvent(event)

        elif event.key() in (
            Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End # CAMBIO
        ):
            super().keyPressEvent(event)
        else:
            event.ignore()

    def insertFromMimeData(self, source: QMimeData):
        text = source.text()
        for char in text:
            if char.isdigit():
                if not self.edit_mode:
                    self.edit_mode = True
                    self.typed_digits = []
                    self.original_digits = self.digits.copy()

                if len(self.typed_digits) < 8:
                    self.typed_digits.append(int(char))
                else:
                    self.typed_digits.pop(0)
                    self.typed_digits.append(int(char))

        final_digits = self.original_digits[:8 - len(self.typed_digits)] + self.typed_digits
        self.digits = final_digits
        self.update_display()
        self.textChanged.emit(self.text())

    def update_display(self):
        hours = self.digits[0] * 10 + self.digits[1]
        minutes = self.digits[2] * 10 + self.digits[3]
        seconds = self.digits[4] * 10 + self.digits[5]
        frames = self.digits[6] * 10 + self.digits[7]
        formatted = "{:02}:{:02}:{:02}:{:02}".format(hours, minutes, seconds, frames)
        self.blockSignals(True)
        self.setText(formatted)
        self.blockSignals(False)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.edit_mode = False
        self.typed_digits = []
        self.original_digits = self.digits.copy()

    def set_time_code(self, time_code: str):
        try:
            parts = time_code.split(':')
            if len(parts) != 4:
                raise ValueError
            self.digits = [
                int(parts[0][0]), int(parts[0][1]),
                int(parts[1][0]), int(parts[1][1]),
                int(parts[2][0]), int(parts[2][1]),
                int(parts[3][0]), int(parts[3][1]),
            ]
            self.update_display()
            self.edit_mode = False
            self.typed_digits = []
            self.original_digits = self.digits.copy()
        except:
            QMessageBox.warning(self, "Error", "Formato de Time Code inválido.")

    def get_time_code(self) -> str:
        return self.text()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.setCursorPosition(len(self.text()))
