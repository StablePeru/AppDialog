# En guion_editor/delegates/custom_delegates.py
import logging
from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit, QMessageBox, QCompleter, QWidget # Asegurar imports de PyQt6
from PyQt6.QtCore import Qt, QObject                                                        # Asegurar imports de PyQt6
# from guion_editor.widgets.time_code_edit import TimeCodeEdit                   # Asumir TimeCodeEdit migrado

from typing import Optional, Any


logger_cd = logging.getLogger(__name__)

class TimeCodeDelegate(QStyledItemDelegate):
    def __init__(self, parent: Optional[QObject] = None): # El tipo del parent es QObject
        logger_cd.info(f"TimeCodeDelegate: Entrando a __init__ con parent tipo {type(parent)}")
        super().__init__(parent) # Pasar el parent al constructor de la clase base
        logger_cd.info("TimeCodeDelegate: super().__init__() completado")
        # No se necesita hacer más nada con el 'parent' aquí generalmente

    def createEditor(self, parent_widget_for_editor: QWidget, option: 'QStyleOptionViewItem', index: 'QModelIndex') -> QWidget:
        # 'parent_widget_for_editor' es el QTableWidget (o la viewport) donde se mostrará el editor.
        logger_cd.debug("TimeCodeDelegate: createEditor")
        # Asumiendo que TimeCodeEdit se migrará y su constructor acepta un QWidget padre
        from guion_editor.widgets.time_code_edit import TimeCodeEdit # Import local para evitar ciclos si TimeCodeEdit importa algo que depende de delegates
        editor = TimeCodeEdit(parent_widget_for_editor)
        return editor

    def setEditorData(self, editor: QWidget, index: 'QModelIndex') -> None:
        logger_cd.debug("TimeCodeDelegate: setEditorData")
        # Qt.ItemDataRole.EditRole
        time_code = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor, TimeCodeEdit): # type guard
            editor.set_time_code(str(time_code) if time_code is not None else "00:00:00:00")

    def setModelData(self, editor: QWidget, model: 'QAbstractItemModel', index: 'QModelIndex') -> None:
        logger_cd.debug("TimeCodeDelegate: setModelData")
        if isinstance(editor, TimeCodeEdit): # type guard
            time_code = editor.get_time_code()
            # Qt.ItemDataRole.EditRole
            model.setData(index, time_code, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor: QWidget, option: 'QStyleOptionViewItem', index: 'QModelIndex') -> None:
        logger_cd.debug("TimeCodeDelegate: updateEditorGeometry")
        editor.setGeometry(option.rect)

# --- CharacterDelegate necesitará una revisión similar ---
class CharacterDelegate(QStyledItemDelegate):
    def __init__(self, get_names_callback=None, parent: Optional[QObject] = None): # 'parent' es el QObject padre
        logger_cd.info(f"CharacterDelegate: Entrando a __init__ con parent tipo {type(parent)}")
        super().__init__(parent)
        logger_cd.info("CharacterDelegate: super().__init__() completado")
        self.get_names_callback = get_names_callback

    def createEditor(self, parent_widget_for_editor: QWidget, option: 'QStyleOptionViewItem', index: 'QModelIndex') -> QWidget:
        logger_cd.debug("CharacterDelegate: createEditor")
        editor = QLineEdit(parent_widget_for_editor)
        if self.get_names_callback:
            # Qt.CaseSensitivity.CaseInsensitive
            completer = QCompleter(self.get_names_callback())
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            editor.setCompleter(completer)
        return editor

    def setEditorData(self, editor: QWidget, index: 'QModelIndex') -> None:
        logger_cd.debug("CharacterDelegate: setEditorData")
        # Qt.ItemDataRole.EditRole
        text = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor, QLineEdit): # type guard
            editor.setText(str(text) if text is not None else "")

    def setModelData(self, editor: QWidget, model: 'QAbstractItemModel', index: 'QModelIndex') -> None:
        logger_cd.debug("CharacterDelegate: setModelData")
        if isinstance(editor, QLineEdit): # type guard
            text = editor.text().strip()
            if not text: # No permitir nombres vacíos
                # QMessageBox.warning(editor, "Invalid Input", "Character name cannot be empty.")
                # No se puede mostrar un QMessageBox directamente desde setModelData de forma modal fácil.
                # Es mejor manejar la validación antes o después, o no cambiar el dato si es inválido.
                # O emitir una señal para que el widget principal muestre el error.
                # Por ahora, si es inválido, no actualizamos el modelo (o lo actualizamos al valor antiguo).
                logger_cd.warning("CharacterDelegate: Nombre de personaje vacío, no se actualiza el modelo.")
                return # Opcionalmente, restaurar editor.setText(index.model().data(index, Qt.ItemDataRole.EditRole))
            
            # Qt.ItemDataRole.EditRole
            model.setData(index, text, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor: QWidget, option: 'QStyleOptionViewItem', index: 'QModelIndex') -> None:
        logger_cd.debug("CharacterDelegate: updateEditorGeometry")
        editor.setGeometry(option.rect)