# guion_editor/widgets/video_window.py

import os
from PyQt6.QtCore import pyqtSignal # CAMBIO
from PyQt6.QtGui import QFont       # CAMBIO
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QMessageBox # CAMBIO


class VideoWindow(QMainWindow):
    """
    Ventana independiente para alojar el VideoPlayerWidget.
    """
    close_detached = pyqtSignal()  # Señal para notificar que la ventana se ha cerrado

    def __init__(self, video_widget: QWidget):
        super().__init__()
        self.setWindowTitle("Reproductor de Video Independiente")
        self.setGeometry(150, 150, 800, 600)
        self.init_ui(video_widget)
        self.load_stylesheet()

    def init_ui(self, video_widget: QWidget) -> None:
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        self.video_widget = video_widget
        self.video_widget.setParent(self)
        self.video_widget.setObjectName("video_widget")
        layout.addWidget(self.video_widget)

        self.attach_button = QPushButton("Adjuntar de Nuevo")
        self.attach_button.setObjectName("attach_button")
        self.attach_button.setFont(QFont("Arial", 12))
        self.attach_button.clicked.connect(self.attach_back)
        layout.addWidget(self.attach_button)

        self.setCentralWidget(central_widget)

    def load_stylesheet(self) -> None:
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(current_dir, '..', 'styles', 'main.css')

            with open(css_path, 'r') as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error de Estilos", f"Error al cargar el stylesheet: {str(e)}")

    def attach_back(self) -> None:
        self.close_detached.emit()
        self.close()

    def closeEvent(self, event) -> None:
        self.close_detached.emit()
        super().closeEvent(event)
