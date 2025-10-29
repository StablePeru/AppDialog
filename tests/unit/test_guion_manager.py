import pandas as pd
import json
from guion_editor.utils.guion_manager import GuionManager

def test_save_to_srt(tmp_path):
    """
    Verifica que la exportación a SRT funciona correctamente.
    """
    manager = GuionManager()
    output_file = tmp_path / "test.srt"
    
    # Crear un DataFrame de ejemplo
    data = {
        'IN': ["00:00:01:00", "00:00:05:12"],
        'OUT': ["00:00:03:05", "00:00:08:00"],
        'DIÁLOGO': ["Primera línea de diálogo.", "Segunda línea."]
    }
    df = pd.DataFrame(data)
    
    # Exportar
    manager.save_to_srt(str(output_file), df, column_to_export='DIÁLOGO')
    
    # Leer el archivo y verificar su contenido
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    expected_content = (
        "1\n"
        "00:00:01,000 --> 00:00:03,200\n"
        "Primera línea de diálogo.\n\n"
        "2\n"
        "00:00:05,480 --> 00:00:08,000\n"
        "Segunda línea.\n\n"
    )
    
    assert content == expected_content

def test_save_to_json(tmp_path):
    """
    Verifica que el guardado en JSON incluye cabecera y datos.
    """
    manager = GuionManager()
    output_file = tmp_path / "test.json"
    
    header = {"product_name": "Test Product", "chapter_number": "01"}
    data = {
        'ID': [1],
        'SCENE': ['1'],
        'IN': ["00:00:01:00"],
        'OUT': ["00:00:03:05"],
        'PERSONAJE': ['NARRADOR'],
        'DIÁLOGO': ["Hola mundo"],
        'EUSKERA': ['Kaixo mundua'],
        'OHARRAK': ['Nota'],
        'BOOKMARK': [False]
    }
    df = pd.DataFrame(data)
    
    manager.save_to_json(str(output_file), df, header)
    
    with open(output_file, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)
        
    assert loaded_data['header'] == header
    assert len(loaded_data['data']) == 1
    assert loaded_data['data'][0]['PERSONAJE'] == 'NARRADOR'