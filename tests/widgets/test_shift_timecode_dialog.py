from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt
from guion_editor.widgets.shift_timecode_dialog import ShiftTimecodeDialog

def test_shift_timecode_dialog_get_values(qtbot):
    """
    Verifica que el diálogo devuelve los valores correctos cuando se acepta.
    """
    # Se necesita una QApplication para cualquier test de widget
    app = QApplication.instance() or QApplication([])

    dialog = ShiftTimecodeDialog(default_fps=25)
    qtbot.addWidget(dialog) # qtbot se encargará de limpiar el widget
    
    # Simular la entrada del usuario
    qtbot.keyClicks(dialog.h_spinbox, "1")
    qtbot.keyClicks(dialog.m_spinbox, "2")
    qtbot.keyClicks(dialog.s_spinbox, "3")
    qtbot.keyClicks(dialog.f_spinbox, "4")
    dialog.dir_combo.setCurrentIndex(1) # 1 = Restar
    
    # Simular clic en el botón OK usando un QTimer para que el diálogo se procese
    def handle_dialog():
        ok_button = dialog.findChild(QDialog.DialogCode.Accepted)
        qtbot.mouseClick(ok_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(dialog.isVisible)
    handle_dialog()

    # Verificar los valores devueltos
    fps, offset_frames, sign = dialog.get_values()
    
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert fps == 25
    # (1*3600 + 2*60 + 3) * 25 + 4 = (3723 * 25) + 4 = 93075 + 4 = 93079
    assert offset_frames == 93079
    assert sign == -1 # Restar