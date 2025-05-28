import logging # Añadir

# --- CAMBIOS PyQt6 ---
from PyQt6.QtWidgets import QTableWidget, QApplication
from PyQt6.QtCore import pyqtSignal, Qt

logger_ctw = logging.getLogger(__name__) # Logger específico

class CustomTableWidget(QTableWidget):
    cellCtrlClicked = pyqtSignal(int)
    cellAltClicked = pyqtSignal(int)

    def __init__(self, parent=None):
        logger_ctw.info("CustomTableWidget: Entrando a __init__")
        super().__init__(parent)
        logger_ctw.info("CustomTableWidget: super().__init__() completado")
        # Cualquier otra inicialización específica de CustomTableWidget iría aquí
        logger_ctw.info("CustomTableWidget: __init__ completado")

    def mousePressEvent(self, event): # event es QMouseEvent
        # logger_ctw.debug("CustomTableWidget: mousePressEvent") # Puede ser muy verboso
        # QApplication.keyboardModifiers() sigue siendo válido, pero el tipo es Qt.KeyboardModifier
        modifiers = QApplication.keyboardModifiers() # Esto es una función estática, no crea QApp
        
        # Qt.LeftButton -> Qt.MouseButton.LeftButton
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid():
                # Qt.ControlModifier -> Qt.KeyboardModifier.ControlModifier
                # Qt.AltModifier -> Qt.KeyboardModifier.AltModifier
                if modifiers == Qt.KeyboardModifier.ControlModifier:
                    logger_ctw.debug(f"CustomTableWidget: Ctrl+Click en fila {index.row()}")
                    self.cellCtrlClicked.emit(index.row())
                    event.accept() # Aceptar el evento para que no se propague más si lo manejamos
                elif modifiers == Qt.KeyboardModifier.AltModifier:
                    logger_ctw.debug(f"CustomTableWidget: Alt+Click en fila {index.row()}")
                    self.cellAltClicked.emit(index.row())
                    event.accept()
                else:
                    # Llamar al manejador de la clase base si no es un clic modificado que manejemos
                    super().mousePressEvent(event)
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)