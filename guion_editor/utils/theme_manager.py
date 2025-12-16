import json
import os
from PyQt6.QtGui import QColor, QPalette, QGuiApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from guion_editor.utils.paths import get_user_config_dir

class ThemeManager(QObject):
    _instance = None
    themeChanged = pyqtSignal()

    DEFAULT_THEME = {
        # Meta
        "name": "Default Dark",

        # UI Basics
        "ui_bg_primary": "#1e1e1e", 
        "ui_text_main": "#ffffff",
        "ui_bg_secondary": "#2d2d2d", # Panels, lighter backgrounds
        "ui_border": "#3d3d3d",

        # Main Window
        "main_window_bg": "#1e1e1e",
        "main_window_text": "#ffffff",

        # Menus
        "menu_bg": "#2d2d2d",
        "menu_text": "#ffffff",
        "menu_selected_bg": "#0078d4", # Standard Windows 10/11 highlight blue
        "menu_selected_text": "#ffffff",
        
        # Table / Grid
        "table_grid_line": "#404040", 
        
        # Video Player
        "video_player_bg": "#000000",
        "video_player_timeline": "#555555",
        "video_player_handle": "#ffffff",
        
        # Editor / Cursor
        "cursor_highlight": "#303030", 
        
        # Table Validations (From PandasTableModel)
        "table_valid_time_bg": "transparent",
        "table_invalid_time_bg": "#8b0000",        # QColor(139, 0, 0)
        "table_bookmark_bg": "rgba(221, 211, 237, 40)", # QColor(221, 211, 237, 40)
        "table_line_error_bg": "rgba(255, 165, 0, 60)", # QColor(255, 165, 0, 60)

         # Toast
        "toast_bg": "#333333",
        "toast_text": "#ffffff",
        "toast_border": "#555555"
    }

    def __init__(self):
        super().__init__()
        # Avoid re-initialization
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._current_theme = self.DEFAULT_THEME.copy()
        self._current_mode = "dark" # "auto", "dark", "light", "custom"
        self._current_preset = None # Filename if loaded from preset
        self._initialized = True
        
        # Load persisted config
        self.load_preference()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def load_preference(self):
        """Loads user preference for mode/preset from config file."""
        config_path = get_user_config_dir() / "theme_config.json"
        
        # Default state
        desired_mode = "dark" 
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    desired_mode = data.get("mode", "dark")
                    self._current_preset = data.get("preset", None)
            except Exception as e:
                print(f"[ThemeManager] Error loading config: {e}")
        
        self.set_preference_mode(desired_mode, save=False)

    def save_preference(self):
        """Saves current mode and preset to config file."""
        config_path = get_user_config_dir() / "theme_config.json"
        data = {
            "mode": self._current_mode,
            "preset": self._current_preset
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[ThemeManager] Error saving config: {e}")

    def set_preference_mode(self, mode: str, save: bool = True):
        """
        Sets the application mode (auto, dark, light).
        Applies a default preset if needed.
        """
        valid_modes = ["auto", "dark", "light", "custom"]
        if mode not in valid_modes:
            mode = "dark"
            
        self._current_mode = mode
        
        if save:
            self.save_preference()
        
        self.apply_mode()

    def apply_mode(self):
        """Decides which theme to load based on current mode."""
        themes_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "themes")
        target_preset = None
        
        if self._current_mode == "auto":
             # Simple system detection via QPalette (approximate but cross-platform safe)
             # QGuiApplication.styleHints().colorScheme() is Qt 6.5+, falling back to palette
             app = QGuiApplication.instance()
             is_dark = True # Default fallback
             if app:
                 # Check standard palette window color lightness
                 window_color = app.palette().color(QPalette.ColorRole.Window)
                 if window_color.lightness() > 128:
                     is_dark = False
             
             target_preset = "dark_studio.json" if is_dark else "light_paper.json"

        elif self._current_mode == "dark":
            target_preset = "dark_studio.json"
        elif self._current_mode == "light":
            target_preset = "light_paper.json"
        elif self._current_mode == "custom":
            # Keep current or load last used preset if stored? 
            # For now, do nothing if already custom, or reload preset if variable set
            if self._current_preset:
                target_preset = self._current_preset

        if target_preset:
            full_path = os.path.join(themes_dir, target_preset)
            if os.path.exists(full_path):
                self.load_theme_from_json(full_path)
            else:
                 print(f"[ThemeManager] Preset not found: {full_path}")

    def get_color(self, key: str) -> QColor:
        """
        Returns a QColor object for the given semantic key.
        If key not found, returns magenta to make error obvious.
        """
        color_val = self._current_theme.get(key, "#ff00ff")
        
        if color_val == "transparent":
            return QColor(0, 0, 0, 0)
            
        c = QColor(color_val)
        if not c.isValid():
            print(f"[ThemeManager] WARNING: Invalid color value '{color_val}' for key '{key}'")
            return QColor(255, 0, 255) # Magenta for error
        return c

    def get_color_str(self, key: str) -> str:
        """Returns the string representation (hex or rgba) of the color."""
        return self._current_theme.get(key, "#ff00ff")

    def load_theme_from_json(self, json_path: str):
        """Loads a theme from a JSON file and applies it."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                theme_data = json.load(f)
            
            # Allow flat structure or {"colors": {...}}
            colors = theme_data.get("colors", theme_data)
            
            # Update current theme with new values (merge to keep defaults if missing)
            self._current_theme.update(colors)
            
            # Store filename as current preset (if it is one of ours or external)
            filename = os.path.basename(json_path)
            self._current_preset = filename
            
            # If manually loading, we might consider switching mode to "custom" implicitly?
            # Or keep it as is. For now let's just emit.
            
            self.themeChanged.emit()
            print(f"[ThemeManager] Loaded theme from {json_path}")
            return True
        except Exception as e:
            print(f"[ThemeManager] Error loading theme from {json_path}: {e}")
            return False

    def get_theme_dictionary(self):
        """Returns a copy of the current theme dictionary."""
        return self._current_theme.copy()

    def update_color(self, key: str, color_str: str):
        """Updates a specific color key and emits change signal."""
        self._current_theme[key] = color_str
        self.themeChanged.emit()

    def save_theme_to_json(self, path: str):
        """Exports content to JSON."""
        try:
            data = {"colors": self._current_theme}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"[ThemeManager] Theme saved to {path}")
            return True
        except Exception as e:
            print(f"[ThemeManager] Error saving theme: {e}")
            return False

    def get_stylesheet_template(self) -> str:
        """
        Returns a dynamic variable-based stylesheet for the application.
        Using f-strings for efficiency over regex replacement.
        """
        # Extract colors for shorter f-string usage
        bg_primary = self.get_color_str("ui_bg_primary")
        text_main = self.get_color_str("ui_text_main")
        bg_secondary = self.get_color_str("ui_bg_secondary")
        border = self.get_color_str("ui_border")
        
        menu_bg = self.get_color_str("menu_bg")
        menu_text = self.get_color_str("menu_text")
        menu_sel_bg = self.get_color_str("menu_selected_bg")
        menu_sel_text = self.get_color_str("menu_selected_text")

        toast_bg = self.get_color_str("toast_bg")
        toast_text = self.get_color_str("toast_text")
        toast_border = self.get_color_str("toast_border")

        return f"""
        QMainWindow {{
            background-color: {bg_primary};
            color: {text_main};
        }}
        QWidget {{
            background-color: {bg_primary};
            color: {text_main};
        }}
        
        /* Menus */
        QMenuBar {{
            background-color: {menu_bg};
            color: {menu_text};
        }}
        QMenuBar::item:selected {{
            background-color: {menu_sel_bg};
            color: {menu_sel_text};
        }}
        QMenu {{
            background-color: {menu_bg};
            color: {menu_text};
            border: 1px solid {border};
        }}
        QMenu::item:selected {{
            background-color: {menu_sel_bg};
            color: {menu_sel_text};
        }}

        /* Table / Grid specifics could go here if checking QTableView */
        QTableView {{
            background-color: {bg_secondary};
            gridline-color: {self.get_color_str("table_grid_line")};
            color: {text_main};
        }}
        QHeaderView::section {{
            background-color: {bg_secondary};
            color: {text_main};
            border: 1px solid {border};
        }}

        /* Toast Widget specifics if accessible via object name or class */
        #toast_widget_container {{
             background-color: {toast_bg};
             color: {toast_text};
             border: 1px solid {toast_border};
             border-radius: 5px;
        }}
        """

# Global instance
theme_manager = ThemeManager.instance()
