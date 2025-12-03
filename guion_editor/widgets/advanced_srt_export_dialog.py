# guion_editor/widgets/advanced_srt_export_dialog.py
import pandas as pd
from collections import Counter
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QPushButton, QComboBox, QTextEdit, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout, QDialogButtonBox, QWidget
)
from PyQt6.QtCore import Qt
from guion_editor import constants as C
from guion_editor.utils.srt_processor import SRTProcessor

# --- ESTILOS CSS PARA CORREGIR LA VISUALIZACIÓN ---
DIALOG_STYLESHEET = """
    QGroupBox {
        font-weight: bold;
        border: 1px solid #555;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        left: 10px;
    }
    QLabel {
        color: #e0e0e0;
    }
    /* Estilos para Inputs numéricos y combos */
    QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #333333;
        color: #ffffff;
        border: 1px solid #555555;
        padding: 4px;
        border-radius: 4px;
        selection-background-color: #0078d7;
    }
    QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
        border: 1px solid #0078d7;
    }
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
        background-color: #444;
        width: 16px;
        border-radius: 2px;
    }
    QTextEdit {
        background-color: #1e1e1e;
        color: #d4d4d4;
        border: 1px solid #444;
        font-family: Consolas, "Courier New", monospace;
    }
    /* Botones */
    QPushButton {
        background-color: #0078d7;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
    }
    QPushButton:hover {
        background-color: #005a9e;
    }
    QPushButton:disabled {
        background-color: #444;
        color: #888;
    }
"""

