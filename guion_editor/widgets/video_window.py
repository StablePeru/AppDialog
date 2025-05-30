# guion_editor/widgets/video_window.py

import os
from PyQt6.QtCore import pyqtSignal, QSize, Qt, QTimer # Asegúrate de importar QTimer
from PyQt6.QtGui import QFont, QIcon, QKeyEvent
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QMessageBox


class VideoWindow(QMainWindow):
    close_detached = pyqtSignal()

    def __init__(self, video_player_widget_instance: QWidget, get_icon_func=None): # Renombrar parámetro
        super().__init__()
        self.get_icon = get_icon_func
        self.setWindowTitle("Reproductor de Video Independiente")
        self.setGeometry(150, 150, 800, 600)
        
        # Renombrar self.video_widget_ref a self.video_widget
        # Este es el VideoPlayerWidget que esta ventana está mostrando.
        self.video_widget = video_player_widget_instance 
        
        self.init_ui() # init_ui ahora usará self.video_widget
        self.load_stylesheet()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.f6_pressed_in_detached_window = False
        
        self.activateWindow()
        self.raise_()
        # No necesitas llamar a self.setFocus() aquí explícitamente, 
        # activateWindow y el foco del sistema operativo deberían manejarlo.

    def init_ui(self) -> None: # Ya no necesita el parámetro video_widget_param
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        # self.video_widget ya está definido en __init__
        self.video_widget.setParent(self) 
        # self.video_widget.setObjectName("video_widget") # El objectName ya debería estar en VideoPlayerWidget
        layout.addWidget(self.video_widget)

        self.attach_button = QPushButton(" Adjuntar de Nuevo")
        if self.get_icon:
            self.attach_button.setIcon(self.get_icon("attach_video_icon.svg"))
            self.attach_button.setIconSize(QSize(20, 20))
        self.attach_button.setObjectName("attach_button")
        self.attach_button.clicked.connect(self.attach_back)
        layout.addWidget(self.attach_button)

        self.setCentralWidget(central_widget)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()

        if not self.video_widget or not hasattr(self.video_widget, 'media_player'):
            super().keyPressEvent(event)
            return

        handled = False
        if key == Qt.Key.Key_F5:
            if hasattr(self.video_widget, 'mark_in'):
                QTimer.singleShot(0, self.video_widget.mark_in) # Diferir llamada
                handled = True
        elif key == Qt.Key.Key_F6:
            if not event.isAutoRepeat() and not self.f6_pressed_in_detached_window:
                if hasattr(self.video_widget, 'start_out_timer'):
                    QTimer.singleShot(0, self.video_widget.start_out_timer) # Diferir llamada
                    self.f6_pressed_in_detached_window = True
                    handled = True
        elif key == Qt.Key.Key_F7:
            if hasattr(self.video_widget, 'change_position'):
                QTimer.singleShot(0, lambda: self.video_widget.change_position(-5000)) # Diferir
                handled = True
        elif key == Qt.Key.Key_F8:
            if hasattr(self.video_widget, 'toggle_play'):
                QTimer.singleShot(0, self.video_widget.toggle_play) # Diferir
                handled = True
        elif key == Qt.Key.Key_F9:
            if hasattr(self.video_widget, 'change_position'):
                QTimer.singleShot(0, lambda: self.video_widget.change_position(5000)) # Diferir
                handled = True

        if handled:
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        key = event.key()

        if not self.video_widget or not hasattr(self.video_widget, 'media_player'):
            super().keyReleaseEvent(event)
            return

        handled = False
        if key == Qt.Key.Key_F6:
            if not event.isAutoRepeat() and self.f6_pressed_in_detached_window:
                if hasattr(self.video_widget, 'stop_out_timer'):
                    QTimer.singleShot(0, self.video_widget.stop_out_timer) # Diferir
                    self.f6_pressed_in_detached_window = False
                    handled = True
        
        if handled:
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def load_stylesheet(self) -> None:
        # ... (sin cambios)
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(current_dir, '..', 'styles', 'main.css')
            
            if not os.path.exists(css_path):
                alt_css_path = os.path.join(os.path.dirname(current_dir), 'styles', 'main.css')
                if os.path.exists(alt_css_path):
                    css_path = alt_css_path
                else:
                    return

            with open(css_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error de Estilos", f"Error al cargar el stylesheet: {str(e)}")


    def attach_back(self) -> None:
        self.close_detached.emit()
        self.close()

    def closeEvent(self, event) -> None:
        if self.f6_pressed_in_detached_window:
            if hasattr(self.video_widget, 'stop_out_timer'):
                # No es necesario diferir aquí, ya que estamos cerrando
                self.video_widget.stop_out_timer() 
            self.f6_pressed_in_detached_window = False
        
        self.close_detached.emit()
        super().closeEvent(event)