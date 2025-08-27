# stylesheet.py

def load_stylesheet():
    """Carga y devuelve la hoja de estilos QSS sin previsualización."""
    # Paleta y fuentes sin cambios, solo se elimina el estilo del previewPanel
    return """
        QWidget {
            background-color: #282C34;
            color: #EAEAEA;
            font-family: "Segoe UI", "Cantarell", "Helvetica Neue", sans-serif;
            font-size: 10pt;
        }

        QLabel#sectionHeader {
            font-size: 11pt;
            font-weight: bold;
            color: #ABB2BF;
            padding-top: 15px;
            padding-bottom: 5px;
            margin-bottom: 8px;
        }

        QFrame#sectionFrame {
            background-color: transparent; /* Mantenido transparente */
            border: none;
            border-radius: 0px;
        }

        QListWidget {
            background-color: #2C313A;
            border: 1px solid #444B58;
            border-radius: 5px;
            padding: 5px;
            font-size: 9.5pt;
            outline: 0px;
        }
        QListWidget::item {
            color: #ABB2BF;
            padding: 5px 3px;
            border-radius: 3px;
        }
        QListWidget::item:selected {
            background-color: #E06C75;
            color: #FFFFFF;
        }
        QListWidget::item:hover:!selected {
            background-color: #3E4451;
            color: #EAEAEA;
        }
        QListWidget:disabled {
             background-color: #2A2E36;
             border-color: #3A4048;
        }
        QListWidget::item:disabled {
             color: #6A737D;
        }

        QLineEdit {
            background-color: #2C313A;
            border: 1px solid #444B58;
            border-radius: 5px;
            padding: 8px 10px;
            color: #EAEAEA;
            font-size: 10pt;
        }
        QLineEdit:focus {
            border: 1px solid #E06C75;
            background-color: #30353E;
        }
        QLineEdit:read-only {
            background-color: #2C313A;
            color: #ABB2BF;
            border: 1px solid #444B58;
        }
        QLineEdit:disabled {
            background-color: #2A2E36;
            color: #6A737D;
            border-color: #3A4048;
        }

        QFormLayout QLabel {
             background-color: transparent;
             color: #D0D0D0;
             font-size: 9.5pt;
             font-weight: normal;
             padding-top: 8px;
             padding-right: 5px;
             border: none;
             margin: 0px;
        }

        QPushButton {
            background-color: #4B5263; color: #EAEAEA; border: none;
            border-radius: 5px; padding: 8px 15px; min-height: 28px; min-width: 80px;
        }
        QPushButton:hover { background-color: #5C6370; }
        QPushButton:pressed { background-color: #404652; }
        QPushButton:disabled { background-color: #3A3F4B; color: #6A737D; }

        QPushButton#convertButton {
            font-size: 11pt; font-weight: bold; color: #FFFFFF;
            background-color: #E06C75; padding: 10px 25px; min-height: 35px;
        }
        QPushButton#convertButton:hover { background-color: #F07C85; }
        QPushButton#convertButton:pressed { background-color: #D05C65; }
        QPushButton#convertButton:disabled { background-color: #555B66; color: #8A939D; }

        QPushButton#cancelButton {
             background-color: #888B92; padding: 8px 15px; min-height: 28px;
        }
        QPushButton#cancelButton:hover { background-color: #989ba2; }
        QPushButton#cancelButton:pressed { background-color: #70737A; }

        QProgressBar {
            border: none; border-radius: 6px; background-color: #353B45;
            height: 8px; text-align: center; color: transparent;
        }
        QProgressBar::chunk { background-color: #E06C75; border-radius: 6px; }
        QProgressBar:disabled { background-color: #30353E; }
        QProgressBar::chunk:disabled { background-color: #4B5263; }

        QLabel#statusLabel {
            color: #ABB2BF; font-size: 9pt; padding-top: 5px; padding-bottom: 5px;
            min-height: 2.5em;
        }

        QFrame[frameShape="4"] {
             border-top: 1px solid #444B58; margin-top: 10px; margin-bottom: 10px;
        }

        /* --- ESTILO PARA QTextEdit#previewPanel ELIMINADO --- */

    """