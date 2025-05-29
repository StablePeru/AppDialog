# guion_editor/delegates/dialog_delegate.py
from PyQt6.QtWidgets import QStyledItemDelegate, QApplication, QStyleOptionViewItem, QWidget, QStyle # QTextEdit se importa abajo
from PyQt6.QtCore import Qt, QSize, QEvent, QModelIndex
from PyQt6.QtGui import QFontMetrics, QPalette, QFont # Añadido QFont

from guion_editor.widgets.custom_text_edit import CustomTextEdit

class DialogDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, font_size=9): # parent es QObject
        super().__init__(parent)
        self.font_size = font_size

    def createEditor(self, parent_widget_for_editor: QWidget, # Cambiado de QTextEdit a QWidget
                     option: QStyleOptionViewItem, 
                     index: QModelIndex) -> CustomTextEdit:
        editor = CustomTextEdit(parent_widget_for_editor)
        
        font = editor.font()
        font.setPointSize(self.font_size)
        editor.setFont(font)
        
        editor.setAcceptRichText(False)
        return editor

    def setEditorData(self, editor_widget: CustomTextEdit, index: QModelIndex) -> None:
        text = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(editor_widget, CustomTextEdit):
            editor_widget.setPlainText(str(text) if text is not None else "")

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
        
        current_font = QFont(option.font) # Usar una copia de la fuente de la opción
        current_font.setPointSize(self.font_size)
        
        metrics = QFontMetrics(current_font)
        
        rect_width = option.rect.width() - 10 
        
        # Usar Qt.AlignmentFlag.AlignLeft para el cálculo de boundingRect con TextWordWrap
        # para que coincida mejor con cómo drawText lo haría.
        bounding_rect = metrics.boundingRect(0, 0, rect_width, 0, 
                                             Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft, 
                                             str(text))
        
        height = bounding_rect.height() + 10 
        return QSize(option.rect.width(), height)

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        opt = QStyleOptionViewItem(option) # Haz una copia para modificarla si es necesario
        self.initStyleOption(opt, index) # Inicializa la opción con datos del modelo y estado

        widget = opt.widget # El QTableView

        # 1. Dibujar el fondo (considerando selección, etc.)
        # initStyleOption ya debería haber configurado opt.backgroundBrush y opt.palette
        # style().drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, widget)
        # Es más simple si dejas que el super().paint() maneje el fondo y la selección,
        # y tú solo te encargas del texto si es necesario.
        # O, si quieres control total:
        if opt.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(opt.rect, opt.palette.highlight())
        else:
            # Considerar el color de fondo alterno si está habilitado y es una fila alterna
            # Esto es un poco más complejo de determinar aquí sin acceso directo al índice de vista y si es par/impar
            # Por ahora, un fondo base. El CSS para QTableView::item y ::item:alternate debería ayudar.
            bg_color_from_model = index.data(Qt.ItemDataRole.BackgroundRole) # e.g. para IN/OUT
            if bg_color_from_model and isinstance(bg_color_from_model, QBrush):
                 painter.fillRect(opt.rect, bg_color_from_model)
            elif bg_color_from_model and isinstance(bg_color_from_model, QColor):
                 painter.fillRect(opt.rect, QBrush(bg_color_from_model))
            else:
                # Fallback al color de fondo de la opción si no hay nada específico del modelo
                # o si el estilo CSS no se aplicó como se esperaba para item normal/alterno.
                 painter.fillRect(opt.rect, opt.backgroundBrush if opt.backgroundBrush.style() != Qt.BrushStyle.NoBrush else opt.palette.base())


        # 2. Dibujar el texto
        text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        if text is None: text = ""
        
        text_rect = widget.style().subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, widget)
        
        paint_font = QFont(opt.font) # Usa la fuente de la opción
        paint_font.setPointSize(self.font_size) # Pero ajusta el tamaño al del delegado
        painter.setFont(paint_font)

        # Configurar el color del texto
        if opt.state & QStyle.StateFlag.State_Selected:
            painter.setPen(opt.palette.highlightedText().color())
        else:
            text_color_from_model = index.data(Qt.ItemDataRole.ForegroundRole) # Color de texto del modelo
            if text_color_from_model and isinstance(text_color_from_model, QBrush):
                painter.setPen(text_color_from_model.color())
            elif text_color_from_model and isinstance(text_color_from_model, QColor):
                painter.setPen(text_color_from_model)
            else:
                painter.setPen(opt.palette.text().color()) # Color de texto por defecto

        painter.drawText(text_rect, 
                         Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, 
                         str(text))
        painter.restore()

    def setFontSize(self, font_size: int):
        self.font_size = font_size
        # Forzar actualización de la vista puede ser necesario aquí si el delegado se reutiliza
        # y el tamaño de fuente cambia mientras está activo.
        # Si el parent es la QTableView, podríamos hacer:
        if self.parent() and isinstance(self.parent(), QWidget) and self.parent().isVisible():
            # Emitir layoutChanged en el modelo para que la vista recalcule los sizeHints.
            model = self.parent().model() # Asumiendo que el padre es la vista que tiene el modelo
            if model:
                model.layoutChanged.emit()