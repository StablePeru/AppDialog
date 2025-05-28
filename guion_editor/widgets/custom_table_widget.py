from PyQt6.QtWidgets import QTableWidget, QApplication
from PyQt6.QtCore import pyqtSignal, Qt

class CustomTableWidget(QTableWidget):
    cellCtrlClicked = pyqtSignal(int)
    cellAltClicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event): # event es QMouseEvent
        modifiers = QApplication.keyboardModifiers() # Esto es una función estática, no crea QApp
        
        # Qt.LeftButton -> Qt.MouseButton.LeftButton
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid():
                # Qt.ControlModifier -> Qt.KeyboardModifier.ControlModifier
                # Qt.AltModifier -> Qt.KeyboardModifier.AltModifier
                if modifiers == Qt.KeyboardModifier.ControlModifier:
                    self.cellCtrlClicked.emit(index.row())
                    event.accept() # Aceptar el evento para que no se propague más si lo manejamos
                elif modifiers == Qt.KeyboardModifier.AltModifier:
                    self.cellAltClicked.emit(index.row())
                    event.accept()
                else:
                    # Llamar al manejador de la clase base si no es un clic modificado que manejemos
                    super().mousePressEvent(event)
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)