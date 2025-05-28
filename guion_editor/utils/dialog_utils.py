import re
from docx import Document

def ajustar_dialogo(dialogo):
    """
    Ajusta el texto del diálogo para que cada línea tenga un máximo de 60 caracteres.
    """
    palabras = dialogo.split()
    linea_actual = ""
    lineas_ajustadas = []

    for palabra in palabras:
        test_linea = linea_actual + (" " if linea_actual else "") + palabra
        if contar_caracteres(test_linea) > 60:
            lineas_ajustadas.append(linea_actual)
            linea_actual = palabra
        else:
            linea_actual = test_linea

    if linea_actual:
        lineas_ajustadas.append(linea_actual)

    return "\n".join(lineas_ajustadas)


def contar_caracteres(dialogo):
    """
    Cuenta los caracteres en el diálogo, excluyendo el texto entre paréntesis.
    """
    dialogo_limpio = re.sub(r'\([^)]*\)', '', dialogo)
    return len(dialogo_limpio)


def es_nombre_personaje(texto):
    """
    Determina si un texto corresponde a un posible nombre de personaje.
    En este formato específico, los personajes:
    - Están en mayúsculas
    - Son relativamente cortos (generalmente una o dos palabras)
    - Pueden incluir números o sufijos (_1, _2, etc.)
    """
    # Si tiene puntos o comas, probablemente es un diálogo
    if '.' in texto or ',' in texto:
        return False
    
    # Si tiene más de 3 palabras, probablemente no es un personaje
    palabras = texto.split()
    if len(palabras) > 3:
        return False
    
    # Debe estar en mayúsculas (permitimos números y algunos caracteres especiales)
    return texto.upper() == texto


def leer_guion(docx_file):
    """
    Lee un archivo DOCX y extrae los personajes y sus diálogos, formateados en una estructura de guion.
    Formato esperado:
    PERSONAJE
    Diálogo
    
    PERSONAJE
    Diálogo
    """
    try:
        doc = Document(docx_file)
        guion = []
        personaje_actual = None
        dialogo_acumulado = []
        
        # Filtramos líneas vacías
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        
        i = 0
        while i < len(paragraphs):
            texto = paragraphs[i]
            
            # Verificamos si es un nombre de personaje
            if es_nombre_personaje(texto):
                # Si teníamos un personaje anterior, guardamos su diálogo
                if personaje_actual:
                    guardar_dialogo(guion, personaje_actual, dialogo_acumulado)
                
                personaje_actual = texto
                dialogo_acumulado = []
                
                # Miramos si hay diálogo en la siguiente línea
                if i + 1 < len(paragraphs):
                    siguiente_texto = paragraphs[i + 1]
                    # Si la siguiente línea NO es un personaje, es diálogo
                    if not es_nombre_personaje(siguiente_texto):
                        dialogo_acumulado.append(siguiente_texto)
                        i += 2  # Avanzamos dos líneas (personaje + diálogo)
                        continue
                
                # Si no hay diálogo o la siguiente línea es otro personaje
                i += 1
            else:
                # Si no es un personaje pero tenemos uno activo, añadimos como diálogo
                if personaje_actual:
                    dialogo_acumulado.append(texto)
                i += 1
        
        # No olvidemos el último personaje
        if personaje_actual:
            guardar_dialogo(guion, personaje_actual, dialogo_acumulado)
        
        return guion
    
    except Exception as e:
        print(f"Error al leer el guion: {e}")
        return []


def guardar_dialogo(guion, personaje, dialogo_acumulado):
    """
    Guarda el diálogo ajustado de un personaje en la lista de guion.
    Ahora permite diálogos vacíos.
    """
    # Incluso si no hay diálogo, guardamos la entrada
    texto_completo = " ".join(dialogo_acumulado) if dialogo_acumulado else ""
    dialogo_ajustado = ajustar_dialogo(texto_completo)
    guion.append({
        'IN': '00:00:00:00',
        'OUT': '00:00:00:00',
        'PERSONAJE': personaje,
        'DIÁLOGO': dialogo_ajustado
    })

