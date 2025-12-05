# utils.py
# Funciones de utilidad

import datetime
import locale

def format_timecode(time_obj):
    """
    Convierte un objeto de tiempo (o string) HH:MM:SS:FF a HH MM SS FF.
    Reemplaza los dos puntos por espacios.
    """
    if time_obj is None:
        return "00 00 00 00"
    
    time_str = str(time_obj).strip()
    # Reemplazar dos puntos por espacios
    return time_str.replace(':', ' ')

def get_formatted_date():
    """
    Obtiene la fecha actual formateada en español (ej. 21 octubre 2025).
    Intenta configurar el locale a español.
    """
    try:
        # Intentar configurar locale a español para el nombre del mes
        # Windows: 'Spanish_Spain', Linux/Mac: 'es_ES.UTF-8'
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, 'Spanish_Spain')
            except locale.Error:
                # Fallback genérico si no encuentra el locale específico
                pass
        
        now = datetime.datetime.now()
        # %d día, %B nombre mes completo, %Y año
        date_str = now.strftime("%d %B %Y")
        
        # Eliminar el 0 inicial del día si lo hay (opcional, pero estético: 05 -> 5)
        if date_str.startswith('0'):
            date_str = date_str[1:]
            
        return date_str.lower() # mes en minúscula como en tu ejemplo
        
    except Exception:
        # Fallback si todo falla
        return datetime.datetime.now().strftime("%d/%m/%Y")