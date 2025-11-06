# --- START OF FILE custom_delegates.py ---

# guion_editor/delegates/custom_delegates.py

from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit, QCompleter, QWidget, QStyle, QStyleOptionViewItem, QComboBox
from PyQt6.QtCore import Qt, QObject, QModelIndex, QAbstractItemModel
from PyQt6.QtGui import QPalette, QPainter, QBrush, QColor, QFont

from guion_editor.commands.undo_commands import EditCommand
from typing import Optional, Any, List, Callable

class TimeCodeDelegate(QStyledItemDelegate):
    # -> FIX: El método __init__ ahora acepta 'table_window_instance' correctamente.
    def __init__(self, parent: Optional[QObject] = None, table_window_instance=None):
        super().__init__(parent)
        self.table_window = table_window_instance

    def createEditor(self, parent_widget_for_editor: QWidget,
                     option: 'QStyleOptionViewItem',
                     index: QModelIndex) -> QWidget:
        from guion_editor.widgets.time_code_edit import TimeCodeEdit
        editor = TimeCodeEdit(parent=parent_widget_for_editor)
        return editor

    def setEditorData(self, editor_widget: QWidget, index: QModelIndex) -> None:
        from guion_editor.widgets.time_code_edit import TimeCodeEdit
        time_code_value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor_widget, TimeCodeEdit):
            editor_widget.set_time_code(str(time_code_value) if time_code_value is not None else "00:00:00:00")

    def setModelData(self, editor_widget: QWidget,
                     model: 'QAbstractItemModel',
                     index: QModelIndex) -> None:
        from guion_editor.widgets.time_code_edit import TimeCodeEdit
        if not isinstance(editor_widget, TimeCodeEdit):
            super().setModelData(editor_widget, model, index)
            return
        if not self.table_window or not hasattr(self.table_window, 'undo_stack'):
            time_code = editor_widget.get_time_code()
            model.setData(index, time_code, Qt.ItemDataRole.EditRole)
            return
        old_value = model.data(index, Qt.ItemDataRole.EditRole) or "00:00:00:00"
        new_value = editor_widget.get_time_code()
        if str(old_value) != new_value:
            command = EditCommand(
                table_window=self.table_window,
                df_row_index=index.row(),
                view_col_index=index.column(),
                old_value=old_value,
                new_value=new_value
            )
            self.table_window.undo_stack.push(command)

    def updateEditorGeometry(self, editor_widget: QWidget,
                             option: 'QStyleOptionViewItem',
                             index: QModelIndex) -> None:
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
            popup = completer.popup()
            if popup:
                popup_stylesheet = """
                    QListView { background-color: #2D2D2D; border: 1px solid #4A4A4A; border-radius: 4px; padding: 2px; font-family: inherit; font-size: inherit; }
                    QListView::item { color: white; background-color: transparent; padding: 5px 8px; margin: 1px; border-radius: 3px; }
                    QListView::item:selected { color: white; background-color: #0078D7; }
                    QListView::item:hover { color: white; background-color: #3A3A3A; }
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
            value = editor_widget.text()
            model.setData(index, value, Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor_widget, model, index)

    def updateEditorGeometry(self, editor_widget: QWidget,
                             option: 'QStyleOptionViewItem',
                             index: QModelIndex) -> None:
        editor_widget.setGeometry(option.rect)

class RepartoDelegate(QStyledItemDelegate):
    def __init__(self, get_names_callback: Optional[Callable[[], List[str]]] = None,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.get_names_callback = get_names_callback

    def createEditor(self, parent_widget_for_editor: QWidget,
                     option: 'QStyleOptionViewItem',
                     index: QModelIndex) -> QWidget:
        editor = QComboBox(parent_widget_for_editor)
        editor.setEditable(True)
        if self.get_names_callback:
            actor_names = self.get_names_callback()
            editor.addItem("") 
            editor.addItems(actor_names)
        return editor

    def setEditorData(self, editor_widget: QWidget, index: QModelIndex) -> None:
        text_value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor_widget, QComboBox):
            editor_widget.setCurrentText(str(text_value) if text_value is not None else "")

    def setModelData(self, editor_widget: QWidget,
                     model: 'QAbstractItemModel',
                     index: QModelIndex) -> None:
        if isinstance(editor_widget, QComboBox):
            value = editor_widget.currentText()
            model.setData(index, value, Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor_widget, model, index)

    def updateEditorGeometry(self, editor_widget: QWidget,
                             option: 'QStyleOptionViewItem',
                             index: QModelIndex) -> None:
        editor_widget.setGeometry(option.rect)