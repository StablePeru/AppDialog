# guion_editor/delegates/guion_delegate.py
from PyQt6.QtWidgets import QStyledItemDelegate, QApplication, QStyleOptionViewItem, QWidget, QStyle, QTextEdit
from PyQt6.QtCore import Qt, QSize, QEvent, QModelIndex, QAbstractItemModel
from PyQt6.QtGui import (
    QFontMetrics, QPalette, QFont, QBrush, 
    QColor, QTextDocument, QPainter, QTextOption 
)

from guion_editor.widgets.custom_text_edit import CustomTextEdit

class DialogDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, font_size=9, table_window_instance=None):
        super().__init__(parent)
        self._font_size = font_size # Atributo con guion bajo
        self._font = QFont()
        self._font.setPointSize(self._font_size)
        self.table_window = table_window_instance
        # self._editor_instance_for_sizehint = None # Puedes quitar esto si no lo usas explícitamente

    def setFontSize(self, size: int):
        self._font_size = size # Atributo con guion bajo
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
        if isinstance(editor, CustomTextEdit): # Usar CustomTextEdit directamente
            value = index.model().data(index, Qt.ItemDataRole.EditRole) or ""
            editor.setPlainText(str(value))
            editor.setEditingIndex(index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex) -> None:
        if isinstance(editor, CustomTextEdit): # Usar CustomTextEdit
            original_value = index.model().data(index, Qt.ItemDataRole.EditRole)
            current_value = editor.toPlainText()
            if original_value != current_value:
                model.setData(index, current_value, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        editor.setGeometry(option.rect)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        doc = QTextDocument()
        doc.setPlainText(text)
        doc.setDefaultFont(self._font) # Usar la fuente del delegado (self._font)

        # CSS padding para QTableView::item (ej: 7px horizontal)
        # CSS padding para QTableView QTextEdit (ej: 3px horizontal)
        # Total padding horizontal interno a considerar para el text width del documento: (7+3)*2 = 20px
        # Sin embargo, option.rect.width() ya es el ancho de la celda.
        # El text width del documento debería ser el ancho de la celda menos el padding que el QTEXTEDIT
        # mismo añade internamente (CSS), que es 3px por lado.
        
        available_width_for_qtextedit_content = option.rect.width() - (3 * 2) # Restar padding del QTextEdit

        doc.setTextWidth(available_width_for_qtextedit_content)
        ideal_height_of_text = doc.size().height()

        # Padding vertical de la celda (QTableView::item)
        # Si QTableView::item tiene padding: 7px 8px; -> 7px arriba y 7px abajo
        # Padding vertical del QTextEdit (CSS)
        # Si QTableView QTextEdit tiene padding: 3px; -> 3px arriba y 3px abajo
        
        # La altura total es la altura del texto más el padding del QTextEdit dentro de la celda.
        # La celda ya tiene su propio padding que es manejado por option.rect.height.
        # Lo que queremos es que el contenido del QTextEdit quepa.
        # Entonces, la altura del texto + padding del QTextEdit debe ser la altura del contenido.
        
        # Altura del contenido dentro del QTextEdit
        content_height = ideal_height_of_text + (3 * 2) # Altura texto + padding superior/inferior del QTextEdit

        # Adicionalmente, la celda (QTableView::item) tiene su propio padding.
        # El sizeHint debe devolver el tamaño total que la celda necesita.
        # Si el padding del item es 7px (vertical), entonces la altura total es content_height + 2*7.
        # Pero option.rect ya debería reflejar el tamaño de la celda con su padding.
        # Lo que necesitamos es la altura *requerida* por el contenido.
        
        # Simplemente, la altura del texto más el padding del propio QTextEdit
        # y un pequeño extra para que no se vea tan justo.
        calculated_height = int(ideal_height_of_text + (3 * 2) + 4) # +4 como un pequeño buffer vertical

        # No dejar que la altura sea menor que una línea de texto estándar
        # Esto usa la fuente actual del delegado
        min_line_height = QFontMetrics(self._font).height() + (3 * 2) + 4
        
        return QSize(option.rect.width(), max(calculated_height, min_line_height))


    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # Guardar el estado del painter para restaurarlo al final
        painter.save()

        # Crear una nueva QStyleOptionViewItem y inicializarla con la opción y el índice actuales.
        # Esto es importante para que el estilo del widget (ej. QTableView) pueda ser aplicado correctamente.
        style_option = QStyleOptionViewItem(option) 
        self.initStyleOption(style_option, index) # El delegado base inicializa la opción con datos del modelo

        widget = style_option.widget # El widget que está pintando (QTableView)

        # 1. Pintar el fondo
        # Si la celda está seleccionada, usar el color de resaltado de la paleta.
        if style_option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(style_option.rect, style_option.palette.highlight())
        else:
            # Si no está seleccionada, verificar si el modelo proporciona un color de fondo.
            background_color_from_model = index.data(Qt.ItemDataRole.BackgroundRole)
            if background_color_from_model:
                if isinstance(background_color_from_model, QBrush):
                    painter.fillRect(style_option.rect, background_color_from_model)
                elif isinstance(background_color_from_model, QColor):
                    painter.fillRect(style_option.rect, QBrush(background_color_from_model))
                else:
                    # Fallback al fondo base de la paleta si el modelo no especifica uno o es inválido.
                    # style_option.backgroundBrush ya debería estar inicializado por initStyleOption
                    painter.fillRect(style_option.rect, style_option.backgroundBrush if style_option.backgroundBrush.style() != Qt.BrushStyle.NoBrush else style_option.palette.base())
            else:
                # Si el modelo no define color, usar el base de la paleta.
                painter.fillRect(style_option.rect, style_option.backgroundBrush if style_option.backgroundBrush.style() != Qt.BrushStyle.NoBrush else style_option.palette.base())


        # No pintar el texto si hay un editor persistente abierto para esta celda
        # Esto ayuda a prevenir el "texto doble" cuando el editor se abre.
        # El CSS que da un fondo al QTextEdit editor es la principal solución para el texto doble
        # durante la edición activa, pero esto es una salvaguarda adicional para el pintado.
        if widget and hasattr(widget, 'isPersistentEditorOpen') and widget.isPersistentEditorOpen(index):
            painter.restore()
            return

        # 2. Preparar para pintar el texto
        text_to_display = str(index.model().data(index, Qt.ItemDataRole.DisplayRole) or "")
        
        # Obtener el rectángulo donde se pintará el texto, ajustado por el estilo.
        # Esto considera el padding de la celda (QTableView::item)
        text_rect = widget.style().subElementRect(QStyle.SubElement.SE_ItemViewItemText, style_option, widget)

        # Configurar la fuente del painter con el tamaño de fuente del delegado.
        current_paint_font = QFont(style_option.font) # Empezar con la fuente de la opción (que ya podría tener el tamaño base)
        current_paint_font.setPointSize(self._font_size) # <--- CORRECCIÓN AQUÍ
        painter.setFont(current_paint_font)

        # Configurar el color del pen para el texto.
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
                    painter.setPen(style_option.palette.text().color()) # Color de texto por defecto
            else:
                painter.setPen(style_option.palette.text().color()) # Color de texto por defecto

        # 3. Pintar el texto
        # Usar QTextOption para el ajuste de palabras si drawText directamente no lo hace bien.
        # O, más robusto, usar un QTextLayout si se necesita control muy fino (más complejo).
        # Para QStyledItemDelegate, drawDisplay es a menudo suficiente si initStyleOption se usa bien.
        # Pero aquí estamos personalizando.
        
        # Flags para el pintado del texto: ajuste de palabras, alineación superior izquierda.
        text_flags = Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        
        # Opcional: Si el texto se corta a pesar del sizeHint, puedes intentar pintar con elipsis
        # text_to_display = painter.fontMetrics().elidedText(text_to_display, Qt.TextElideMode.ElideRight, text_rect.width())
        
        painter.drawText(text_rect, int(text_flags), text_to_display)

        # Restaurar el estado del painter
        painter.restore()