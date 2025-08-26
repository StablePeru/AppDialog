# guion_editor/delegates/guion_delegate.py
from PyQt6.QtWidgets import QStyledItemDelegate, QApplication, QStyleOptionViewItem, QWidget, QStyle, QTextEdit
from PyQt6.QtCore import Qt, QSize, QEvent, QModelIndex, QAbstractItemModel
from PyQt6.QtGui import (
    QFontMetrics, QPalette, QFont, QBrush, 
    QColor, QTextDocument, QPainter, QTextOption 
)

from guion_editor.widgets.custom_text_edit import CustomTextEdit
# -> NUEVO: Importar el EditCommand para usarlo en el delegado
from guion_editor.commands.undo_commands import EditCommand


class DialogDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, font_size=9, table_window_instance=None):
        super().__init__(parent)
        self._font_size = font_size
        self._font = QFont()
        self._font.setPointSize(self._font_size)
        self.table_window = table_window_instance

    def setFontSize(self, size: int):
        self._font_size = size
        self._font.setPointSize(self._font_size)
        if self.table_window and hasattr(self.table_window, 'table_view'):
            self.table_window.table_view.viewport().update()
            self.table_window.request_resize_rows_to_contents_deferred()

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        editor = CustomTextEdit(parent)
        editor.setFont(self._font)
        editor.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        
        if self.table_window:
            editor.focusLostWithState.connect(self.table_window.handle_dialog_editor_state_on_focus_out)
        return editor

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        if isinstance(editor, CustomTextEdit):
            value = index.model().data(index, Qt.ItemDataRole.EditRole) or ""
            editor.setPlainText(str(value))
            editor.setEditingIndex(index)

    # -> MODIFICADO: setModelData ahora usa QUndoStack
    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex) -> None:
        if not isinstance(editor, CustomTextEdit):
            super().setModelData(editor, model, index)
            return

        # Comprobar si tenemos acceso a la pila de deshacer
        if not self.table_window or not hasattr(self.table_window, 'undo_stack'):
            # Fallback al comportamiento antiguo si no hay pila (por seguridad)
            current_value = editor.toPlainText()
            model.setData(index, current_value, Qt.ItemDataRole.EditRole)
            return

        old_value = model.data(index, Qt.ItemDataRole.EditRole) or ""
        new_value = editor.toPlainText()

        # Solo crear un comando si el valor realmente ha cambiado
        if str(old_value) != new_value:
            command = EditCommand(
                table_window=self.table_window,
                df_row_index=index.row(),
                view_col_index=index.column(),
                old_value=old_value,
                new_value=new_value
            )
            # Añadir el comando a la pila. Esto ejecutará redo() automáticamente
            self.table_window.undo_stack.push(command)


    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        editor.setGeometry(option.rect)

    # ... (el resto de los métodos sizeHint y paint no cambian)
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        doc = QTextDocument()
        doc.setPlainText(text)
        doc.setDefaultFont(self._font) 

        available_width_for_qtextedit_content = option.rect.width() - (3 * 2)

        doc.setTextWidth(available_width_for_qtextedit_content)
        ideal_height_of_text = doc.size().height()
        
        calculated_height = int(ideal_height_of_text + (3 * 2) + 4)

        min_line_height = QFontMetrics(self._font).height() + (3 * 2) + 4
        
        return QSize(option.rect.width(), max(calculated_height, min_line_height))


    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()

        style_option = QStyleOptionViewItem(option) 
        self.initStyleOption(style_option, index)

        widget = style_option.widget

        if style_option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(style_option.rect, style_option.palette.highlight())
        else:
            background_color_from_model = index.data(Qt.ItemDataRole.BackgroundRole)
            if background_color_from_model:
                if isinstance(background_color_from_model, QBrush):
                    painter.fillRect(style_option.rect, background_color_from_model)
                elif isinstance(background_color_from_model, QColor):
                    painter.fillRect(style_option.rect, QBrush(background_color_from_model))
                else:
                    painter.fillRect(style_option.rect, style_option.backgroundBrush if style_option.backgroundBrush.style() != Qt.BrushStyle.NoBrush else style_option.palette.base())
            else:
                painter.fillRect(style_option.rect, style_option.backgroundBrush if style_option.backgroundBrush.style() != Qt.BrushStyle.NoBrush else style_option.palette.base())

        if widget and hasattr(widget, 'isPersistentEditorOpen') and widget.isPersistentEditorOpen(index):
            painter.restore()
            return

        text_to_display = str(index.model().data(index, Qt.ItemDataRole.DisplayRole) or "")
        text_rect = widget.style().subElementRect(QStyle.SubElement.SE_ItemViewItemText, style_option, widget)
        current_paint_font = QFont(style_option.font)
        current_paint_font.setPointSize(self._font_size)
        painter.setFont(current_paint_font)

        if style_option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(style_option.palette.highlightedText().color())
        else:
            text_color_from_model = index.data(Qt.ItemDataRole.ForegroundRole)
            if text_color_from_model:
                if isinstance(text_color_from_model, QBrush):
                    painter.setPen(text_color_from_model.color())
                elif isinstance(text_color_from_model, QColor):
                    painter.setPen(text_color_from_model)
                else:
                    painter.setPen(style_option.palette.text().color())
            else:
                painter.setPen(style_option.palette.text().color())

        text_flags = Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        painter.drawText(text_rect, int(text_flags), text_to_display)

        painter.restore()