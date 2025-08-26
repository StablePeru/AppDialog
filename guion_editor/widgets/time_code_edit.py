# guion_editor/widgets/time_code_edit.py

from PyQt6.QtWidgets import QLineEdit, QMessageBox
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QFont, QKeyEvent


class TimeCodeEdit(QLineEdit):
    def __init__(self, parent=None, initial_time_code="00:00:00:00"):
        super().__init__(parent)
        self.setFixedWidth(120)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Arial", 12)) # La fuente puede ser ajustada por VideoPlayerWidget
        self.setStyleSheet("font-size: 16px;") # El tamaño de fuente también
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

        elif event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if self.edit_mode and self.typed_digits:
                self.typed_digits.pop()
                final_digits = self.original_digits[:8 - len(self.typed_digits)] + self.typed_digits
                self.digits = final_digits
                self.update_display()
                self.textChanged.emit(self.text())
            else:
                super().keyPressEvent(event)
        
        elif event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            # Al presionar Enter, queremos que se finalice la edición.
            # Forzar la pérdida de foco es una forma robusta de asegurar
            # que editingFinished se emita.
            self.clearFocus() 
        
        elif event.key() in (
            Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End
        ):
            super().keyPressEvent(event)
        else:
            # Permitir otros eventos (como Ctrl+C, Ctrl+V si es necesario, etc.)
            # Si solo quieres dígitos y las teclas manejadas, usa event.ignore()
            super().keyPressEvent(event)


    def insertFromMimeData(self, source: QMimeData):
        text = source.text()
        temp_typed_digits_for_paste = []
        for char in text:
            if char.isdigit():
                if len(temp_typed_digits_for_paste) < 8:
                    temp_typed_digits_for_paste.append(int(char))
        
        if temp_typed_digits_for_paste: # Solo proceder si se pegaron dígitos
            if not self.edit_mode:
                self.edit_mode = True
                self.typed_digits = [] # Resetear typed_digits al pegar
                self.original_digits = self.digits.copy()

            # Reemplazar typed_digits con lo pegado, hasta 8 dígitos
            self.typed_digits = temp_typed_digits_for_paste 
            
            # Actualizar self.digits basado en original_digits y los nuevos typed_digits
            # Si se pegaron menos de 8 dígitos, se toman los iniciales de original_digits
            # y se completan con los pegados.
            # Si se pegaron 8, se reemplazan todos.
            num_typed = len(self.typed_digits)
            if num_typed < 8:
                final_digits = self.original_digits[:8 - num_typed] + self.typed_digits
            else: # num_typed == 8
                final_digits = self.typed_digits
            
            self.digits = final_digits
            self.update_display()
            self.textChanged.emit(self.text())


    def update_display(self):
        hours = self.digits[0] * 10 + self.digits[1]
        minutes = self.digits[2] * 10 + self.digits[3]
        seconds = self.digits[4] * 10 + self.digits[5]
        frames = self.digits[6] * 10 + self.digits[7]
        formatted = "{:02}:{:02}:{:02}:{:02}".format(hours, minutes, seconds, frames)
        
        # Evitar señal si el texto no cambia para prevenir bucles o efectos no deseados
        current_text = self.text()
        if current_text != formatted:
            self.blockSignals(True)
            self.setText(formatted)
            self.blockSignals(False)
            # La señal textChanged debe emitirse explícitamente si es necesario
            # después de este cambio programático, si alguna lógica depende de ello.
            # Pero usualmente, los cambios programáticos no deben disparar la misma lógica
            # que los cambios del usuario.


    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # editingFinished se emite automáticamente por QLineEdit al perder foco
        self.edit_mode = False
        self.typed_digits = []
        self.original_digits = self.digits.copy() # Sincronizar original con el estado actual


    def set_time_code(self, time_code: str):
        try:
            parts = time_code.split(':')
            if len(parts) != 4 or not all(p.isdigit() and len(p) == 2 for p in parts):
                #raise ValueError("Formato de Timecode inválido: debe ser HH:MM:SS:FF con dígitos.")
                pass
            
            self.digits = [
                int(parts[0][0]), int(parts[0][1]),
                int(parts[1][0]), int(parts[1][1]),
                int(parts[2][0]), int(parts[2][1]),
                int(parts[3][0]), int(parts[3][1]),
            ]
            self.update_display() # Actualiza el texto
            self.edit_mode = False # Resetear estado de edición
            self.typed_digits = []
            self.original_digits = self.digits.copy() # Sincronizar original_digits
        except ValueError as e: # Capturar el error específico para un mejor mensaje
            QMessageBox.warning(self, "Error de Formato", str(e))
        except Exception as e_gen: # Capturar otros errores inesperados
            #QMessageBox.warning(self, "Error", f"Error al establecer timecode: {e_gen}")
            pass

    def get_time_code(self) -> str:
        return self.text()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # Al hacer clic, no necesariamente entramos en modo edición aún.
        # Podríamos seleccionar todo el texto para facilitar el reemplazo si el usuario empieza a escribir.
        # self.selectAll() # Opcional, depende de la UX deseada.
        # El modo de edición (edit_mode) se activará cuando el usuario empiece a escribir dígitos.
        self.setCursorPosition(len(self.text())) # Mover cursor al final es un comportamiento común