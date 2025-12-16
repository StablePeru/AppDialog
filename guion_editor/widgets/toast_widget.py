
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve, QSequentialAnimationGroup, QPauseAnimation
from PyQt6.QtGui import QPainter, QColor, QBrush, QFont

from guion_editor.utils.theme_manager import theme_manager

class ToastWidget(QWidget):
    """
    A custom widget for displaying non-blocking notifications (Toasts).
    Overlays on the parent widget typically at the bottom center.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Click-through
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # Rounded corners support

        self.message = "" # Store message for paintEvent

        # UI Setup
        self._setup_ui()
        
        # Animations
        self._setup_animations()

        # Hide initially
        self.hide()

    def _setup_ui(self):
        # Style is now handled by paintEvent
        # self.setStyleSheet("""
        #     QWidget {
        #         background-color: rgba(40, 40, 40, 220);
        #         border-radius: 10px;
        #         padding: 10px;
        #     }
        #     QLabel {
        #         color: white;
        #         background-color: transparent;
        #         font-weight: bold;
        #         font-size: 14px;
        #     }
        # """)

        layout = QHBoxLayout()
        layout.setContentsMargins(20, 10, 20, 10)
        
        # The QLabel is no longer used for displaying text, but its layout might still be useful for sizing.
        # We'll keep it for now, but its text will be empty and paintEvent will draw the actual message.
        self.label = QLabel("") 
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("background-color: transparent;") # Ensure label background is transparent
        layout.addWidget(self.label)
        
        self.setLayout(layout)
        
        # Opacity Effect for fading
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

    def _setup_animations(self):
        # Fade In
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Hold (Pause)
        self.hold = QPauseAnimation(2000)

        # Fade Out
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(500)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        # Sequence
        self.anim_group = QSequentialAnimationGroup(self)
        self.anim_group.addAnimation(self.fade_in)
        self.anim_group.addAnimation(self.hold)
        self.anim_group.addAnimation(self.fade_out)
        self.anim_group.finished.connect(self.hide)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bg_color = theme_manager.get_color("toast_bg")
        text_color = theme_manager.get_color("toast_text")
        border_color = theme_manager.get_color("toast_border")

        # Fondo
        painter.setBrush(QBrush(bg_color))
        painter.setPen(border_color) 
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 5, 5)

        # Texto
        painter.setPen(text_color)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)

    def show_message(self, message: str, duration_ms: int = 2000):
        # Update text
        self.message = message
        # self.label.setText(message) # No longer needed if painting manually, but harmless
        self.adjustSize()
        self.update() # Trigger paintEvent
        
        # Center on parent bottom
        if self.parent():
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            y = parent_rect.height() - self.height() - 50 # 50px from bottom
            self.move(x, y)
        
        # Update duration
        self.hold.setDuration(duration_ms)

        self.raise_()
        self.show()
        self.anim_group.stop()
        self.anim_group.start()
