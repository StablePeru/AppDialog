from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt
from guion_editor.widgets.shift_timecode_dialog import ShiftTimecodeDialog

def test_shift_timecode_dialog_get_values(qtbot):
    """
    Verifica que el diálogo devuelve los valores correctos cuando se acepta.
    """
    app = QApplication.instance() or QApplication([])

    dialog = ShiftTimecodeDialog(default_fps=25)
    qtbot.addWidget(dialog)
    dialog.show() # Es importante mostrar el diálogo
    
    # Simular la entrada del usuario
    dialog.h_spinbox.setValue(1)
    dialog.m_spinbox.setValue(2)
    dialog.s_spinbox.setValue(3)
    dialog.f_spinbox.setValue(4)
    dialog.dir_combo.setCurrentIndex(1) # 1 = Restar
    
    # Simular la aceptación del diálogo directamente
    dialog.accept()

    # Verificar los valores devueltos
    fps, offset_frames, sign = dialog.get_values()
    
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert fps == 25
    # (1*3600 + 2*60 + 3) * 25 + 4 = 93079
    assert offset_frames == 93079
    assert sign == -1

def test_shift_timecode_dialog_cancel(qtbot):
    """Verifica que el diálogo devuelve None cuando se cancela."""
    app = QApplication.instance() or QApplication([])
    dialog = ShiftTimecodeDialog(default_fps=25)
    qtbot.addWidget(dialog)
    dialog.show()
    
    dialog.reject() # Simular cancelación
    
    assert dialog.get_values() is None
    assert dialog.result() == QDialog.DialogCode.Rejected