# Takeo/main.py
import sys
from PyQt6.QtWidgets import QApplication
from takeo_mainwindow import TakeoMainWindow # Asegúrate que el nombre del archivo coincida

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Opcional: Aplicar un estilo global para un look más moderno
    # Comunes son "Fusion", "Windows", "WindowsVista" (en Windows), "macOS" (en macOS)
    app.setStyle("Fusion") 
    
    main_win = TakeoMainWindow()
    main_win.show() # Mover .show() aquí, después de que __init__ de TakeoMainWindow haya completado
    
    sys.exit(app.exec())