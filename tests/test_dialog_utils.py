# tests/test_dialog_utils.py

import pytest
from guion_editor.utils.dialog_utils import ajustar_dialogo, tc_to_frames, frames_to_tc

# --- Pruebas para ajustar_dialogo (ya existentes) ---
@pytest.mark.parametrize("texto_entrada, max_chars, texto_esperado", [
    ("Esta línea es corta.", 60, "Esta línea es corta."),
    ("Esta es una línea de diálogo muy larga que definitivamente debería ser dividida por la función.", 60,
     "Esta es una línea de diálogo muy larga que definitivamente\n"
     "debería ser dividida por la función."),
    ("", 60, ""),
    ("PRIMERA LÍNEA CORTA\nEsta segunda línea es bastante más larga y probablemente necesite ser ajustada en algún punto.", 60,
     "PRIMERA LÍNEA CORTA\n"
     "Esta segunda línea es bastante más larga y probablemente\n"
     "necesite ser ajustada en algún punto."),
    ("Esta línea tiene exactamente 60 caracteres de longitud!!!", 60,
     "Esta línea tiene exactamente 60 caracteres de longitud!!!"),
    ("Una palabra supercalifragilisticoespialidoso que es muy larga.", 30,
     "Una palabra\n"
     "supercalifragilisticoespialidoso\n"
     "que es muy larga."),
])
def test_ajustar_dialogo_varios_casos(texto_entrada, max_chars, texto_esperado):
    """
    Prueba la función ajustar_dialogo con múltiples escenarios.
    """
    resultado_real = ajustar_dialogo(texto_entrada, max_chars)
    assert resultado_real == texto_esperado

# --- NUEVAS PRUEBAS PARA CONVERSIÓN DE TIMECODE ---

@pytest.mark.parametrize("tc_string, fps, expected_frames", [
    # Casos válidos
    ("00:00:00:00", 25, 0),
    ("00:00:01:00", 25, 25),
    ("00:00:00:10", 25, 10),
    ("00:01:10:05", 25, 1755),  # (70 segundos * 25 fps) + 5 frames
    ("01:00:00:00", 25, 90000), # (3600 segundos * 25 fps)
    ("00:00:01:00", 30, 30),    # Probando con diferentes FPS

    # Casos inválidos que deben devolver None
    ("invalid", 25, None),
    ("01:02:03", 25, None),      # Formato incompleto
    ("01:02:03:04:05", 25, None),# Formato demasiado largo
    ("", 25, None),             # String vacío
])
def test_tc_to_frames(tc_string, fps, expected_frames):
    """
    Prueba la conversión de un string de timecode a un número total de frames.
    """
    assert tc_to_frames(tc_string, fps) == expected_frames


@pytest.mark.parametrize("frames, fps, expected_tc", [
    # Casos válidos
    (0, 25, "00:00:00:00"),
    (25, 25, "00:00:01:00"),
    (10, 25, "00:00:00:10"),
    (1755, 25, "00:01:10:05"),
    (90000, 25, "01:00:00:00"),
    (30, 30, "00:00:01:00"),    # Probando con diferentes FPS
    (9000000, 25, "100:00:00:00"), # Horas por encima de 99

    # Casos límite
    (-100, 25, "00:00:00:00"),   # Los frames negativos deben ser tratados como 0
])
def test_frames_to_tc(frames, fps, expected_tc):
    """
    Prueba la conversión de un número total de frames a un string de timecode.
    """
    assert frames_to_tc(frames, fps) == expected_tc