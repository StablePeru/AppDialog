# guion_editor/delegates/custom_delegates.py

from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit, QCompleter, QWidget
from PyQt6.QtCore import Qt, QObject, QModelIndex, pyqtSignal # Agregado QModelIndex, pyqtSignal
from PyQt6.QtGui import QPalette # Agregado QPalette

# TimeCodeEdit se importa localmente en createEditor para TimeCodeDelegate
# from guion_editor.widgets.time_code_edit import TimeCodeEdit

from typing import Optional, Any, List, Callable # Agregado List, Callable

class TimeCodeDelegate(QStyledItemDelegate):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

    def createEditor(self, parent_widget_for_editor: QWidget, 
                     option: 'QStyleOptionViewItem', 
                     index: QModelIndex) -> QWidget:
        """Crea el editor TimeCodeEdit."""
        # Importación local para evitar ciclos si TimeCodeEdit importara delegados.
        from guion_editor.widgets.time_code_edit import TimeCodeEdit
        editor = TimeCodeEdit(parent=parent_widget_for_editor) # Pasar el QWidget padre
        return editor

    def setEditorData(self, editor_widget: QWidget, index: QModelIndex) -> None:
        """Establece los datos del modelo en el editor TimeCodeEdit."""
        # Importación local para el type check con isinstance
        from guion_editor.widgets.time_code_edit import TimeCodeEdit
        
        time_code_value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor_widget, TimeCodeEdit):
            editor_widget.set_time_code(str(time_code_value) if time_code_value is not None else "00:00:00:00")
        else:
            # Fallback o advertencia si el editor no es del tipo esperado
            # print(f"Advertencia: TimeCodeDelegate encontró un editor inesperado: {type(editor_widget)}")
            pass


    def setModelData(self, editor_widget: QWidget, 
                     model: 'QAbstractItemModel', 
                     index: QModelIndex) -> None:
        """Obtiene los datos del editor TimeCodeEdit y los establece en el modelo."""
        # Importación local para el type check con isinstance
        from guion_editor.widgets.time_code_edit import TimeCodeEdit

        if isinstance(editor_widget, TimeCodeEdit):
            time_code = editor_widget.get_time_code()
            model.setData(index, time_code, Qt.ItemDataRole.EditRole)
        else:
            # Fallback o advertencia
            # print(f"Advertencia: TimeCodeDelegate.setModelData con editor inesperado: {type(editor_widget)}")
            pass


    def updateEditorGeometry(self, editor_widget: QWidget, 
                             option: 'QStyleOptionViewItem', 
                             index: QModelIndex) -> None:
        """Ajusta la geometría del editor para que ocupe la celda."""
        editor_widget.setGeometry(option.rect)


class CharacterDelegate(QStyledItemDelegate):
    def __init__(self, get_names_callback: Optional[Callable[[], List[str]]] = None, 
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.get_names_callback = get_names_callback

    def createEditor(self, parent_widget_for_editor: QWidget, 
                     option: 'QStyleOptionViewItem', 
                     index: QModelIndex) -> QWidget:
        """Crea el editor QLineEdit para el nombre del personaje."""
        editor = QLineEdit(parent_widget_for_editor)
        if self.get_names_callback:
            character_names = self.get_names_callback()
            completer = QCompleter(character_names, editor) # Pasar editor como parent del completer
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            # completer.setFilterMode(Qt.MatchFlag.MatchContains) # Opcional: para que coincida en cualquier parte
            editor.setCompleter(completer)
        return editor

    def setEditorData(self, editor_widget: QWidget, index: QModelIndex) -> None:
        """Establece los datos del modelo en el editor QLineEdit."""
        text_value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor_widget, QLineEdit):
            editor_widget.setText(str(text_value) if text_value is not None else "")

    def setModelData(self, editor_widget: QWidget, 
                     model: 'QAbstractItemModel', 
                     index: QModelIndex) -> None:
        """Obtiene los datos del editor QLineEdit y los establece en el modelo."""
        if isinstance(editor_widget, QLineEdit):
            text = editor_widget.text().strip()
            # La validación de si el nombre está vacío o duplicado
            # debería realizarse en el modelo (PandasTableModel.setData)
            # o en TableWindow después de que dataChanged sea emitida.
            # No se deben mostrar QMessageBox desde aquí.
            model.setData(index, text, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor_widget: QWidget, 
                             option: 'QStyleOptionViewItem', 
                             index: QModelIndex) -> None:
        """Ajusta la geometría del editor para que ocupe la celda."""
        editor_widget.setGeometry(option.rect)