# guion_editor/widgets/shift_timecode_dialog.py

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QSpinBox,
    QHBoxLayout, QVBoxLayout, QDialog, QComboBox, QDialogButtonBox
)
from PyQt6.QtCore import QSize

class ShiftTimecodeDialog(QDialog):
    def __init__(self, default_fps: int = 25, get_icon_func=None, parent=None):
        super().__init__(parent)
        self.get_icon = get_icon_func
        self.setWindowTitle("Desplazar Timecodes (IN/OUT)")
        self.setMinimumWidth(450)
        self._init_ui(default_fps)

    def _init_ui(self, default_fps: int):
        main_layout = QVBoxLayout(self)

        # FPS
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 240)
        self.fps_spinbox.setValue(default_fps)
        self.fps_spinbox.setToolTip("Frames Por Segundo a utilizar para los cálculos.")
        
        row_fps = QHBoxLayout()
        row_fps.addWidget(QLabel("FPS:"))
        row_fps.addWidget(self.fps_spinbox)
        main_layout.addLayout(row_fps)

        # Offset HH:MM:SS:FF
        self.h_spinbox = QSpinBox(); self.h_spinbox.setRange(0, 999)
        self.m_spinbox = QSpinBox(); self.m_spinbox.setRange(0, 59)
        self.s_spinbox = QSpinBox(); self.s_spinbox.setRange(0, 59)
        self.f_spinbox = QSpinBox(); self.f_spinbox.setRange(0, 239)
        self.fps_spinbox.valueChanged.connect(self._sync_frame_max)
        self._sync_frame_max(default_fps) # Sincronización inicial

        row_offset = QHBoxLayout()
        row_offset.addWidget(QLabel("Cantidad a desplazar:"))
        row_offset.addWidget(self.h_spinbox); row_offset.addWidget(QLabel("h"))
        row_offset.addWidget(self.m_spinbox); row_offset.addWidget(QLabel("m"))
        row_offset.addWidget(self.s_spinbox); row_offset.addWidget(QLabel("s"))
        row_offset.addWidget(self.f_spinbox); row_offset.addWidget(QLabel("f"))
        main_layout.addLayout(row_offset)

        # Dirección (Sumar/Restar)
        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["Sumar (Adelantar)", "Restar (Retrasar)"])
        row_dir = QHBoxLayout()
        row_dir.addWidget(QLabel("Operación:"))
        row_dir.addWidget(self.dir_combo)
        main_layout.addLayout(row_dir)

        # Botones estándar OK/Cancel
        icon_size_buttons = QSize(18, 18)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText(" Aceptar")
        if self.get_icon:
            ok_button.setIcon(self.get_icon("accept_icon.svg"))
            ok_button.setIconSize(icon_size_buttons)

        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setText(" Cancelar")
        if self.get_icon:
            cancel_button.setIcon(self.get_icon("cancel_icon.svg"))
            cancel_button.setIconSize(icon_size_buttons)
            
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _sync_frame_max(self, fps_value: int):
        """Ajusta el valor máximo del spinbox de frames según los FPS."""
        self.f_spinbox.setMaximum(max(fps_value - 1, 0))

    def _offset_to_frames(self, h: int, m: int, s: int, f: int, fps: int) -> int:
        """Convierte el offset introducido a un número total de frames."""
        f = min(f, max(fps - 1, 0))
        return ((h * 3600 + m * 60 + s) * fps) + f

    def get_values(self) -> tuple[int, int, int] | None:
        """
        Devuelve los valores introducidos por el usuario si se acepta el diálogo.
        Retorna: (fps, offset_en_frames, signo) o None si se cancela.
        """
        if self.result() == QDialog.DialogCode.Accepted:
            fps = self.fps_spinbox.value()
            offset_frames = self._offset_to_frames(
                self.h_spinbox.value(),
                self.m_spinbox.value(),
                self.s_spinbox.value(),
                self.f_spinbox.value(),
                fps
            )
            sign = 1 if self.dir_combo.currentIndex() == 0 else -1
            return fps, offset_frames, sign
        return None