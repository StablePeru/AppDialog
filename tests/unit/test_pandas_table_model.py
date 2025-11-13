import pytest
import pandas as pd
from PyQt6.QtGui import QBrush
from guion_editor.models.pandas_table_model import PandasTableModel, LINE_ERROR_BG_COLOR

# Datos de prueba para diferentes escenarios
DATA_NO_ERROR = {
    'IN': ["00:01:00:00", "00:01:00:00"], 'OUT': ["00:01:05:00", "00:01:05:00"],
    'PERSONAJE': ['IZZY', 'STELLA'], 'DIÁLOGO': ['Linea 1', 'Linea 2'], 'EUSKERA': ['', '']
}

DATA_CHAR_ERROR = { # Izzy tiene 6 líneas en DIÁLOGO
    'IN': ["00:01:00:00"] * 3, 'OUT': ["00:01:05:00"] * 3,
    'PERSONAJE': ['IZZY', 'IZZY', 'STELLA'],
    'DIÁLOGO': ['L1\nL2\nL3', 'L4\nL5\nL6', 'Linea de Stella'], 'EUSKERA': ['', '', '']
}

DATA_GROUP_ERROR = { # El grupo tiene 11 líneas en DIÁLOGO
    'IN': ["00:01:00:00"] * 3, 'OUT': ["00:01:05:00"] * 3,
    'PERSONAJE': ['IZZY', 'STELLA', 'MADISON'],
    'DIÁLOGO': ['L1\nL2\nL3\nL4', 'L5\nL6\nL7', 'L8\nL9\nL10\nL11'], 'EUSKERA': ['', '', '']
}

DATA_EUSKERA_PRIORITY = { # Error de 6 líneas en EUSKERA, aunque DIÁLOGO esté vacío
    'IN': ["00:01:00:00"], 'OUT': ["00:01:05:00"],
    'PERSONAJE': ['IZZY'], 'DIÁLOGO': [''], 'EUSKERA': ['L1\nL2\nL3\nL4\nL5\nL6']
}

@pytest.fixture
def model():
    """Fixture que crea un PandasTableModel vacío."""
    # Simula la estructura que necesita el constructor del modelo
    column_map = { 0: "__ROW_NUMBER__", 1: "SCENE", 2: "IN", 3: "OUT", 4: "PERSONAJE", 5: "DIÁLOGO", 6: "EUSKERA" }
    view_names = ["Nº", "SCENE", "IN", "OUT", "PERSONAJE", "DIÁLOGO", "EUSKERA"]
    return PandasTableModel(column_map, view_names)

def test_line_validation_no_error(model):
    """
    Verifica que no se marcan errores si no se cumplen las condiciones.
    """
    df = pd.DataFrame(DATA_NO_ERROR)
    model.set_dataframe(df)
    
    # El diccionario puede contener entradas 'True', pero no debe contener ninguna 'False'.
    has_errors = any(
        not status.get('DIÁLOGO', True) or not status.get('EUSKERA', True)
        for status in model._line_validation_status.values()
    )
    
    assert not has_errors # La aserción correcta es que no se encontraron errores

def test_line_validation_character_error(model):
    """Verifica la regla de 6 líneas para un solo personaje."""
    df = pd.DataFrame(DATA_CHAR_ERROR)
    model.set_dataframe(df)
    
    status = model._line_validation_status
    # Fila 0 (IZZY): DIÁLOGO debe ser inválido
    assert status[0]['DIÁLOGO'] is False
    # Fila 1 (IZZY): DIÁLOGO debe ser inválido
    assert status[1]['DIÁLOGO'] is False
    # Fila 2 (STELLA): DIÁLOGO debe ser válido
    assert status[2]['DIÁLOGO'] is True
    # Todas las de EUSKERA deben ser válidas
    assert status[0]['EUSKERA'] is True
    assert status[1]['EUSKERA'] is True

def test_line_validation_group_error(model):
    """Verifica la regla de 11 líneas para un grupo."""
    df = pd.DataFrame(DATA_GROUP_ERROR)
    model.set_dataframe(df)

    status = model._line_validation_status
    # Todas las filas del grupo deben tener DIÁLOGO inválido
    assert status[0]['DIÁLOGO'] is False
    assert status[1]['DIÁLOGO'] is False
    assert status[2]['DIÁLOGO'] is False

def test_line_validation_euskera_priority(model):
    """Verifica que EUSKERA tiene prioridad para el conteo."""
    df = pd.DataFrame(DATA_EUSKERA_PRIORITY)
    model.set_dataframe(df)

    status = model._line_validation_status
    # La columna DIÁLOGO debe ser válida (no se cuenta)
    assert status[0]['DIÁLOGO'] is True
    # La columna EUSKERA debe ser inválida (tiene 6 líneas)
    assert status[0]['EUSKERA'] is False