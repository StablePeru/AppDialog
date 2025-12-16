import sys
import os

# Add project root to path
sys.path.append(r"c:\Users\PeruDelHoyoSanchez\Desktop\Programazioa\MIXER\TAKEO\TakeoAPP")

print("Attempting to import ThemeManager...")
try:
    from guion_editor.utils.theme_manager import theme_manager
    print("ThemeManager imported successfully.")
    print(f"Colors keys: {list(theme_manager.get_theme_dictionary().keys())[:5]}")
except Exception as e:
    print(f"Failed to import ThemeManager: {e}")
    import traceback
    traceback.print_exc()

print("Done.")
