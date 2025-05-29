# guion_editor/delegates/guion_delegate.py
from PyQt6.QtWidgets import QStyledItemDelegate, QApplication, QStyleOptionViewItem, QWidget, QStyle
from PyQt6.QtCore import Qt, QSize, QEvent, QModelIndex
from PyQt6.QtGui import QFontMetrics, QPalette, QFont

from guion_editor.widgets.custom_text_edit import CustomTextEdit

class DialogDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, font_size=9, table_window_instance=None): # parent es QObject
        super().__init__(parent)
        self.font_size = font_size
        self.table_window_instance = table_window_instance # Guardar referencia a TableWindow

    def createEditor(self, parent_widget_for_editor: QWidget,
                     option: QStyleOptionViewItem,
                     index: QModelIndex) -> CustomTextEdit:
        editor = CustomTextEdit(parent_widget_for_editor)
        
        font = editor.font()
        font.setPointSize(self.font_size)
        editor.setFont(font)
        editor.setAcceptRichText(False)
        
        editor.setEditingIndex(index) # Informar al editor qué índice está manejando

        if self.table_window_instance:
            # Conectar la nueva señal del editor al slot de TableWindow
            editor.focusLostWithState.connect(
                self.table_window_instance.handle_dialog_editor_state_on_focus_out
            )
        return editor

    def setEditorData(self, editor_widget: CustomTextEdit, index: QModelIndex) -> None:
        text = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor_widget, CustomTextEdit):
            editor_widget.setPlainText(str(text) if text is not None else "")
            editor_widget.setEditingIndex(index) # Asegurar que el índice esté actualizado

    # ... (setModelData, updateEditorGeometry, sizeHint, paint, setFontSize sin cambios) ...
    def setModelData(self, editor_widget: CustomTextEdit,
                     model: 'QAbstractItemModel',
                     index: QModelIndex) -> None:
        if isinstance(editor_widget, CustomTextEdit):
            text = editor_widget.toPlainText()
            model.setData(index, text, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor_widget: CustomTextEdit,
                             option: QStyleOptionViewItem,
                             index: QModelIndex) -> None:
        editor_widget.setGeometry(option.rect)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        if text is None: text = ""
        
        current_font = QFont(option.font) 
        current_font.setPointSize(self.font_size)
        metrics = QFontMetrics(current_font)
        rect_width = option.rect.width() - 10
        bounding_rect = metrics.boundingRect(0, 0, rect_width, 0,
                                             Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
                                             str(text))
        height = bounding_rect.height() + 10
        return QSize(option.rect.width(), height)

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        opt = QStyleOptionViewItem(option) 
        self.initStyleOption(opt, index) 

        widget = opt.widget 
        if opt.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(opt.rect, opt.palette.highlight())
        else:
            bg_color_from_model = index.data(Qt.ItemDataRole.BackgroundRole) 
            if bg_color_from_model and isinstance(bg_color_from_model, QBrush):
                 painter.fillRect(opt.rect, bg_color_from_model)
            elif bg_color_from_model and isinstance(bg_color_from_model, QColor):
                 painter.fillRect(opt.rect, QBrush(bg_color_from_model))
            else:
                 painter.fillRect(opt.rect, opt.backgroundBrush if opt.backgroundBrush.style() != Qt.BrushStyle.NoBrush else opt.palette.base())

        text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        if text is None: text = ""
        text_rect = widget.style().subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, widget)
        paint_font = QFont(opt.font)
        paint_font.setPointSize(self.font_size) 
        painter.setFont(paint_font)

        if opt.state & QStyle.StateFlag.State_Selected:
            painter.setPen(opt.palette.highlightedText().color())
        else:
            text_color_from_model = index.data(Qt.ItemDataRole.ForegroundRole)
            if text_color_from_model and isinstance(text_color_from_model, QBrush):
                painter.setPen(text_color_from_model.color())
            elif text_color_from_model and isinstance(text_color_from_model, QColor):
                painter.setPen(text_color_from_model)
            else:
                painter.setPen(opt.palette.text().color()) 

        painter.drawText(text_rect,
                         Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                         str(text))
        painter.restore()

    def setFontSize(self, font_size: int):
        self.font_size = font_size
        if self.parent() and isinstance(self.parent(), QWidget) and self.parent().isVisible():
            model = self.parent().model() 
            if model and hasattr(model, 'layoutChanged'): # Verificar si el modelo tiene layoutChanged
                model.layoutChanged.emit()