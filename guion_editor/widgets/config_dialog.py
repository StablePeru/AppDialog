from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QSpinBox, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt 


class ConfigDialog(QDialog):
    def __init__(self, current_trim=0, current_font_size=9):
        super().__init__()
        self.setWindowTitle("Settings")
        self.setFixedSize(300, 200)
        self.init_ui(current_trim, current_font_size)

    def init_ui(self, current_trim: int, current_font_size: int) -> None:
        layout = QVBoxLayout()

        # Configuración del valor de TRIM
        trim_layout = QHBoxLayout()
        trim_label = QLabel("Trim (ms):")
        self.trim_spinbox = QSpinBox()
        self.trim_spinbox.setRange(0, 10000)
        self.trim_spinbox.setValue(current_trim)
        trim_layout.addWidget(trim_label)
        trim_layout.addWidget(self.trim_spinbox)
        layout.addLayout(trim_layout)

        # Configuración del tamaño de fuente
        font_layout = QHBoxLayout()
        font_label = QLabel("Font Size:")
        self.font_spinbox = QSpinBox()
        self.font_spinbox.setRange(8, 48)
        self.font_spinbox.setValue(current_font_size)
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_spinbox)
        layout.addLayout(font_layout)

        # Botones de confirmación y cancelación
        buttons_layout = QHBoxLayout()
        self.accept_button = QPushButton("Accept")
        self.accept_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.accept_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)

        # Establece el layout principal de la ventana de diálogo
        self.setLayout(layout)

    # Devuelve los valores actuales de trim y tamaño de fuente
    def get_values(self) -> tuple[int, int]: # CAMBIO: tipo de retorno
        return self.trim_spinbox.value(), self.font_spinbox.value()
