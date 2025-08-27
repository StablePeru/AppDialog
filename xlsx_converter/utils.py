# utils.py
# Funciones de utilidad

import datetime
import locale

def format_timecode(time_obj):
    """
    Convierte un objeto de tiempo (o string) HH:MM:SS:FF a HH MM SS FF.
    Maneja posibles errores de formato o tipos None.
    """
    if time_obj is None: return "00 00 00 00"
    time_str = str(time_obj).strip()
    try:
        # Intenta reemplazar separadores comunes y dividir
        parts = time_str.replace(':', ' ').replace('.', ' ').replace(',', ' ').split()
        if len(parts) == 4:
            # Asegura que cada parte tenga 2 dígitos
            formatted_parts = [part.zfill(2) for part in parts]
            # Validar que sean números de 2 dígitos (básico)
            for part in formatted_parts:
                if not part.isdigit() or len(part) > 2:
                    raise ValueError("Part is not a valid 2-digit number")
            return " ".join(formatted_parts)
        elif len(parts) == 3: # Asume HH MM SS, añade FF=00
             formatted_parts = [part.zfill(2) for part in parts]
             for part in formatted_parts:
                 if not part.isdigit() or len(part) > 2:
                     raise ValueError("Part is not a valid 2-digit number")
             return f"{formatted_parts[0]} {formatted_parts[1]} {formatted_parts[2]} 00"
        else:
            print(f"Warning: Unexpected time format parts: {parts} from '{time_str}'. Using default.")
            return "00 00 00 00"
    except Exception as e:
        print(f"Error parsing time '{time_str}': {e}. Using default.")
        return "00 00 00 00"

def get_formatted_date():
    """
    Obtiene la fecha actual formateada en español si es posible.
    """
    try:
        # Intenta establecer la localización a español
        try: locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except locale.Error:
            try: locale.setlocale(locale.LC_TIME, 'Spanish_Spain')
            except locale.Error:
                try: locale.setlocale(locale.LC_TIME, 'es_ES')
                except locale.Error: print("Warning: Locale español no configurado.")
        # Intenta formatear con nombre de mes
        try: fecha_hoy = datetime.datetime.now().strftime('%d %B %Y').capitalize()
        except ValueError:
            print("Warning: Formato fecha localizado falló. Usando numérico.")
            locale.setlocale(locale.LC_TIME, '') # Reset a default locale
            fecha_hoy = datetime.datetime.now().strftime('%d/%m/%Y')
    except Exception as e:
        print(f"Error formateando fecha: {e}. Usando formato ISO.")
        fecha_hoy = datetime.datetime.now().strftime('%Y-%m-%d')
    return fecha_hoy