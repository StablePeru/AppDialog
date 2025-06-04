# guion_editor/widgets/video_window.py
import os
from PyQt6.QtCore import pyqtSignal, QSize, Qt, QTimer, QKeyCombination
from PyQt6.QtGui import QFont, QIcon, QKeyEvent, QKeySequence
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QMessageBox

class VideoWindow(QMainWindow):
    close_detached = pyqtSignal()

    def __init__(self, video_player_widget_instance: QWidget, get_icon_func=None, main_window=None): # Added main_window
        super().__init__()
        self.get_icon = get_icon_func
        self.main_window = main_window # Store reference
        self.video_widget = video_player_widget_instance 
        self.f6_key_pressed_internally = False # For F6 state within this window

        self.setWindowTitle("Reproductor de Video Independiente")
        self.setGeometry(150, 150, 800, 600)
        
        self.init_ui()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) # Important for key events
        self.activateWindow(); self.raise_()
        self.video_widget.setFocus() # Give focus to the player inside

    def init_ui(self) -> None:
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        # self.video_widget is already set in __init__
        # Its parent is changed when added to this layout (or explicitly by setParent)
        layout.addWidget(self.video_widget)

        self.attach_button = QPushButton(" Adjuntar de Nuevo")
        if self.get_icon:
            self.attach_button.setIcon(self.get_icon("attach_video_icon.svg"))
            self.attach_button.setIconSize(QSize(20, 20))
        self.attach_button.setObjectName("attach_button")
        self.attach_button.setToolTip("Volver a adjuntar el reproductor a la ventana principal")
        self.attach_button.clicked.connect(self.attach_back)
        layout.addWidget(self.attach_button)
        self.setCentralWidget(central_widget)

    def update_key_listeners(self):
        # Called by ShortcutManager if shortcuts change.
        # For "video_mark_out_hold", its QKeySequence is stored in the QAction.
        # KeyPress/Release events in this widget will query this QAction's shortcut.
        pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # print(f"VPW KeyPress: key={event.key()}, combo={event.keyCombination()}, focus={QApplication.focusWidget()}")
        if not self.main_window or not hasattr(self.main_window, 'mark_out_hold_key_sequence'): # Comprueba el nuevo atributo
            super().keyPressEvent(event)
            return

        current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence
        # print(f"  VPW: Expected F6 combo from main_window: {current_mark_out_shortcut[0] if not current_mark_out_shortcut.isEmpty() else 'EMPTY'}")
            
        key_match = False
        if not current_mark_out_shortcut.isEmpty():
            # event.keyCombination() es la forma correcta de obtener la combinación del evento
            if event.keyCombination() == current_mark_out_shortcut[0]: 
                key_match = True
        
        if key_match and not event.isAutoRepeat() and not self.f6_key_pressed_internally:
            self.f6_key_pressed_internally = True
            # --- CORRECCIÓN AQUÍ ---
            if self.video_widget and hasattr(self.video_widget, 'handle_out_button_pressed'):
                self.video_widget.handle_out_button_pressed()
            # --- FIN DE LA CORRECCIÓN ---
            event.accept()
            return
        
        # Si F6 no coincidió, deja que las QActions de este widget (si las tuviera) o del padre se procesen
        super().keyPressEvent(event)


    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if not self.main_window or not hasattr(self.main_window, 'mark_out_hold_key_sequence') or not self.video_widget:
            super().keyReleaseEvent(event)
            return

        # --- CORRECCIÓN AQUÍ ---
        current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence
        # --- FIN DE LA CORRECCIÓN ---
            
        key_match = False
        if not current_mark_out_shortcut.isEmpty():
            if event.keyCombination() == current_mark_out_shortcut[0]:
                key_match = True

        if key_match and not event.isAutoRepeat() and self.f6_key_pressed_internally:
            self.f6_key_pressed_internally = False
            if hasattr(self.video_widget, 'handle_out_button_released'):
                self.video_widget.handle_out_button_released()
            event.accept()
            return
        
        super().keyReleaseEvent(event)

    def attach_back(self) -> None:
        # This method will trigger closeEvent, which then emits close_detached
        self.close() 

    def closeEvent(self, event) -> None:
        # Ensure F6 state is reset if window is closed while key is pressed
        if self.f6_key_pressed_internally:
            if hasattr(self.video_widget, 'handle_out_button_released'):
                self.video_widget.handle_out_button_released() 
            self.f6_key_pressed_internally = False
        
        self.close_detached.emit() # Signal MainWindow to re-attach
        super().closeEvent(event)