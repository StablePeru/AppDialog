# main.py
# Punto de entrada principal de la aplicación

import sys
from PySide6.QtWidgets import QApplication

# Importar componentes necesarios
from main_window import MainWindow
from stylesheet import load_stylesheet

def main():
    """Función principal para lanzar la aplicación."""
    app = QApplication(sys.argv)

    # Cargar y aplicar la hoja de estilos global
    style_sheet = load_stylesheet()
    app.setStyleSheet(style_sheet)

    # Crear y mostrar la ventana principal
    window = MainWindow()
    window.show()

    # Ejecutar el bucle de eventos de la aplicación
    sys.exit(app.exec())

if __name__ == '__main__':
    main()