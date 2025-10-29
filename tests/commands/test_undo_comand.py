import pytest
from PyQt6.QtWidgets import QApplication
from main import MainWindow
from guion_editor.commands.undo_commands import EditCommand

@pytest.fixture
def app(qtbot):
    """Fixture para la aplicación principal."""
    test_app = QApplication.instance() or QApplication([])
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)
    return window

def test_edit_command_undo_redo(app, qtbot):
    """
    Verifica el funcionamiento de un comando de edición.
    """
    table_window = app.tableWindow
    model = table_window.pandas_model
    undo_stack = table_window.undo_stack
    
    # Añadir una fila para tener datos que editar
    qtbot.mouseClick(table_window.action_buttons['edit_add_row'], Qt.MouseButton.LeftButton)
    assert model.rowCount() == 1
    
    # Datos para el comando
    df_row_index = 0
    view_col_index = table_window.COL_CHARACTER_VIEW
    old_value = model.data(model.index(df_row_index, view_col_index))
    new_value = "NUEVO PERSONAJE"
    
    # Crear y ejecutar el comando (push lo ejecuta por primera vez)
    command = EditCommand(table_window, df_row_index, view_col_index, old_value, new_value)
    undo_stack.push(command)
    
    # Verificar que redo() funcionó
    assert model.data(model.index(df_row_index, view_col_index)) == new_value
    
    # Deshacer
    undo_stack.undo()
    
    # Verificar que undo() funcionó
    assert model.data(model.index(df_row_index, view_col_index)) == old_value
    
    # Rehacer
    undo_stack.redo()
    
    # Verificar que redo() funcionó de nuevo
    assert model.data(model.index(df_row_index, view_col_index)) == new_value