import pytest
import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from main import MainWindow # Importa tu ventana principal

@pytest.fixture
def app(qtbot):
    """Un fixture para crear la aplicación principal para los tests."""
    test_app = QApplication.instance() or QApplication([])
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)
    return window

def test_add_new_row(app, qtbot):
    """
    Verifica que al hacer clic en 'Agregar Línea', se añade una fila al modelo.
    """
    table_window = app.tableWindow
    model = table_window.pandas_model
    
    initial_rows = model.rowCount()
    
    # Buscar el botón de "Agregar Lína"
    add_row_button = table_window.action_buttons['edit_add_row']
    
    # Simular clic
    qtbot.mouseClick(add_row_button, Qt.MouseButton.LeftButton)
    
    # Verificar que el número de filas en el modelo ha aumentado en 1
    assert model.rowCount() == initial_rows + 1

def test_remove_row(app, qtbot, monkeypatch):
    """
    Verifica que la acción de eliminar fila funciona.
    Usa monkeypatch para simular la respuesta "Sí" en el diálogo de confirmación.
    """
    table_window = app.tableWindow
    model = table_window.pandas_model
    
    # Añadir una fila para asegurarse de que haya algo que eliminar
    qtbot.mouseClick(table_window.action_buttons['edit_add_row'], Qt.MouseButton.LeftButton)
    initial_rows = model.rowCount()
    assert initial_rows > 0
    
    # Seleccionar la primera fila
    table_window.table_view.selectRow(0)
    
    # Simular la respuesta QMessageBox.StandardButton.Yes
    monkeypatch.setattr('PyQt6.QtWidgets.QMessageBox.question', lambda *args: QMessageBox.StandardButton.Yes)
    
    # Buscar y hacer clic en el botón de eliminar
    remove_row_button = table_window.action_buttons['edit_delete_row']
    qtbot.mouseClick(remove_row_button, Qt.MouseButton.LeftButton)
    
    # Verificar que la fila fue eliminada
    assert model.rowCount() == initial_rows - 1

def test_line_alert_appears_on_error(app, qtbot):
    """
    Verifica que el botón de alerta de LÍNEAS aparece cuando se introduce
    un guion con errores de línea.
    """
    table_window = app.tableWindow
    model = table_window.pandas_model
    alert_button = table_window.line_error_indicator_button

    # 1. Estado inicial: el botón no debe ser visible
    assert not alert_button.isVisible()

    # 2. Cargar un DataFrame con un error conocido (6 líneas para un personaje)
    error_data = {
        'IN': ["00:01:00:00"], 'OUT': ["00:01:05:00"], 'PERSONAJE': ['TEST_CHAR'],
        'DIÁLOGO': ['L1\nL2\nL3\nL4\nL5\nL6'], 'EUSKERA': ['']
    }
    error_df = pd.DataFrame(error_data)
    
    # Usamos qtbot.waitForSignal para asegurarnos de que la UI se actualiza
    # después de que el modelo se haya reseteado.
    with qtbot.waitForSignal(model.modelReset, raising=True):
        model.set_dataframe(error_df)

    # 3. Verificar que el botón de alerta es ahora visible
    assert alert_button.isVisible()
    assert "LÍNEAS" in alert_button.text()

    # 4. Simular clic y verificar que navega a la fila correcta
    qtbot.mouseClick(alert_button, Qt.MouseButton.LeftButton)
    selected_rows = table_window.table_view.selectionModel().selectedRows()
    assert len(selected_rows) == 1
    assert selected_rows[0].row() == 0