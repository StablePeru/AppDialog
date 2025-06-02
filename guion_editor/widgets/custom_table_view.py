# guion_editor/widgets/custom_table_view.py
from PyQt6.QtWidgets import QTableView, QApplication
from PyQt6.QtCore import pyqtSignal, Qt, QModelIndex
from PyQt6.QtGui import QMouseEvent

class CustomTableView(QTableView):
    cellCtrlClicked = pyqtSignal(int)  # Emits view row index
    cellAltClicked = pyqtSignal(int)   # Emits view row index

    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event: QMouseEvent):
        modifiers = QApplication.keyboardModifiers()
        index_at_click: QModelIndex = self.indexAt(event.pos())

        if event.button() == Qt.MouseButton.LeftButton:
            if index_at_click.isValid():
                if modifiers == Qt.KeyboardModifier.ControlModifier:
                    self.cellCtrlClicked.emit(index_at_click.row())
                    # NO ACEPTAMOS EL EVENTO AQUÍ SI QUEREMOS QUE LA SELECCIÓN MÚLTIPLE NO FUNCIONE CON CTRL+CLICK
                    # Si lo aceptaras, ExtendedSelection no lo vería.
                    # Para que la selección múltiple NO use Ctrl+Click, DEBERÍAS aceptarlo aquí.
                    # event.accept() # <--- AÑADIR ESTO SI QUIERES QUE CTRL+CLICK SOLO SEA PARA TU ACCIÓN
                    super().mousePressEvent(event) # Permitir que la selección normal ocurra o no.
                    return
                elif modifiers == Qt.KeyboardModifier.AltModifier:
                    self.cellAltClicked.emit(index_at_click.row())
                    # event.accept() # <--- IDEM
                    super().mousePressEvent(event)
                    return
                # Aquí es donde ExtendedSelection haría su magia con Ctrl+Click si no lo interceptamos.
                # Si Ctrl+Click fue tu acción, y llamaste a super(), entonces ExtendedSelection también
                # podría haber actuado.

        super().mousePressEvent(event)