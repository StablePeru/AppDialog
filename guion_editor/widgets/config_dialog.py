from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QSpinBox, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt, QSize # Añadir QSize
from PyQt6.QtGui import QIcon      # Añadir QIcon


class ConfigDialog(QDialog):
    def __init__(self, current_trim=0, current_font_size=11, current_line_length=60, get_icon_func=None): # -> MODIFICADO
        super().__init__()
        self.get_icon = get_icon_func 
        self.setWindowTitle("Settings")
        self.setFixedSize(350, 250) # -> MODIFICADO: Aumentamos un poco el tamaño
        self.init_ui(current_trim, current_font_size, current_line_length) # -> MODIFICADO

    def init_ui(self, current_trim: int, current_font_size: int, current_line_length: int) -> None: # -> MODIFICADO
        layout = QVBoxLayout()
        icon_size_buttons = QSize(18, 18)

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

        # -> INICIO: NUEVA SECCIÓN para longitud de línea
        line_length_layout = QHBoxLayout()
        line_length_label = QLabel("Caracteres por línea (ajuste):")
        self.line_length_spinbox = QSpinBox()
        self.line_length_spinbox.setRange(20, 120)  # Un rango razonable
        self.line_length_spinbox.setValue(current_line_length)
        line_length_layout.addWidget(line_length_label)
        line_length_layout.addWidget(self.line_length_spinbox)
        layout.addLayout(line_length_layout)
        # -> FIN: NUEVA SECCIÓN

        # Botones de confirmación y cancelación
        buttons_layout = QHBoxLayout()
        self.accept_button = QPushButton(" Accept") 
        if self.get_icon:
            self.accept_button.setIcon(self.get_icon("accept_icon.svg"))
            self.accept_button.setIconSize(icon_size_buttons)
        self.accept_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton(" Cancel") 
        if self.get_icon:
            self.cancel_button.setIcon(self.get_icon("cancel_icon.svg"))
            self.cancel_button.setIconSize(icon_size_buttons)
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addStretch() 
        buttons_layout.addWidget(self.accept_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    # Devuelve los valores actuales
    def get_values(self) -> tuple[int, int, int]: # -> MODIFICADO
        return self.trim_spinbox.value(), self.font_spinbox.value(), self.line_length_spinbox.value() # -> MODIFICADO