# guion_editor/delegates/custom_delegates.py

from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit, QCompleter, QWidget, QStyle, QStyleOptionViewItem
from PyQt6.QtCore import Qt, QObject, QModelIndex
from PyQt6.QtGui import QPalette, QPainter, QBrush, QColor, QFont

# TimeCodeEdit se importa localmente en createEditor para TimeCodeDelegate
# from guion_editor.widgets.time_code_edit import TimeCodeEdit

from typing import Optional, Any, List, Callable

class TimeCodeDelegate(QStyledItemDelegate):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

    def createEditor(self, parent_widget_for_editor: QWidget,
                     option: 'QStyleOptionViewItem',
                     index: QModelIndex) -> QWidget:
        """Crea el editor TimeCodeEdit."""
        from guion_editor.widgets.time_code_edit import TimeCodeEdit
        editor = TimeCodeEdit(parent=parent_widget_for_editor)
        return editor

    def setEditorData(self, editor_widget: QWidget, index: QModelIndex) -> None:
        """Establece los datos del modelo en el editor TimeCodeEdit."""
        from guion_editor.widgets.time_code_edit import TimeCodeEdit

        time_code_value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor_widget, TimeCodeEdit):
            editor_widget.set_time_code(str(time_code_value) if time_code_value is not None else "00:00:00:00")

    def setModelData(self, editor_widget: QWidget,
                     model: 'QAbstractItemModel',
                     index: QModelIndex) -> None:
        """Obtiene los datos del editor TimeCodeEdit y los establece en el modelo."""
        from guion_editor.widgets.time_code_edit import TimeCodeEdit

        if isinstance(editor_widget, TimeCodeEdit):
            time_code = editor_widget.get_time_code()
            model.setData(index, time_code, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor_widget: QWidget,
                             option: 'QStyleOptionViewItem',
                             index: QModelIndex) -> None:
        """Ajusta la geometría del editor para que ocupe la celda."""
        editor_widget.setGeometry(option.rect)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()

        current_option = QStyleOptionViewItem(option)
        self.initStyleOption(current_option, index)

        widget = current_option.widget

        bg_to_draw = None
        is_selected = current_option.state & QStyle.StateFlag.State_Selected

        if is_selected:
            bg_to_draw = current_option.palette.highlight()
        else:
            model_bg_data = index.data(Qt.ItemDataRole.BackgroundRole)
            model_provided_specific_bg = False

            if isinstance(model_bg_data, QBrush):
                if model_bg_data.color() != Qt.GlobalColor.transparent and model_bg_data.style() != Qt.BrushStyle.NoBrush:
                    bg_to_draw = model_bg_data
                    model_provided_specific_bg = True
            elif isinstance(model_bg_data, QColor):
                 if model_bg_data != Qt.GlobalColor.transparent:
                    bg_to_draw = QBrush(model_bg_data)
                    model_provided_specific_bg = True

            if not model_provided_specific_bg:
                bg_to_draw = current_option.backgroundBrush

        if bg_to_draw:
            painter.fillRect(current_option.rect, bg_to_draw)

        text_rect = widget.style().subElementRect(QStyle.SubElement.SE_ItemViewItemText, current_option, widget)

        final_text_color = None
        if is_selected:
            final_text_color = current_option.palette.highlightedText().color()
        else:
            model_fg_data = index.data(Qt.ItemDataRole.ForegroundRole)
            if isinstance(model_fg_data, QBrush):
                final_text_color = model_fg_data.color()
            elif isinstance(model_fg_data, QColor):
                final_text_color = model_fg_data
            else:
                final_text_color = current_option.palette.text().color()

        painter.setPen(final_text_color)
        painter.drawText(text_rect, current_option.displayAlignment, current_option.text)

        painter.restore()


class CharacterDelegate(QStyledItemDelegate):
    def __init__(self, get_names_callback: Optional[Callable[[], List[str]]] = None,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.get_names_callback = get_names_callback

    def createEditor(self, parent_widget_for_editor: QWidget,
                     option: 'QStyleOptionViewItem',
                     index: QModelIndex) -> QWidget:
        editor = QLineEdit(parent_widget_for_editor)
        if self.get_names_callback:
            character_names = self.get_names_callback()
            completer = QCompleter(character_names, editor)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            editor.setCompleter(completer)

            popup = completer.popup() # El popup es un QListView
            if popup:
                # Aplicar un estilo específico al popup del QCompleter para asegurar colores correctos
                popup_stylesheet = """
                    QListView {
                        background-color: #2D2D2D;
                        border: 1px solid #4A4A4A;
                        border-radius: 4px;
                        padding: 2px;
                        font-family: inherit; /* Heredar fuente de la aplicación/editor */
                        font-size: inherit;   /* Heredar tamaño de fuente */
                    }
                    QListView::item {
                        color: white;
                        background-color: transparent;
                        padding: 5px 8px;
                        margin: 1px;
                        border-radius: 3px;
                    }
                    QListView::item:selected {
                        color: white;
                        background-color: #0078D7; /* Color de selección estándar */
                    }
                    QListView::item:hover {
                        color: white;
                        background-color: #3A3A3A; /* Fondo ligeramente más claro en hover */
                    }
                """
                popup.setStyleSheet(popup_stylesheet)
        return editor

    def setEditorData(self, editor_widget: QWidget, index: QModelIndex) -> None:
        text_value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor_widget, QLineEdit):
            editor_widget.setText(str(text_value) if text_value is not None else "")

    def setModelData(self, editor_widget: QWidget,
                     model: 'QAbstractItemModel',
                     index: QModelIndex) -> None:
        if isinstance(editor_widget, QLineEdit):
            text = editor_widget.text().strip()
            model.setData(index, text, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor_widget: QWidget,
                             option: 'QStyleOptionViewItem',
                             index: QModelIndex) -> None:
        editor_widget.setGeometry(option.rect)