import pytest
from guion_editor.utils.dialog_utils import ajustar_dialogo, tc_to_frames, frames_to_tc

# Tests para la función de ajuste de diálogos
def test_ajustar_dialogo_sin_cambios():
    texto = "Esta es una línea corta que no necesita ajuste."
    assert ajustar_dialogo(texto, max_chars=60) == texto

def test_ajustar_dialogo_con_ajuste_simple():
    texto = "Esta es una línea muy larga que definitivamente necesita ser ajustada para no exceder el límite de caracteres establecido."
    esperado = "Esta es una línea muy larga que definitivamente necesita\nser ajustada para no exceder el límite de caracteres\nestablecido."
    assert ajustar_dialogo(texto, max_chars=50) == esperado

def test_ajustar_dialogo_con_palabra_larga():
    texto = "Una palabra supercalifragilisticoespialidoso no se puede cortar."
    esperado = "Una palabra\nsupercalifragilisticoespialidoso no se puede cortar."
    assert ajustar_dialogo(texto, max_chars=20) == esperado

# Tests para las funciones de conversión de timecode
@pytest.mark.parametrize("tc_str, fps, expected_frames", [
    ("00:00:01:00", 25, 25),
    ("00:01:00:00", 25, 1500),
    ("01:00:00:00", 25, 90000),
    ("00:00:00:00", 25, 0),
    ("01:02:03:04", 25, 93079),
    ("INVALIDO", 25, None), # Manejo de errores
    ("", 25, None),
])
def test_tc_to_frames(tc_str, fps, expected_frames):
    assert tc_to_frames(tc_str, fps) == expected_frames

@pytest.mark.parametrize("frames, fps, expected_tc", [
    (25, 25, "00:00:01:00"),
    (1500, 25, "00:01:00:00"),
    (90000, 25, "01:00:00:00"),
    (0, 25, "00:00:00:00"),
    (93079, 25, "01:02:03:04"),
    (-100, 25, "00:00:00:00"), # Manejo de valores negativos
])
def test_frames_to_tc(frames, fps, expected_tc):
    assert frames_to_tc(frames, fps) == expected_tc