class AdvancedSrtExportDialog(QDialog):
    # Códigos de color definidos en tu programa original
    COLOR_OPTIONS = [
        ("<AN1>", "Amarillo"),
        ("<CN1>", "Cyan"),
        ("<MN1>", "Magenta"),
        ("<VN1>", "Verde")
    ]

    def __init__(self, table_window, get_icon_func=None, parent=None):
        super().__init__(parent)
        self.table_window = table_window
        self.get_icon = get_icon_func
        self.setWindowTitle("Exportar SRT Avanzado")
        self.setMinimumSize(850, 750) # Un poco más alto para los colores
        
        # Aplicar estilos
        self.setStyleSheet(DIALOG_STYLESHEET)
        
        self.config = SRTProcessor.DEFAULT_CONFIG.copy()
        
        # Diccionario para guardar referencias a los combos de color { "<AN1>": QComboBox, ... }
        self.color_combos = {} 
        
        self.setup_ui()
        self._auto_assign_colors() # Lógica de ranking automático
        self.update_preview()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- SECCIÓN SUPERIOR: DATOS Y COLORES (Horizontal) ---
        top_layout = QHBoxLayout()
        
        # 1. Configuración de Fuente de Datos (Izquierda)
        source_group = QGroupBox("Origen de Datos")
        source_layout = QFormLayout(source_group)
        
        self.column_combo = QComboBox()
        self.column_combo.addItems([C.COL_DIALOGO, C.COL_EUSKERA])
        self.column_combo.currentIndexChanged.connect(self._on_source_changed)
        source_layout.addRow("Columna de Texto:", self.column_combo)
        
        top_layout.addWidget(source_group, 1)

        # 2. Configuración de Colores (Derecha)
        colors_group = QGroupBox("Asignación de Colores por Personaje")
        colors_layout = QFormLayout(colors_group)
        
        all_characters = [""] + self.table_window.get_character_names_from_model()
        
        for code, label in self.COLOR_OPTIONS:
            combo = QComboBox()
            combo.setEditable(True) # Permitir escribir para filtrar si hay muchos
            combo.addItems(all_characters)
            combo.currentTextChanged.connect(self.update_preview) # Actualizar preview al cambiar color
            colors_layout.addRow(f"{label} ({code}):", combo)
            self.color_combos[code] = combo
            
        top_layout.addWidget(colors_group, 2) # Más peso visual a los colores
        layout.addLayout(top_layout)

        # --- SECCIÓN MEDIA: PARÁMETROS TÉCNICOS ---
        config_group = QGroupBox("Parámetros Técnicos SRT")
        config_layout = QHBoxLayout(config_group) # Usamos HBox para aprovechar el ancho
        
        # Columna 1
        col1 = QVBoxLayout()
        row_fps = QHBoxLayout(); row_fps.addWidget(QLabel("FPS:")); 
        self.fps_spin = QSpinBox(); self.fps_spin.setRange(1, 120); self.fps_spin.setValue(self.config["FPS"])
        row_fps.addWidget(self.fps_spin); col1.addLayout(row_fps)
        
        row_chars = QHBoxLayout(); row_chars.addWidget(QLabel("Caract/Línea:"));
        self.max_chars_spin = QSpinBox(); self.max_chars_spin.setRange(10, 100); self.max_chars_spin.setValue(self.config["MAX_CHARS_PER_LINE"])
        row_chars.addWidget(self.max_chars_spin); col1.addLayout(row_chars)
        
        # Columna 2
        col2 = QVBoxLayout()
        row_lines = QHBoxLayout(); row_lines.addWidget(QLabel("Líneas/Sub:"));
        self.max_lines_spin = QSpinBox(); self.max_lines_spin.setRange(1, 4); self.max_lines_spin.setValue(self.config["MAX_LINES_PER_SUB"])
        row_lines.addWidget(self.max_lines_spin); col2.addLayout(row_lines)
        
        row_sgap = QHBoxLayout(); row_sgap.addWidget(QLabel("Gap Frases (s):"));
        self.sentence_gap_spin = QDoubleSpinBox(); self.sentence_gap_spin.setRange(0.0, 5.0); self.sentence_gap_spin.setSingleStep(0.1); self.sentence_gap_spin.setValue(self.config["SENTENCE_GAP_S"])
        row_sgap.addWidget(self.sentence_gap_spin); col2.addLayout(row_sgap)

        # Columna 3
        col3 = QVBoxLayout()
        row_fgap = QHBoxLayout(); row_fgap.addWidget(QLabel("Gap Seguridad (s):"));
        self.fixed_gap_spin = QDoubleSpinBox(); self.fixed_gap_spin.setRange(0.0, 1.0); self.fixed_gap_spin.setSingleStep(0.01); self.fixed_gap_spin.setValue(self.config["FIXED_GAP_S"])
        row_fgap.addWidget(self.fixed_gap_spin); col3.addLayout(row_fgap)
        
        # Botón reset
        self.reset_btn = QPushButton("Valores por Defecto")
        self.reset_btn.clicked.connect(self._reset_values)
        col3.addWidget(self.reset_btn)

        config_layout.addLayout(col1)
        config_layout.addLayout(col2)
        config_layout.addLayout(col3)
        layout.addWidget(config_group)

        # Conexiones de actualización
        for widget in [self.fps_spin, self.max_chars_spin, self.max_lines_spin, 
                       self.sentence_gap_spin, self.fixed_gap_spin]:
            if hasattr(widget, 'valueChanged'): widget.valueChanged.connect(self.update_preview)

        # --- SECCIÓN INFERIOR: PREVIEW ---
        preview_group = QGroupBox("Previsualización (Primeros 15 subtítulos)")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_text)
        layout.addWidget(preview_group)

        # --- BOTONES DE ACCIÓN ---
        button_box = QHBoxLayout()
        button_box.addStretch()
        
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("background-color: #444;") # Estilo diferente para cancelar
        
        self.export_btn = QPushButton(" Exportar SRT...")
        if self.get_icon: self.export_btn.setIcon(self.get_icon("export_srt_icon.svg"))
        self.export_btn.clicked.connect(self.export_srt)
        self.export_btn.setMinimumHeight(40) # Botón grande e importante
        self.export_btn.setMinimumWidth(150)
        
        button_box.addWidget(self.cancel_btn)
        button_box.addWidget(self.export_btn)
        layout.addLayout(button_box)

    def _reset_values(self):
        """Restablece los valores numéricos a los defaults."""
        self.fps_spin.setValue(SRTProcessor.DEFAULT_CONFIG["FPS"])
        self.max_chars_spin.setValue(SRTProcessor.DEFAULT_CONFIG["MAX_CHARS_PER_LINE"])
        self.max_lines_spin.setValue(SRTProcessor.DEFAULT_CONFIG["MAX_LINES_PER_SUB"])
        self.sentence_gap_spin.setValue(SRTProcessor.DEFAULT_CONFIG.get("SENTENCE_GAP_S", 0.4))
        self.fixed_gap_spin.setValue(SRTProcessor.DEFAULT_CONFIG["FIXED_GAP_S"])

    def _on_source_changed(self):
        """Cuando cambia la columna de origen, re-calculamos el ranking de personajes."""
        self._auto_assign_colors()
        self.update_preview()

    def _auto_assign_colors(self):
        """
        Analiza el DataFrame, cuenta intervenciones por personaje y asigna
        los 4 más habladores a los 4 colores disponibles automáticamente.
        """
        df = self.table_window.pandas_model.dataframe()
        if df.empty or C.COL_PERSONAJE not in df.columns: return

        target_col = self.column_combo.currentText()
        if target_col not in df.columns: return

        # Filtrar solo filas con texto en la columna objetivo
        valid_df = df[df[target_col].astype(str).str.strip() != ""]
        
        # Contar intervenciones por personaje
        char_counts = Counter(valid_df[C.COL_PERSONAJE].dropna().astype(str).str.strip())
        
        # Obtener los N personajes más comunes (donde N es num colores)
        top_characters = [char for char, count in char_counts.most_common(len(self.COLOR_OPTIONS))]
        
        # Asignar a los combos
        for i, (code, _) in enumerate(self.COLOR_OPTIONS):
            combo = self.color_combos[code]
            combo.blockSignals(True) # Evitar refrescar preview 4 veces seguidas
            if i < len(top_characters):
                # Buscar texto (case insensitive preferiblemente, pero exacto es más seguro aquí)
                index = combo.findText(top_characters[i])
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.setCurrentIndex(0) # Vacío
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

    def get_current_config(self):
        return {
            "FPS": self.fps_spin.value(),
            "MAX_CHARS_PER_LINE": self.max_chars_spin.value(),
            "MAX_LINES_PER_SUB": self.max_lines_spin.value(),
            "SENTENCE_GAP_S": self.sentence_gap_spin.value(),
            "FIXED_GAP_S": self.fixed_gap_spin.value(),
            "SMALL_GAP_S": 0.04, 
            "MAX_OVERLAP_S": 2.0 
        }

    def get_color_mapping(self):
        """Devuelve un diccionario { 'Personaje': '<AN1>', ... }"""
        mapping = {}
        for code, combo in self.color_combos.items():
            char_name = combo.currentText().strip()
            if char_name:
                mapping[char_name] = code
        return mapping

    def update_preview(self):
        df = self.table_window.pandas_model.dataframe()
        if df.empty:
            self.preview_text.setText("No hay datos en el guion.")
            return

        config = self.get_current_config()
        processor = SRTProcessor(config)
        
        col_mapping = {
            "IN": C.COL_IN,
            "OUT": C.COL_OUT,
            "PERSONAJE": C.COL_PERSONAJE,
            "DIALOGO": self.column_combo.currentText()
        }
        
        char_mapping = self.get_color_mapping()

        # Generar solo una muestra para la preview
        preview_df = df.head(20).copy() 
        try:
            srt_content = processor.generate_srt_string(preview_df, col_mapping, char_mapping)
            self.preview_text.setText(srt_content)
        except Exception as e:
            self.preview_text.setText(f"Error generando preview: {e}")

    def export_srt(self):
        default_filename = self.table_window._generate_default_filename("srt")
        path, _ = QFileDialog.getSaveFileName(self, "Guardar Archivo SRT", default_filename, "SubRip Subtitle (*.srt)")
        
        if path:
            try:
                df = self.table_window.pandas_model.dataframe()
                config = self.get_current_config()
                processor = SRTProcessor(config)
                
                col_mapping = {
                    "IN": C.COL_IN,
                    "OUT": C.COL_OUT,
                    "PERSONAJE": C.COL_PERSONAJE,
                    "DIALOGO": self.column_combo.currentText()
                }
                char_mapping = self.get_color_mapping()
                
                srt_content = processor.generate_srt_string(df, col_mapping, char_mapping)
                
                with open(path, "w", encoding="utf-8") as f:
                    f.write(srt_content)
                
                QMessageBox.information(self, "Exportación Exitosa", f"Archivo guardado en:\n{path}")
                self.accept()
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"No se pudo exportar el SRT:\n{e}")