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
    # main_win.show() # .show() ya está en TakeoMainWindow.__init__ al final.
    # Corrección: Es mejor llamar a .show() explícitamente después de la creación del objeto.
    # Aunque esté en init_ui, moverlo aquí es más estándar.
    # En este caso particular, ya está en `init_ui` llamado desde `__init__`,
    # y el `self.show()` está al final de `init_ui`. Así que no es estrictamente necesario aquí.
    # Lo dejaré como estaba en tu original, asumiendo que el `self.show()` en `init_ui` es intencional.
    # Sin embargo, la guía general es:
    # main_win = TakeoMainWindow()
    # main_win.show() # Esta línea aquí es lo más común.
    
    sys.exit(app.exec())