from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QWidget, QScrollArea, QFormLayout, 
    QPushButton, QHBoxLayout, QColorDialog, QLabel, QFileDialog,
    QGroupBox, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import os
from guion_editor.utils.theme_manager import theme_manager

class ThemeEditorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Theme Editor")
        self.resize(500, 700)
        self.init_ui()
        
        # Subscribe to outside changes (e.g. if import happens elsewhere)
        theme_manager.themeChanged.connect(self.refresh_ui)

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)

        # --- 0. High Level Controls (Quick Actions) ---
        self.group_quick = QGroupBox("Quick Settings")
        quick_layout = QFormLayout(self.group_quick)
        
        # Mode Selector
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["auto", "dark", "light"]) # "custom" implies manual edits
        # Set current
        current_mode = theme_manager._current_mode
        if current_mode in ["auto", "dark", "light"]:
             self.combo_mode.setCurrentText(current_mode)
        
        self.combo_mode.currentTextChanged.connect(self.on_mode_changed)
        quick_layout.addRow("Mode:", self.combo_mode)
        
        # Preset Selector
        self.combo_preset = QComboBox()
        self.refresh_presets_combo()
        self.combo_preset.currentTextChanged.connect(self.on_preset_selected)
        quick_layout.addRow("Preset:", self.combo_preset)
        
        self.main_layout.addWidget(self.group_quick)

        # --- 1. Colors List (Scroll Area) ---
        lbl_details = QLabel("Advanced Color Overrides:")
        lbl_details.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.main_layout.addWidget(lbl_details)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.form_layout = QFormLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        
        self.main_layout.addWidget(self.scroll_area)

        # 2. Populate Colors
        self.populate_inputs()

        # 3. Toolbar
        self.toolbar_layout = QHBoxLayout()
        
        btn_import = QPushButton("Import JSON...")
        btn_import.clicked.connect(self.import_theme)
        
        btn_export = QPushButton("Export JSON...")
        btn_export.clicked.connect(self.export_theme)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)

        self.toolbar_layout.addWidget(btn_import)
        self.toolbar_layout.addWidget(btn_export)
        self.toolbar_layout.addStretch()
        self.toolbar_layout.addWidget(btn_close)
        
        self.main_layout.addLayout(self.toolbar_layout)

    def refresh_presets_combo(self):
        self.combo_preset.blockSignals(True)
        self.combo_preset.clear()
        self.combo_preset.addItem("Select a preset...")
        
        themes_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "themes")
        if os.path.exists(themes_dir):
            files = [f for f in os.listdir(themes_dir) if f.endswith(".json")]
            self.combo_preset.addItems(sorted(files))
            
        self.combo_preset.blockSignals(False)

    def on_mode_changed(self, mode_text):
        if mode_text:
            theme_manager.set_preference_mode(mode_text)

    def on_preset_selected(self, preset_name):
        if not preset_name or preset_name == "Select a preset...":
            return
            
        themes_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "themes")
        full_path = os.path.join(themes_dir, preset_name)
        
        if os.path.exists(full_path):
             theme_manager.load_theme_from_json(full_path)
             # Note: Loading a specific preset might technically put us in "custom" mode relative to auto logic,
             # but user intent here is "apply this look". 
             # For now, we don't force 'custom' mode variable, but maybe we should if we want strict mode logic.
             # Ideally, "Preset" is just a helper.

    def populate_inputs(self):
        # Clear existing
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        theme_data = theme_manager.get_theme_dictionary()
        # Sort keys so it's not chaotic
        sorted_keys = sorted(theme_data.keys())

        self.color_buttons = {}

        for key in sorted_keys:
            val = theme_data[key]
            # If not color-like or semantic name, skip? No, show all for now.
            if key == "name" or key == "author":
                 # Metadata
                continue
            
            # Color button
            btn = QPushButton()
            btn.setFixedSize(60, 25)
            self.update_button_style(btn, val)
            btn.clicked.connect(lambda checked, k=key: self.pick_color(k))
            
            self.color_buttons[key] = btn
            self.form_layout.addRow(key, btn)

    def update_button_style(self, btn, color_str):
        btn.setStyleSheet(f"background-color: {color_str}; border: 1px solid #555;")
        btn.setText("") 

    def pick_color(self, key):
        current_color_str = theme_manager.get_color_str(key)
        
        # Handle "transparent" or weird values
        if current_color_str == "transparent":
            initial = QColor(0,0,0,0)
        else:
            initial = QColor(current_color_str)
            
        color = QColorDialog.getColor(initial, self, f"Pick color for {key}", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        
        if color.isValid():
            new_val = color.name(QColor.NameFormat.HexArgb) # returns #AARRGGBB or #RRGGBB
            theme_manager.update_color(key, new_val)
            # Switch to 'custom' mode if user edits manually?
            # theme_manager._current_mode = "custom" 
            # (If we want to be strict about modes)

    def refresh_ui(self):
        # Optimization: Update existing buttons instead of full rebuild
        theme_data = theme_manager.get_theme_dictionary()
        for key, btn in self.color_buttons.items():
            if key in theme_data:
                self.update_button_style(btn, theme_data[key])
        
        # Also update combo boxes if they drifted?
        # If theme changed externally (e.g. auto mode switch), we might want to update mode combo.
        self.combo_mode.blockSignals(True)
        if theme_manager._current_mode in ["auto", "dark", "light"]:
             self.combo_mode.setCurrentText(theme_manager._current_mode)
        self.combo_mode.blockSignals(False)

    def import_theme(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Theme", "", "JSON Files (*.json)")
        if path:
            theme_manager.load_theme_from_json(path)

    def export_theme(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Theme", "custom_theme.json", "JSON Files (*.json)")
        if path:
            theme_manager.save_theme_to_json(path)
