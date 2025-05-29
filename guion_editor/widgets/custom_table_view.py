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
        # Check for keyboard modifiers BEFORE calling super,
        # as super().mousePressEvent might change selection, clear focus, etc.
        # which could affect how other parts of the application react.
        
        modifiers = QApplication.keyboardModifiers()
        index_at_click: QModelIndex = self.indexAt(event.pos())

        if event.button() == Qt.MouseButton.LeftButton:
            if index_at_click.isValid(): # Click was on a cell
                if modifiers == Qt.KeyboardModifier.ControlModifier:
                    self.cellCtrlClicked.emit(index_at_click.row())
                    # event.accept() # Accept to prevent default processing like selection change if needed
                                   # For now, let selection proceed.
                    super().mousePressEvent(event) # Still allow default processing for selection
                    return
                elif modifiers == Qt.KeyboardModifier.AltModifier:
                    self.cellAltClicked.emit(index_at_click.row())
                    # event.accept()
                    super().mousePressEvent(event)
                    return
        
        # If not a handled special click, or click not on a cell, let base class handle it.
        super().mousePressEvent(event)