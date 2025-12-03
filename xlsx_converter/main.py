import sys
import os
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QMessageBox, QRadioButton, 
    QGroupBox, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPalette, QColor

# --- ESTILOS CSS INTEGRADOS ---
STYLESHEET = """
    QWidget {
        font-family: "Segoe UI", sans-serif;
        font-size: 10pt;
    }
    
    QGroupBox {
        font-weight: bold;
        border: 1px solid #4a4a4a;
        border-radius: 6px;
        margin-top: 10px; /* Deja espacio para el título */
        padding-top: 15px;
        padding-bottom: 10px;
        padding-left: 10px;
        padding-right: 10px;
        background-color: #2b2b2b;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        left: 10px;
        color: #d0d0d0;
    }

    QLineEdit {
        background-color: #1e1e1e;
        color: #f0f0f0;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 6px;
        selection-background-color: #0078d7;
    }
    QLineEdit:focus {
        border: 1px solid #0078d7;
    }

    /* Botón Secundario (Examinar) */
    QPushButton {
        background-color: #3c3c3c;
        color: #e0e0e0;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 6px 12px;
    }
    QPushButton:hover {
        background-color: #4a4a4a;
        border-color: #666;
    }
    QPushButton:pressed {
        background-color: #2a2a2a;
    }

    /* Botón Principal (Convertir) */
    QPushButton#ActionButton {
        background-color: #0078d7; /* Azul Windows */
        color: white;
        font-weight: bold;
        border: 1px solid #0063b1;
        font-size: 11pt;
        padding: 8px;
    }
    QPushButton#ActionButton:hover {
        background-color: #1084e3;
    }
    QPushButton#ActionButton:pressed {
        background-color: #005a9e;
    }
    QPushButton#ActionButton:disabled {
        background-color: #444;
        color: #888;
        border-color: #444;
    }

    QRadioButton {
        spacing: 8px;
        color: #e0e0e0;
    }
    QRadioButton::indicator {
        width: 14px;
        height: 14px;
    }

    QProgressBar {
        border: 1px solid #444;
        border-radius: 4px;
        text-align: center;
        background-color: #1e1e1e;
    }
    QProgressBar::chunk {
        background-color: #0078d7;
        width: 10px;
    }
"""

class ExcelToTxtConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Conversor Excel a TXT")
        self.setGeometry(300, 300, 550, 300)
        
        # Intentar cargar icono si existe (ruta relativa ajustada a tu estructura)
        try:
            # Asumiendo que xlsx_converter está al mismo nivel que guion_editor
            icon_path = os.path.join(os.path.dirname(__file__), '..', 'guion_editor', 'styles', 'icons', 'convert_icon.svg')
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except:
            pass

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # --- Selección de Archivo ---
        file_group = QGroupBox("Archivo de Origen")
        file_layout = QVBoxLayout()
        
        input_layout = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Selecciona el archivo Excel (.xlsx)...")
        self.browse_btn = QPushButton("Examinar...")
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.clicked.connect(self.browse_file)
        
        input_layout.addWidget(self.file_path_input)
        input_layout.addWidget(self.browse_btn)
        file_layout.addLayout(input_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # --- Selección de Columna ---
        options_group = QGroupBox("Opciones de Conversión")
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(10, 15, 10, 10)
        
        self.lbl_columna = QLabel("Columna a exportar:")
        self.lbl_columna.setStyleSheet("color: #cccccc;")
        self.radio_dialogo = QRadioButton("DIÁLOGO")
        self.radio_dialogo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.radio_euskera = QRadioButton("EUSKERA")
        self.radio_euskera.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.radio_dialogo.setChecked(True) # Por defecto
        
        options_layout.addWidget(self.lbl_columna)
        options_layout.addSpacing(15)
        options_layout.addWidget(self.radio_dialogo)
        options_layout.addWidget(self.radio_euskera)
        options_layout.addStretch()
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # --- Barra de Progreso ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8) # Barra fina
        layout.addWidget(self.progress_bar)

        # --- Botón de Acción ---
        self.convert_btn = QPushButton("Convertir a TXT")
        self.convert_btn.setObjectName("ActionButton") # ID para CSS
        self.convert_btn.setMinimumHeight(45)
        self.convert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.convert_btn.clicked.connect(self.convert_file)
        layout.addWidget(self.convert_btn)

        layout.addStretch()
        self.setLayout(layout)

    def browse_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Excel", "", "Excel Files (*.xlsx *.xls)"
        )
        if filename:
            self.file_path_input.setText(filename)

    def convert_file(self):
        excel_path = self.file_path_input.text()
        if not excel_path or not os.path.exists(excel_path):
            QMessageBox.warning(self, "Error", "Por favor, selecciona un archivo Excel válido.")
            return

        target_column = "EUSKERA" if self.radio_euskera.isChecked() else "DIÁLOGO"
        
        folder = os.path.dirname(excel_path)
        base_name = os.path.splitext(os.path.basename(excel_path))[0]
        suffix = "_EUS" if target_column == "EUSKERA" else "_ESP"
        output_path = os.path.join(folder, f"{base_name}{suffix}.txt")

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.convert_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            df = pd.read_excel(excel_path)
            
            # Normalizar columnas
            df.columns = df.columns.astype(str).str.strip().str.upper()

            if "PERSONAJE" not in df.columns:
                 raise ValueError("No se encontró la columna 'PERSONAJE' en el Excel.")
            
            # Búsqueda difusa de la columna objetivo
            real_target_col = None
            if target_column in df.columns:
                real_target_col = target_column
            else:
                # Intentar buscar variaciones (ej: DIALOGO vs DIÁLOGO)
                for col in df.columns:
                    # Comprobación simple eliminando acentos visualmente para matching
                    norm_col = col.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
                    norm_target = target_column.replace("Á", "A") # etc
                    if norm_target in norm_col:
                        real_target_col = col
                        break
            
            if not real_target_col:
                 raise ValueError(f"No se encontró la columna '{target_column}' en el Excel.")

            content_lines = []
            
            for index, row in df.iterrows():
                personaje = str(row["PERSONAJE"]).strip()
                texto = str(row[real_target_col]).strip()
                
                if not personaje or personaje.lower() == 'nan': continue
                if not texto or texto.lower() == 'nan': continue
                
                content_lines.append(f"{personaje}\n{texto}\n")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(content_lines))

            self.progress_bar.setVisible(False)
            self.convert_btn.setEnabled(True)
            QMessageBox.information(
                self, 
                "Éxito", 
                f"Conversión completada.\n\nColumna usada: {real_target_col}\nArchivo guardado en:\n{output_path}"
            )

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.convert_btn.setEnabled(True)
            QMessageBox.critical(self, "Error de Conversión", f"Ocurrió un error:\n{str(e)}")

def main():
    app = QApplication(sys.argv)
    
    # 1. Configurar Estilo Fusión (Base)
    app.setStyle("Fusion")
    
    # 2. Configurar Paleta Oscura (Fondo general)
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(43, 43, 43))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(43, 43, 43))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(43, 43, 43))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(dark_palette)

    # 3. Aplicar Hoja de Estilos Personalizada (Detalles finos)
    app.setStyleSheet(STYLESHEET)
    
    window = ExcelToTxtConverter()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()