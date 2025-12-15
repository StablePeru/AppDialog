from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve, QSequentialAnimationGroup, QPauseAnimation
from PyQt6.QtGui import QColor, QPalette, QFont

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

        # UI Setup
        self._setup_ui()
        
        # Animations
        self._setup_animations()

        # Hide initially
        self.hide()

    def _setup_ui(self):
        # Style
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(40, 40, 40, 220);
                border-radius: 10px;
                padding: 10px;
            }
            QLabel {
                color: white;
                background-color: transparent;
                font-weight: bold;
                font-size: 14px;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(20, 10, 20, 10)
        
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

    def show_message(self, message: str, duration_ms: int = 2000):
        # Update text
        self.label.setText(message)
        self.adjustSize()
        
        # Center on parent bottom
        if self.parent():
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            y = parent_rect.height() - self.height() - 50 # 50px from bottom
            self.move(x, y)
        
        # Update duration if needed (adjusting the pause animation is tricky in group, 
        # simpler to just recreate prompt or stick to default. 
        # For this Stability Update, fixed duration is fine, but we can update hold duration property directly)
        self.hold.setDuration(duration_ms)

        self.raise_()
        self.show()
        self.anim_group.stop()
        self.anim_group.start()
