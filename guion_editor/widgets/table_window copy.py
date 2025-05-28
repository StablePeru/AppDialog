import json
import os

# Módulos de PyQt5 para la creación de la interfaz y manejo de eventos
from PyQt5.QtCore import pyqtSignal, QObject, QEvent, Qt
from PyQt5.QtGui import QFont, QKeySequence, QColor, QIntValidator
from PyQt5.QtWidgets import (
    QWidget, QTableWidgetItem, QTextEdit, QFileDialog, QAbstractItemView,
    QMessageBox, QVBoxLayout, QHBoxLayout, QPushButton, QShortcut, QCompleter,
    QUndoStack, QUndoCommand, QLineEdit, QComboBox, QLabel, QFormLayout
)

# Módulos de terceros
import pandas as pd

# Delegados y utilidades específicas del proyecto
from guion_editor.delegates.custom_delegates import TimeCodeDelegate, CharacterDelegate
from guion_editor.utils.dialog_utils import leer_guion, ajustar_dialogo
from guion_editor.widgets.custom_table_widget import CustomTableWidget
from guion_editor.widgets.custom_text_edit import CustomTextEdit


class TableWindow(QWidget):
    """
    Ventana principal que permite la edición de guiones mediante una tabla interactiva.
    """

    # -----------------------------------------------------------------------------------
    # SEÑALES
    # -----------------------------------------------------------------------------------
    in_out_signal = pyqtSignal(str, int)
    character_name_changed = pyqtSignal()

    # -----------------------------------------------------------------------------------
    # CONSTANTES DE CLASE (Índices de columnas y mapeo)
    # -----------------------------------------------------------------------------------
    COL_ID = 0
    COL_SCENE = 1
    COL_IN = 2
    COL_OUT = 3
    COL_CHARACTER = 4
    COL_DIALOGUE = 5

    TABLE_TO_DF_COL_MAP = {
        COL_ID: 'ID',
        COL_SCENE: 'SCENE',
        COL_IN: 'IN',
        COL_OUT: 'OUT',
        COL_CHARACTER: 'PERSONAJE',
        COL_DIALOGUE: 'DIÁLOGO'
    }

    # -----------------------------------------------------------------------------------
    # CLASE INTERNA PARA FILTRAR TECLAS (F6)
    # -----------------------------------------------------------------------------------
    class KeyPressFilter(QObject):
        """
        Filtro de eventos para manejar teclas especiales (por ejemplo, F6).
        """
        def __init__(self, table_window):
            super().__init__()
            self.table_window = table_window

        def eventFilter(self, obj, event):
            """
            Intercepta eventos de teclado para manejar atajos específicos (F6).
            """
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_F6 and not event.isAutoRepeat():
                    self.table_window.video_player_widget.start_out_timer()
                    return True
            elif event.type() == QEvent.KeyRelease:
                if event.key() == Qt.Key_F6 and not event.isAutoRepeat():
                    self.table_window.video_player_widget.stop_out_timer()
                    return True
            return False

    # -----------------------------------------------------------------------------------
    # CONSTRUCTOR E INICIALIZACIÓN DE LA VENTANA
    # -----------------------------------------------------------------------------------
    def __init__(self, video_player_widget, main_window=None):
        """
        Inicializa la ventana de edición de guiones y configura sus componentes principales.
        """
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("Editor de Guion")
        self.setGeometry(100, 100, 800, 600)

        # ------------------------------
        # Reproductor de video y señales
        # ------------------------------
        self.video_player_widget = video_player_widget
        self.video_player_widget.in_out_signal.connect(self.update_in_out)
        self.video_player_widget.out_released.connect(self.select_next_row_and_set_in)

        # ------------------------------
        # Filtro para teclas especiales
        # ------------------------------
        self.key_filter = self.KeyPressFilter(self)
        self.installEventFilter(self.key_filter)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

        # --------------------------------
        # DataFrame y variables de estado
        # --------------------------------
        self.dataframe = pd.DataFrame(columns=self.TABLE_TO_DF_COL_MAP.values())
        self.unsaved_changes = False
        self.undo_stack = QUndoStack(self)
        self.has_scene_numbers = False
        self.current_script_name = None

        # --------------------------------
        # Atributos para la cabecera extra
        # --------------------------------
        self.reference_number = ""  # 6 dígitos
        self.product_name = ""
        self.chapter_number = ""
        self.selected_type = ""  # Ficcion, Animacion, Documental

        # -----------------------
        # Configurar la interfaz
        # -----------------------
        self.setup_ui()

        # -------------------------
        # Configurar atajos (shortcuts)
        # -------------------------
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self.undo_stack.undo)

        redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        redo_shortcut.activated.connect(self.undo_stack.redo)

        copy_in_out_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        copy_in_out_shortcut.activated.connect(self.copy_in_out_to_next)

    # -----------------------------------------------------------------------------------
    # MÉTODOS DE CONFIGURACIÓN DE LA INTERFAZ
    # -----------------------------------------------------------------------------------
    def setup_ui(self):
        """
        Configura los botones, los campos extra y la tabla principal de la interfaz de usuario.
        """
        layout = QVBoxLayout(self)

        # 1. Campos superiores (cabecera)
        self.setup_header_fields(layout)

        # 2. Botones de acción
        self.setup_buttons(layout)

        # 3. Tabla principal
        self.setup_table_widget(layout)

        # 4. Cargar hoja de estilo
        self.load_stylesheet()

    def setup_header_fields(self, layout):
        """
        Crea los inputs para los campos solicitados:
          - Número de referencia (6 dígitos)
          - Nombre del producto
          - Número de capítulo
          - Tipo (combobox: Ficcion, Animacion, Documental)
        """
        header_form = QFormLayout()

        # Número de referencia (sólo 6 dígitos)
        self.reference_edit = QLineEdit()
        validator_ref = QIntValidator(0, 999999, self)
        self.reference_edit.setValidator(validator_ref)
        self.reference_edit.setMaxLength(6)
        self.reference_edit.setPlaceholderText("Máximo 6 dígitos")
        header_form.addRow("Número de referencia:", self.reference_edit)

        # Nombre del producto
        self.product_edit = QLineEdit()
        self.product_edit.setPlaceholderText("Nombre del producto")
        header_form.addRow("Nombre del Producto:", self.product_edit)

        # Número de capítulo
        self.chapter_edit = QLineEdit()
        self.chapter_edit.setPlaceholderText("Número de capítulo")
        header_form.addRow("N.º Capítulo:", self.chapter_edit)

        # Tipo (Ficcion, Animacion, Documental)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Ficcion", "Animacion", "Documental"])
        header_form.addRow("Tipo:", self.type_combo)

        layout.addLayout(header_form)

    def setup_buttons(self, layout):
        """
        Crea y añade los botones de acción a la interfaz.
        """
        buttons_layout = QHBoxLayout()
        buttons = [
            ("Agregar Línea", self.add_new_row),
            ("Eliminar Fila", self.remove_row),
            ("Mover Arriba", self.move_row_up),
            ("Mover Abajo", self.move_row_down),
            ("Ajustar Diálogos", self.adjust_dialogs),
            ("Separar Intervención", self.split_intervention),
            ("Juntar Intervenciones", self.merge_interventions)
        ]
        for text, method in buttons:
            button = QPushButton(text)
            button.clicked.connect(method)
            buttons_layout.addWidget(button)
        layout.addLayout(buttons_layout)

    def setup_table_widget(self, layout):
        """
        Crea y configura la tabla principal de edición.
        """
        self.table_widget = CustomTableWidget()
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_widget.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        layout.addWidget(self.table_widget)

        # Definir las columnas de la tabla
        self.columns = ["ID", "SCENE", "IN", "OUT", "PERSONAJE", "DIÁLOGO"]
        self.table_widget.setColumnCount(len(self.columns))
        self.table_widget.setHorizontalHeaderLabels(self.columns)

        # Ocultar la columna ID
        self.table_widget.setColumnHidden(self.columns.index("ID"), True)

        # Delegados para formatear IN, OUT y PERSONAJE
        self.table_widget.setItemDelegateForColumn(self.COL_IN, TimeCodeDelegate(self.table_widget))
        self.table_widget.setItemDelegateForColumn(self.COL_OUT, TimeCodeDelegate(self.table_widget))
        self.table_widget.setItemDelegateForColumn(
            self.COL_CHARACTER,
            CharacterDelegate(get_names_callback=self.get_character_names, parent=self.table_widget)
        )

        # Señales personalizadas del CustomTableWidget
        self.table_widget.cellCtrlClicked.connect(self.handle_ctrl_click)
        self.table_widget.cellAltClicked.connect(self.handle_alt_click)
        self.table_widget.itemChanged.connect(self.on_item_changed)

    def load_stylesheet(self):
        """
        Carga el archivo de estilos CSS para aplicar a la tabla.
        """
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(current_dir, '..', 'styles', 'table_styles.css')
            with open(css_path, 'r') as f:
                self.table_widget.setStyleSheet(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error de Estilos", f"Error al cargar el stylesheet: {str(e)}")

    # -----------------------------------------------------------------------------------
    # MÉTODOS PARA ABRIR / IMPORTAR / GUARDAR ARCHIVOS
    # -----------------------------------------------------------------------------------
    def open_file_dialog(self):
        """
        Abre un cuadro de diálogo para seleccionar un archivo de guion y cargar sus datos.
        """
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Abrir guion", "", "Documentos de Word (*.docx)"
        )
        if file_name:
            self.load_data(file_name)
            # Agregar archivo a recientes
            if self.main_window:
                self.main_window.add_to_recent_files(file_name)

    def load_data(self, file_name):
        """
        Carga los datos del guion desde un archivo de Word.
        """
        try:
            guion_data = leer_guion(file_name)

            # Verificar si existe la columna SCENE
            if 'SCENE' not in guion_data[0]:
                self.has_scene_numbers = False
                for entry in guion_data:
                    entry['SCENE'] = 1
                print("Importación sin números de escena. Asignando '1' a todas las escenas.")
            else:
                scene_values = [entry['SCENE'] for entry in guion_data]
                unique_scenes = set(scene_values)
                if len(unique_scenes) > 1 or (len(unique_scenes) == 1 and unique_scenes.pop() != '1'):
                    self.has_scene_numbers = True
                    print("Importación con números de escena. Preservando escenas existentes.")
                else:
                    self.has_scene_numbers = False
                    for entry in guion_data:
                        entry['SCENE'] = 1
                    print("Importación sin números de escena (todos '1'). Asignando '1' a todas las escenas.")

            # Crear DataFrame
            self.dataframe = pd.DataFrame(guion_data)

            # Comprobar columnas requeridas (excepto ID)
            required_columns = [col for col in self.TABLE_TO_DF_COL_MAP.values() if col != 'ID']
            if not all(col in self.dataframe.columns for col in required_columns):
                raise ValueError("Faltan columnas requeridas en los datos.")

            # Nombre del guion actual
            self.current_script_name = os.path.basename(file_name)
            if self.main_window:
                self.main_window.setWindowTitle(f"Editor de Guion - {self.current_script_name}")

            # Asignar IDs
            self.dataframe.insert(0, 'ID', range(len(self.dataframe)))

            # Llenar la tabla
            self.populate_table()
            self.unsaved_changes = False
        except Exception as e:
            self.handle_exception(e, "Error al cargar los datos")

    def load_from_excel(self, path=None):
        """
        Carga datos desde un archivo Excel y actualiza la tabla.
        """
        try:
            if not path:
                path, _ = QFileDialog.getOpenFileName(self, "Abrir archivo Excel", "", "Archivos Excel (*.xlsx)")
            if path:
                df = pd.read_excel(path)
                # Asignar IDs si no existen
                if 'ID' not in df.columns:
                    df.insert(0, 'ID', range(len(df)))

                required_columns = [col for col in self.TABLE_TO_DF_COL_MAP.values() if col != 'ID']
                if not all(col in df.columns for col in required_columns):
                    raise ValueError("Faltan columnas requeridas en los datos.")

                # Verificar SCENE
                if 'SCENE' not in df.columns:
                    self.has_scene_numbers = False
                    df['SCENE'] = 1
                    print("Importación desde Excel sin números de escena. Asignando 1 a todas las escenas.")
                else:
                    scene_values = df['SCENE'].astype(str).tolist()
                    unique_scenes = set(scene_values)
                    if len(unique_scenes) > 1 or (len(unique_scenes) == 1 and unique_scenes.pop() != '1'):
                        self.has_scene_numbers = True
                        print("Importación desde Excel con números de escena. Preservando escenas existentes.")
                    else:
                        self.has_scene_numbers = False
                        df['SCENE'] = 1
                        print("Importación desde Excel sin números de escena (todos '1'). Asignando 1 a todas las escenas.")

                df['SCENE'] = df['SCENE'].astype(int)
                self.dataframe = df
                self.populate_table()
                QMessageBox.information(self, "Éxito", "Datos importados correctamente desde Excel.")
                self.unsaved_changes = False

                self.current_script_name = os.path.basename(path)
                self.update_window_title()

                if self.main_window:
                    self.main_window.add_to_recent_files(path)
            else:
                QMessageBox.information(self, "Carga cancelada", "La carga del archivo Excel ha sido cancelada.")
        except Exception as e:
            self.handle_exception(e, "Error al cargar desde Excel")

    def import_from_excel(self):
        """
        Permite seleccionar un archivo Excel para importarlo en la tabla.
        """
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Abrir archivo Excel", "", "Archivos Excel (*.xlsx)")
            if path:
                self.load_from_excel(path)
            else:
                QMessageBox.information(self, "Carga cancelada", "La carga del archivo Excel ha sido cancelada.")
        except Exception as e:
            self.handle_exception(e, "Error al importar desde Excel")


    def export_to_excel(self):
        """
        Exporta los datos actuales a un archivo Excel.
        """
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Guardar archivo", "", "Archivos Excel (*.xlsx)")
            if path:
                self.save_to_excel(path)
                QMessageBox.information(self, "Éxito", "Datos exportados correctamente a Excel.")
                self.unsaved_changes = False
            else:
                QMessageBox.information(self, "Exportación cancelada", "La exportación ha sido cancelada.")
        except Exception as e:
            self.handle_exception(e, "Error al exportar a Excel")

    def save_to_excel(self, path):
        """
        Guarda el contenido del DataFrame en un archivo Excel.
        """
        try:
            # Actualizar el DataFrame con los diálogos actuales (desde los widgets)
            for row in range(self.table_widget.rowCount()):
                dialog_widget = self.table_widget.cellWidget(row, self.COL_DIALOGUE)
                if dialog_widget:
                    self.dataframe.at[row, 'DIÁLOGO'] = dialog_widget.toPlainText()

            # No incluir la columna 'ID'
            df_to_export = self.dataframe.drop(columns=['ID'])
            df_to_export.to_excel(path, index=False)

            self.current_script_name = os.path.basename(path)
            self.update_window_title()
            self.unsaved_changes = False
        except Exception as e:
            self.handle_exception(e, "Error al guardar en Excel")
            raise e

    def load_from_json(self):
        """
        Permite seleccionar un archivo JSON y cargar sus datos en la tabla,
        además de recuperar los campos de cabecera (header) si existen.
        """
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Abrir archivo JSON", "", "Archivos JSON (*.json)")
            if path:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # ---------------------
                # Leer la cabecera
                # ---------------------
                if "header" in data:
                    header = data["header"]
                    # Cargamos los valores si existen
                    self.reference_edit.setText(str(header.get("reference_number", "")))
                    self.product_edit.setText(header.get("product_name", ""))
                    self.chapter_edit.setText(str(header.get("chapter_number", "")))
                    tipo = header.get("type", "Ficcion")
                    if tipo in ["Ficcion", "Animacion", "Documental"]:
                        self.type_combo.setCurrentText(tipo)

                # ---------------------
                # Leer los datos (lista)
                # ---------------------
                if "data" in data and isinstance(data["data"], list):
                    df = pd.DataFrame(data["data"])
                else:
                    # Podría no tener la forma esperada
                    df = pd.DataFrame(data)

                if 'ID' not in df.columns:
                    df.insert(0, 'ID', range(len(df)))

                required_columns = [col for col in self.TABLE_TO_DF_COL_MAP.values() if col != 'ID']
                if not all(col in df.columns for col in required_columns):
                    raise ValueError("Faltan columnas requeridas en los datos.")

                if 'SCENE' not in df.columns:
                    self.has_scene_numbers = False
                    df['SCENE'] = 1
                    print("Importación desde JSON sin números de escena. Asignando 1 a todas las escenas.")
                else:
                    scene_values = df['SCENE'].astype(str).tolist()
                    unique_scenes = set(scene_values)
                    if len(unique_scenes) > 1 or (len(unique_scenes) == 1 and unique_scenes.pop() != '1'):
                        self.has_scene_numbers = True
                        print("Importación desde JSON con números de escena. Preservando escenas existentes.")
                    else:
                        self.has_scene_numbers = False
                        df['SCENE'] = 1
                        print("Importación desde JSON sin números de escena (todos '1'). Asignando 1 a todas las escenas.")

                df['SCENE'] = df['SCENE'].astype(int)
                self.dataframe = df
                self.populate_table()
                QMessageBox.information(self, "Éxito", "Datos cargados correctamente desde JSON.")
                self.unsaved_changes = False

                self.current_script_name = os.path.basename(path)
                self.update_window_title()
        except Exception as e:
            self.handle_exception(e, "Error al cargar desde JSON")

    def save_to_json(self):
        """
        Permite guardar los datos actuales en un archivo JSON,
        incluyendo la cabecera con los cuatro campos extra.
        Ahora, sugiere un nombre de archivo basado en product_name y chapter_number.
        """
        try:
            # Obtener valores actuales de los campos
            product_name = self.product_edit.text().strip()
            chapter_str = self.chapter_edit.text().strip()

            # Construir nombre de archivo sugerido
            suggested_name = "script.json"
            if product_name and chapter_str:
                suggested_name = f"{product_name}_{chapter_str}.json"
            elif product_name:  # Si solo está el nombre de producto
                suggested_name = f"{product_name}.json"
            elif chapter_str:   # Si solo está el número de capítulo
                suggested_name = f"capitulo_{chapter_str}.json"

            # Abrir diálogo con el nombre sugerido
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar archivo JSON",
                suggested_name,                 # Nombre por defecto
                "Archivos JSON (*.json)"
            )
            if path:
                self.save_to_json_file(path)
                QMessageBox.information(self, "Éxito", "Datos guardados correctamente en JSON.")
                self.unsaved_changes = False
            else:
                QMessageBox.information(self, "Exportación cancelada", "La exportación ha sido cancelada.")
        except Exception as e:
            self.handle_exception(e, "Error al guardar en JSON")


    def save_to_json_file(self, path):
        """
        Guarda el contenido del DataFrame en un archivo JSON,
        junto con la cabecera en la sección 'header'.
        """
        try:
            # Actualizar el DataFrame con los diálogos actuales
            for row in range(self.table_widget.rowCount()):
                dialog_widget = self.table_widget.cellWidget(row, self.COL_DIALOGUE)
                if dialog_widget:
                    self.dataframe.at[row, 'DIÁLOGO'] = dialog_widget.toPlainText()

            data = self.dataframe.drop(columns=['ID']).to_dict(orient='records')

            # Cabecera a exportar
            header = {
                "reference_number": self.reference_edit.text(),
                "product_name": self.product_edit.text(),
                "chapter_number": self.chapter_edit.text(),
                "type": self.type_combo.currentText()
            }

            # Estructura final del JSON
            json_output = {
                "header": header,
                "data": data
            }

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, ensure_ascii=False, indent=4)

            self.current_script_name = os.path.basename(path)
            self.update_window_title()
            self.unsaved_changes = False
        except Exception as e:
            self.handle_exception(e, "Error al guardar en JSON")
            raise e

    # -----------------------------------------------------------------------------------
    # MÉTODOS PARA LLENAR / ACTUALIZAR LA TABLA DESDE EL DATAFRAME
    # -----------------------------------------------------------------------------------
    def populate_table(self):
        """
        Llena la tabla con los datos del DataFrame.
        """
        try:
            if self.dataframe.empty:
                QMessageBox.information(self, "Información", "El archivo está vacío.")
                return

            self.table_widget.blockSignals(True)
            self.table_widget.clear()
            self.table_widget.setRowCount(self.dataframe.shape[0])
            self.table_widget.setColumnCount(len(self.columns))
            self.table_widget.setHorizontalHeaderLabels(self.columns)

            # Ocultar la columna ID
            self.table_widget.setColumnHidden(self.columns.index("ID"), True)

            for i in range(self.dataframe.shape[0]):
                for col_index, col_name in enumerate(self.columns):
                    if col_name == "DIÁLOGO":
                        dialogo_text = str(self.dataframe.at[i, col_name])
                        dialogo_item = self.create_text_edit(dialogo_text, i, self.COL_DIALOGUE)
                        self.table_widget.setCellWidget(i, self.COL_DIALOGUE, dialogo_item)
                    else:
                        text = str(self.dataframe.at[i, col_name])
                        item = self.create_table_item(text, col_index)
                        self.table_widget.setItem(i, col_index, item)

                self.adjust_row_height(i)

            self.table_widget.resizeColumnsToContents()
            self.table_widget.horizontalHeader().setStretchLastSection(True)
            self.table_widget.blockSignals(False)
        except Exception as e:
            self.handle_exception(e, "Error al llenar la tabla")

    def create_text_edit(self, text, row, column):
        """
        Crea un widget de texto personalizado para la celda de diálogo.
        """
        text_edit = CustomTextEdit()
        text_edit.setStyleSheet("font-size: 16px;")
        text_edit.setFont(QFont("Arial", 12))
        text_edit.setPlainText(str(text))

        # Conectar la señal de finalización de edición al slot correspondiente
        text_edit.editingFinished.connect(self.on_editing_finished)
        return text_edit

    def on_editing_finished(self, new_text):
        """
        Maneja el evento cuando se finaliza la edición de un campo de texto (CustomTextEdit).
        """
        try:
            text_edit = self.sender()
            if text_edit is None:
                return

            # Encontrar en qué celda está este widget
            found = False
            for row in range(self.table_widget.rowCount()):
                for column in range(self.table_widget.columnCount()):
                    widget = self.table_widget.cellWidget(row, column)
                    if widget == text_edit:
                        found = True
                        break
                if found:
                    break

            if not found:
                return

            df_col = self.get_dataframe_column_name(column)
            if not df_col:
                return

            old_text = self.dataframe.at[row, df_col]
            if new_text != old_text:
                command = EditCommand(self, row, column, old_text, new_text)
                self.undo_stack.push(command)
                self.unsaved_changes = True
        except Exception as e:
            self.handle_exception(e, "Error al finalizar la edición del texto")

    def create_table_item(self, text, column):
        """
        Crea un QTableWidgetItem con el texto y formato específico.
        """
        item = QTableWidgetItem(text)
        item.setFont(QFont("Arial", 12))
        return item

    def adjust_row_height(self, row):
        """
        Ajusta la altura de una fila en función del contenido de la celda de diálogo.
        """
        try:
            text_widget = self.table_widget.cellWidget(row, self.COL_DIALOGUE)
            if text_widget:
                document = text_widget.document()
                text_height = document.size().height()
                margins = text_widget.contentsMargins()
                total_height = text_height + margins.top() + margins.bottom() + 10
                self.table_widget.setRowHeight(row, int(total_height))
        except Exception as e:
            self.handle_exception(e, f"Error al ajustar la altura de la fila {row}")

    def adjust_all_row_heights(self):
        """
        Ajusta la altura de todas las filas de la tabla.
        """
        for row in range(self.table_widget.rowCount()):
            self.adjust_row_height(row)

    # -----------------------------------------------------------------------------------
    # MÉTODOS DE EDICIÓN Y MANIPULACIÓN DE CELDAS
    # -----------------------------------------------------------------------------------
    def on_item_changed(self, item):
        """
        Maneja el evento cuando cambia el contenido de una celda (QTableWidgetItem).
        """
        try:
            row = item.row()
            column = item.column()
            df_col = self.get_dataframe_column_name(column)
            if not df_col:
                return

            new_text = item.text()
            old_text = self.dataframe.at[row, df_col]

            # Si la columna es SCENE, convertir a entero
            if df_col == 'SCENE':
                try:
                    new_text = int(new_text)
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Error de Tipo",
                        f"El valor '{new_text}' no es un número entero válido para 'SCENE'."
                    )
                    item.setText(str(old_text))
                    return

            if new_text != old_text:
                command = EditCommand(self, row, column, old_text, new_text)
                self.undo_stack.push(command)
                self.unsaved_changes = True
                if column == self.COL_SCENE:
                    self.has_scene_numbers = True
                    print("El usuario ha editado los números de escena. has_scene_numbers = True")
        except Exception as e:
            self.handle_exception(e, "Error al actualizar celda en la tabla")

    def adjust_dialogs(self):
        """
        Ajusta el texto de todos los diálogos aplicando la función 'ajustar_dialogo'.
        """
        try:
            for i in range(self.dataframe.shape[0]):
                text_widget = self.table_widget.cellWidget(i, self.COL_DIALOGUE)
                if text_widget:
                    dialogo_actual = text_widget.toPlainText()
                    dialogo_ajustado = ajustar_dialogo(dialogo_actual)
                    text_widget.blockSignals(True)
                    text_widget.setPlainText(dialogo_ajustado)
                    text_widget.blockSignals(False)

                    old_text = self.dataframe.at[i, 'DIÁLOGO']
                    if dialogo_actual != dialogo_ajustado:
                        command = EditCommand(self, i, self.COL_DIALOGUE, old_text, dialogo_ajustado)
                        self.undo_stack.push(command)
                        self.unsaved_changes = True

                    self.adjust_row_height(i)

            QMessageBox.information(self, "Éxito", "Diálogos ajustados correctamente.")
        except Exception as e:
            self.handle_exception(e, "Error al ajustar diálogos")

    def copy_in_out_to_next(self):
        """
        Copia los valores IN y OUT de la fila seleccionada a la siguiente fila.
        """
        try:
            selected_row = self.table_widget.currentRow()
            if selected_row == -1:
                QMessageBox.warning(self, "Copiar IN/OUT", "Por favor, selecciona una fila para copiar IN y OUT.")
                return

            if selected_row >= self.table_widget.rowCount() - 1:
                QMessageBox.warning(self, "Copiar IN/OUT", "No hay una fila siguiente para pegar los tiempos.")
                return

            in_time = self.dataframe.at[selected_row, 'IN']
            out_time = self.dataframe.at[selected_row, 'OUT']

            next_row = selected_row + 1

            # Copiar IN
            old_in = self.dataframe.at[next_row, 'IN']
            if in_time != old_in:
                command_in = EditCommand(self, next_row, self.COL_IN, old_in, in_time)
                self.undo_stack.push(command_in)
                self.unsaved_changes = True

            # Copiar OUT
            old_out = self.dataframe.at[next_row, 'OUT']
            if out_time != old_out:
                command_out = EditCommand(self, next_row, self.COL_OUT, old_out, out_time)
                self.undo_stack.push(command_out)
                self.unsaved_changes = True

            QMessageBox.information(self, "Copiar IN/OUT", "Tiempos IN y OUT copiados a la siguiente intervención.")
        except Exception as e:
            self.handle_exception(e, "Error al copiar IN/OUT a la siguiente intervención")

    # -----------------------------------------------------------------------------------
    # MÉTODOS PARA AÑADIR / ELIMINAR / MOVER FILAS
    # -----------------------------------------------------------------------------------
    def add_new_row(self):
        """
        Agrega una nueva fila al final o debajo de la selección actual.
        """
        try:
            selected_row = self.table_widget.currentRow()
            if selected_row == -1:
                selected_row = self.table_widget.rowCount()
            else:
                selected_row += 1

            command = AddRowCommand(self, selected_row)
            self.undo_stack.push(command)
            self.unsaved_changes = True
        except Exception as e:
            self.handle_exception(e, "Error al agregar una nueva fila")

    def remove_row(self):
        """
        Elimina la(s) fila(s) seleccionada(s).
        """
        try:
            selected_rows = self.table_widget.selectionModel().selectedRows()
            if selected_rows:
                rows = sorted([index.row() for index in selected_rows], reverse=False)
                confirm = QMessageBox.question(
                    self, "Confirmar Eliminación",
                    f"¿Estás seguro de que deseas eliminar las filas seleccionadas?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if confirm == QMessageBox.Yes:
                    command = RemoveRowsCommand(self, rows)
                    self.undo_stack.push(command)
                    self.unsaved_changes = True
            else:
                QMessageBox.warning(self, "Eliminar Filas", "Por favor, selecciona al menos una fila para eliminar.")
        except Exception as e:
            self.handle_exception(e, "Error al eliminar las filas")

    def move_row_up(self):
        """
        Mueve la fila seleccionada hacia arriba.
        """
        try:
            selected_row = self.table_widget.currentRow()
            if selected_row > 0:
                command = MoveRowCommand(self, selected_row, selected_row - 1)
                self.undo_stack.push(command)
                self.table_widget.selectRow(selected_row - 1)
                self.unsaved_changes = True
        except Exception as e:
            self.handle_exception(e, "Error al mover la fila hacia arriba")

    def move_row_down(self):
        """
        Mueve la fila seleccionada hacia abajo.
        """
        try:
            selected_row = self.table_widget.currentRow()
            if selected_row < self.table_widget.rowCount() - 1:
                command = MoveRowCommand(self, selected_row, selected_row + 1)
                self.undo_stack.push(command)
                self.table_widget.selectRow(selected_row + 1)
                self.unsaved_changes = True
        except Exception as e:
            self.handle_exception(e, "Error al mover la fila hacia abajo")

    # -----------------------------------------------------------------------------------
    # MÉTODOS PARA CONVERSIÓN DE TIME CODES
    # -----------------------------------------------------------------------------------
    def convert_time_code_to_milliseconds(self, time_code):
        """
        Convierte un time code en formato HH:MM:SS:FF a milisegundos.
        """
        try:
            parts = time_code.split(':')
            if len(parts) != 4:
                raise ValueError("Formato de time code inválido.")
            hours, minutes, seconds, frames = map(int, parts)
            milliseconds = (hours * 3600 + minutes * 60 + seconds) * 1000 + int((frames / 25) * 1000)
            return milliseconds
        except Exception as e:
            self.handle_exception(e, "Error al convertir time code a milisegundos")
            raise

    def convert_milliseconds_to_time_code(self, ms):
        """
        Convierte milisegundos en un time code con formato HH:MM:SS:FF.
        """
        try:
            total_seconds = ms // 1000
            frames = int((ms % 1000) / (1000 / 25))
            seconds = total_seconds % 60
            minutes = (total_seconds // 60) % 60
            hours = total_seconds // 3600
            return f"{hours:02}:{minutes:02}:{seconds:02}:{frames:02}"
        except Exception:
            return "00:00:00:00"

    # -----------------------------------------------------------------------------------
    # MANEJO DE IN/OUT DESDE EL REPRODUCTOR DE VIDEO
    # -----------------------------------------------------------------------------------
    def update_in_out(self, action, position_ms):
        """
        Actualiza la columna IN u OUT de la fila seleccionada según la acción recibida.
        """
        try:
            if not action or position_ms is None:
                return

            selected_row = self.table_widget.currentRow()
            if selected_row == -1:
                QMessageBox.warning(self, "Error", "No hay fila seleccionada para actualizar IN/OUT.")
                return

            time_code = self.convert_milliseconds_to_time_code(position_ms)
            if action.upper() == "IN":
                old_value = self.dataframe.at[selected_row, 'IN']
                if time_code != old_value:
                    command = EditCommand(self, selected_row, self.COL_IN, old_value, time_code)
                    self.undo_stack.push(command)
                    self.unsaved_changes = True
            elif action.upper() == "OUT":
                old_value = self.dataframe.at[selected_row, 'OUT']
                if time_code != old_value:
                    command = EditCommand(self, selected_row, self.COL_OUT, old_value, time_code)
                    self.undo_stack.push(command)
                    self.unsaved_changes = True
        except Exception as e:
            self.handle_exception(e, "Error en update_in_out")

    def select_next_row_and_set_in(self):
        """
        Selecciona la siguiente fila y ajusta el tiempo IN al valor OUT de la fila actual.
        """
        try:
            current_row = self.table_widget.currentRow()
            if current_row == -1:
                return

            current_out_time = self.dataframe.at[current_row, 'OUT']
            current_out_ms = self.convert_time_code_to_milliseconds(current_out_time)

            next_row = current_row + 1
            if next_row < self.table_widget.rowCount():
                self.table_widget.selectRow(next_row)
                time_code = self.convert_milliseconds_to_time_code(current_out_ms)
                old_in = self.dataframe.at[next_row, 'IN']
                if time_code != old_in:
                    command = EditCommand(self, next_row, self.COL_IN, old_in, time_code)
                    self.undo_stack.push(command)
                    self.unsaved_changes = True
                self.adjust_row_height(next_row)
                self.table_widget.scrollToItem(
                    self.table_widget.item(next_row, self.COL_SCENE),
                    QAbstractItemView.PositionAtCenter
                )
        except Exception as e:
            self.handle_exception(e, "Error al seleccionar la siguiente fila")

    # -----------------------------------------------------------------------------------
    # MÉTODOS PARA SEPARAR / JUNTAR INTERVENCIONES
    # -----------------------------------------------------------------------------------
    def split_intervention(self):
        """
        Separa una intervención en dos (en la fila seleccionada),
        basándose en la posición del cursor dentro del diálogo.
        """
        try:
            selected_row = self.table_widget.currentRow()
            if selected_row == -1:
                QMessageBox.warning(self, "Separar Intervención", "Por favor, selecciona una fila para separar.")
                return

            dialog_widget = self.table_widget.cellWidget(selected_row, self.COL_DIALOGUE)
            if not dialog_widget:
                QMessageBox.warning(self, "Separar Intervención", "No hay diálogo para separar.")
                return

            cursor = dialog_widget.textCursor()
            if cursor.hasSelection():
                position = cursor.selectionEnd()
            else:
                position = cursor.position()

            text = dialog_widget.toPlainText()
            if position >= len(text):
                QMessageBox.warning(self, "Separar Intervención",
                                    "No hay texto para separar después de la posición seleccionada.")
                return

            before = text[:position]
            after = text[position:]

            command = SplitInterventionCommand(self, selected_row, before, after)
            self.undo_stack.push(command)
            self.unsaved_changes = True
        except Exception as e:
            self.handle_exception(e, "Error al separar intervención")

    def merge_interventions(self):
        """
        Junta la intervención de la fila seleccionada con la siguiente,
        siempre y cuando el personaje sea el mismo.
        """
        try:
            selected_row = self.table_widget.currentRow()
            if selected_row == -1:
                QMessageBox.warning(self, "Juntar Intervenciones", "Por favor, selecciona una fila para juntar.")
                return

            if selected_row >= self.table_widget.rowCount() - 1:
                QMessageBox.warning(self, "Juntar Intervenciones", "No hay una segunda fila para juntar.")
                return

            personaje_current = self.dataframe.at[selected_row, 'PERSONAJE']
            personaje_next = self.dataframe.at[selected_row + 1, 'PERSONAJE']

            if personaje_current != personaje_next:
                QMessageBox.warning(self, "Juntar Intervenciones",
                                    "Las filas seleccionadas no tienen el mismo personaje.")
                return

            dialog_current_widget = self.table_widget.cellWidget(selected_row, self.COL_DIALOGUE)
            dialog_next_widget = self.table_widget.cellWidget(selected_row + 1, self.COL_DIALOGUE)
            if not dialog_current_widget or not dialog_next_widget:
                QMessageBox.warning(self, "Juntar Intervenciones", "No hay diálogos para juntar.")
                return

            dialog_current = dialog_current_widget.toPlainText().strip()
            dialog_next = dialog_next_widget.toPlainText().strip()

            if not dialog_current and not dialog_next:
                QMessageBox.warning(self, "Juntar Intervenciones", "Ambos diálogos están vacíos.")
                return

            merged_dialog = f"{dialog_current} {dialog_next}".strip()

            command = MergeInterventionsCommand(self, selected_row, merged_dialog)
            self.undo_stack.push(command)
            self.unsaved_changes = True

            QMessageBox.information(self, "Juntar Intervenciones", "Las intervenciones han sido juntadas exitosamente.")
        except Exception as e:
            self.handle_exception(e, "Error al juntar intervenciones")

    # -----------------------------------------------------------------------------------
    # OTROS MÉTODOS DE UTILIDAD
    # -----------------------------------------------------------------------------------
    def handle_ctrl_click(self, row):
        try:
            in_time_code = self.dataframe.at[row, 'IN']
            milliseconds = self.convert_time_code_to_milliseconds(in_time_code)
            self.in_out_signal.emit("IN", milliseconds)
        except Exception as e:
            self.handle_exception(e, "Error al desplazar el video")

    def handle_alt_click(self, row):
        try:
            out_time_code = self.dataframe.at[row, 'OUT']
            milliseconds = self.convert_time_code_to_milliseconds(out_time_code)
            self.in_out_signal.emit("OUT", milliseconds)
        except Exception as e:
            self.handle_exception(e, "Error al desplazar el video")

    def get_character_names(self):
        """
        Devuelve un conjunto ordenado de los nombres de personajes en el DataFrame.
        """
        return sorted(set(self.dataframe['PERSONAJE'].tolist()))

    def update_character_completer(self):
        """
        Actualiza el completer del delegado de personaje (CharacterDelegate).
        """
        self.table_widget.setItemDelegateForColumn(
            self.COL_CHARACTER,
            CharacterDelegate(get_names_callback=self.get_character_names, parent=self.table_widget)
        )

    def update_character_name(self, old_name, new_name):
        """
        Actualiza un nombre de personaje en el DataFrame y en la tabla.
        """
        self.dataframe.loc[self.dataframe['PERSONAJE'] == old_name, 'PERSONAJE'] = new_name
        for row in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row, self.COL_CHARACTER)
            if item and item.text() == old_name:
                item.setText(new_name)

        self.unsaved_changes = True
        self.update_character_completer()
        self.character_name_changed.emit()

    def find_and_replace(self, find_text, replace_text, search_in_character=True, search_in_dialogue=True):
        """
        Realiza un buscar y reemplazar en columnas de personaje y/o diálogos.
        """
        try:
            for row in range(self.table_widget.rowCount()):
                # Reemplazar en diálogos
                if search_in_dialogue:
                    dialog_widget = self.table_widget.cellWidget(row, self.COL_DIALOGUE)
                    if dialog_widget:
                        text = dialog_widget.toPlainText()
                        if find_text in text:
                            new_text = text.replace(find_text, replace_text)
                            command = EditCommand(self, row, self.COL_DIALOGUE, text, new_text)
                            self.undo_stack.push(command)
                            self.unsaved_changes = True

                # Reemplazar en personajes
                if search_in_character:
                    character_item = self.table_widget.item(row, self.COL_CHARACTER)
                    if character_item:
                        text = character_item.text()
                        if find_text in text:
                            new_text = text.replace(find_text, replace_text)
                            command = EditCommand(self, row, self.COL_CHARACTER, text, new_text)
                            self.undo_stack.push(command)
                            self.unsaved_changes = True

            QMessageBox.information(self, "Buscar y Reemplazar", "Reemplazo completado.")
        except Exception as e:
            self.handle_exception(e, "Error en buscar y reemplazar")

    def update_window_title(self):
        """
        Actualiza el título de la ventana principal, indicando si hay cambios sin guardar.
        """
        prefix = "*" if self.unsaved_changes else ""
        script_name = self.current_script_name if self.current_script_name else "Sin Título"
        if self.main_window:
            self.main_window.setWindowTitle(f"{prefix}Editor de Guion - {script_name}")

    def renumerar_escenas(self):
        """
        Asigna '1' a todas las escenas si no se detectaron números de escena durante la carga.
        """
        try:
            if not self.has_scene_numbers:
                print("Renumerando escenas: Asignando '1' a todas las escenas.")
                for row in range(self.table_widget.rowCount()):
                    self.dataframe.at[row, 'SCENE'] = '1'
                    item = self.table_widget.item(row, self.COL_SCENE)
                    if item:
                        item.setText('1')
                self.unsaved_changes = True
            else:
                print("No se renumeran escenas porque los datos importados tienen números de escena.")
        except Exception as e:
            self.handle_exception(e, "Error al renumerar escenas")

    def get_next_id(self):
        """
        Devuelve el siguiente ID disponible para una nueva fila.
        """
        if not self.dataframe.empty and 'ID' in self.dataframe.columns:
            return int(self.dataframe['ID'].max()) + 1
        else:
            return 0

    def find_dataframe_index_by_id(self, id_value):
        """
        Devuelve el índice del DataFrame para el ID dado.
        Si no se encuentra, devuelve None.
        """
        df_index = self.dataframe.index[self.dataframe['ID'] == id_value]
        if not df_index.empty:
            return df_index[0]
        else:
            return None

    def find_table_row_by_id(self, id_value):
        """
        Devuelve la fila de la tabla para el ID dado.
        Si no se encuentra, devuelve None.
        """
        for row in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row, self.COL_ID)
            if item and int(item.text()) == id_value:
                return row
        return None

    def change_scene(self):
        """
        Cambia el número de escena desde la fila seleccionada en adelante (incrementa en +1).
        """
        selected_row = self.table_widget.currentRow()
        if selected_row == -1:
            QMessageBox.warning(
                self,
                "Cambio de Escena",
                "Por favor, selecciona una intervención para marcar el cambio de escena."
            )
            return

        command = ChangeSceneCommand(self, selected_row)
        self.undo_stack.push(command)
        self.unsaved_changes = True

    # -----------------------------------------------------------------------------------
    # MANEJO DE EXCEPCIONES
    # -----------------------------------------------------------------------------------
    def handle_exception(self, exception, message):
        """
        Muestra un mensaje de error en pantalla y registra la excepción.
        """
        QMessageBox.critical(self, "Error", f"{message}: {str(exception)}")

    def get_dataframe_column_name(self, table_col_index):
        """
        Mapea el índice de columna de la tabla al nombre de columna del DataFrame.
        """
        return self.TABLE_TO_DF_COL_MAP.get(table_col_index, None)


# =======================================================================================
# CLASES DE COMANDOS (DESHACER / REHACER)
# =======================================================================================

class EditCommand(QUndoCommand):
    """
    Comando para editar el contenido de una celda. Soporta deshacer/rehacer.
    """
    def __init__(self, table_window, row, column, old_value, new_value):
        super().__init__()
        self.table_window = table_window
        self.row = row
        self.column = column
        self.old_value = old_value
        self.new_value = new_value
        column_name = table_window.columns[column]
        self.setText(f"Editar {column_name} en fila {row + 1}")

    def undo(self):
        self._apply_value(self.old_value)

    def redo(self):
        self._apply_value(self.new_value)

    def _apply_value(self, value):
        df_col_name = self.table_window.get_dataframe_column_name(self.column)
        if df_col_name is None:
            return

        # Manejo especial para SCENE o ID (enteros)
        if df_col_name in ['SCENE', 'ID']:
            try:
                int_value = int(value)
            except ValueError:
                QMessageBox.warning(
                    self.table_window,
                    "Error de Tipo",
                    f"El valor '{value}' no es un número entero válido."
                )
                return
            self.table_window.dataframe.at[self.row, df_col_name] = int_value
        else:
            self.table_window.dataframe.at[self.row, df_col_name] = value

        # Actualizar interfaz
        if self.column == self.table_window.COL_DIALOGUE:
            text_widget = self.table_window.table_widget.cellWidget(self.row, self.column)
            if text_widget:
                text_widget.blockSignals(True)
                text_widget.setPlainText(str(value))
                text_widget.blockSignals(False)
            self.table_window.adjust_row_height(self.row)
        else:
            item = self.table_window.table_widget.item(self.row, self.column)
            if item:
                item.setText(str(value))


class AddRowCommand(QUndoCommand):
    """
    Comando para agregar una nueva fila a la tabla y al DataFrame.
    """
    def __init__(self, table_window, row):
        super().__init__()
        self.table_window = table_window
        self.row = row
        self.new_row_data = {
            'ID': int(self.table_window.get_next_id()),
            'SCENE': int(1),
            'IN': '00:00:00:00',
            'OUT': '00:00:00:00',
            'PERSONAJE': 'Personaje',
            'DIÁLOGO': 'Nuevo diálogo'
        }
        self.setText("Agregar fila")

    def undo(self):
        # Eliminar la fila tanto de la tabla como del DataFrame
        self.table_window.table_widget.removeRow(self.row)
        df_row = self.table_window.find_dataframe_index_by_id(self.new_row_data['ID'])
        if df_row is not None:
            self.table_window.dataframe = self.table_window.dataframe.drop(df_row).reset_index(drop=True)

    def redo(self):
        # Insertar la nueva fila en la tabla
        self.table_window.table_widget.insertRow(self.row)
        for col_index, col_name in enumerate(self.table_window.columns):
            value = self.new_row_data.get(col_name, '')
            if col_name == "DIÁLOGO":
                dialogo_item = self.table_window.create_text_edit(value, self.row, self.table_window.COL_DIALOGUE)
                self.table_window.table_widget.setCellWidget(self.row, self.table_window.COL_DIALOGUE, dialogo_item)
            else:
                item = self.table_window.create_table_item(str(value), col_index)
                self.table_window.table_widget.setItem(self.row, col_index, item)

        self.table_window.adjust_row_height(self.row)

        # Insertar datos en el DataFrame
        df_new_row = pd.DataFrame([self.new_row_data])
        self.table_window.dataframe = pd.concat(
            [
                self.table_window.dataframe.iloc[:self.row],
                df_new_row,
                self.table_window.dataframe.iloc[self.row:]
            ],
            ignore_index=True
        )


class RemoveRowsCommand(QUndoCommand):
    """
    Comando para eliminar una o varias filas de la tabla y el DataFrame.
    """
    def __init__(self, table_window, rows):
        super().__init__()
        self.table_window = table_window
        self.rows = sorted(rows)
        self.removed_data = self.table_window.dataframe.iloc[self.rows].copy()
        self.setText("Eliminar filas")

    def undo(self):
        # Restaurar filas en la tabla y DataFrame
        for i, row in enumerate(self.rows):
            self.table_window.table_widget.insertRow(row)
            data_row = self.removed_data.iloc[i]
            for col_index, col_name in enumerate(self.table_window.columns):
                value = data_row[col_name]
                if col_name == "DIÁLOGO":
                    dialogo_text = str(value)
                    dialogo_item = self.table_window.create_text_edit(dialogo_text, row,
                                                                      self.table_window.COL_DIALOGUE)
                    self.table_window.table_widget.setCellWidget(row, self.table_window.COL_DIALOGUE, dialogo_item)
                else:
                    item = self.table_window.create_table_item(str(value), col_index)
                    self.table_window.table_widget.setItem(row, col_index, item)

            self.table_window.adjust_row_height(row)

            # Insertar datos en el DataFrame
            upper_df = self.table_window.dataframe.iloc[:row] if row > 0 else pd.DataFrame(
                columns=self.table_window.dataframe.columns)
            lower_df = self.table_window.dataframe.iloc[row:] if row < self.table_window.dataframe.shape[0] else pd.DataFrame(
                columns=self.table_window.dataframe.columns)
            new_df = pd.DataFrame([data_row.to_dict()])
            self.table_window.dataframe = pd.concat([upper_df, new_df, lower_df], ignore_index=True)

    def redo(self):
        # Eliminar filas en la tabla y DataFrame
        for row in reversed(self.rows):
            self.table_window.table_widget.removeRow(row)
            df_row = self.table_window.find_dataframe_index_by_id(self.removed_data.at[row, 'ID'])
            if df_row is not None:
                self.table_window.dataframe = self.table_window.dataframe.drop(df_row).reset_index(drop=True)


class MoveRowCommand(QUndoCommand):
    """
    Comando para mover una fila de la tabla y el DataFrame a otra posición.
    """
    def __init__(self, table_window, source_row, target_row):
        super().__init__()
        self.table_window = table_window
        self.source_row = source_row
        self.target_row = target_row
        self.setText("Mover fila")

    def undo(self):
        self._move_row(self.target_row, self.source_row)

    def redo(self):
        self._move_row(self.source_row, self.target_row)

    def _move_row(self, from_row, to_row):
        # Mover en DataFrame
        df = self.table_window.dataframe
        row_data = df.iloc[from_row].copy()
        df = df.drop(from_row).reset_index(drop=True)
        df = pd.concat([df.iloc[:to_row], pd.DataFrame([row_data]), df.iloc[to_row:]]).reset_index(drop=True)
        self.table_window.dataframe = df

        # Mover visualmente en la tabla
        self.table_window.table_widget.blockSignals(True)

        row_data_items = {}
        for col in range(self.table_window.table_widget.columnCount()):
            if col == self.table_window.COL_DIALOGUE:
                widget = self.table_window.table_widget.cellWidget(from_row, col)
                if widget:
                    text = widget.toPlainText()
                    row_data_items[col] = text
            else:
                item = self.table_window.table_widget.item(from_row, col)
                if item:
                    text = item.text()
                    row_data_items[col] = text

        self.table_window.table_widget.removeRow(from_row)
        self.table_window.table_widget.insertRow(to_row)

        for col in range(self.table_window.table_widget.columnCount()):
            if col == self.table_window.COL_DIALOGUE:
                text = row_data_items.get(col, '')
                text_edit = self.table_window.create_text_edit(text, to_row, col)
                self.table_window.table_widget.setCellWidget(to_row, col, text_edit)
            else:
                text = row_data_items.get(col, '')
                item = self.table_window.create_table_item(text, col)
                self.table_window.table_widget.setItem(to_row, col, item)

        self.table_window.table_widget.blockSignals(False)
        self.table_window.adjust_row_height(to_row)


class SplitInterventionCommand(QUndoCommand):
    """
    Comando para separar una intervención en dos.
    """
    def __init__(self, table_window, row, before_text, after_text):
        super().__init__()
        self.table_window = table_window
        self.before_text = before_text
        self.after_text = after_text
        self.original_text = before_text + after_text

        # Capturar ID, PERSONAJE y SCENE de la fila actual
        self.row_id = int(self.table_window.dataframe.at[row, 'ID'])
        self.personaje = self.table_window.dataframe.at[row, 'PERSONAJE']
        self.scene = int(self.table_window.dataframe.at[row, 'SCENE'])

        # Crear nueva fila con la parte "after" del diálogo
        self.new_row_id = int(self.table_window.get_next_id())
        self.new_row_data = {
            'ID': self.new_row_id,
            'SCENE': self.scene,
            'IN': '00:00:00:00',
            'OUT': '00:00:00:00',
            'PERSONAJE': self.personaje,
            'DIÁLOGO': self.after_text
        }
        self.setText("Separar intervención")

    def undo(self):
        # Restaurar texto original en la fila actual
        df_row = self.table_window.find_dataframe_index_by_id(self.row_id)
        if df_row is None:
            return
        self.table_window.dataframe.at[df_row, 'DIÁLOGO'] = self.original_text

        table_row = self.table_window.find_table_row_by_id(self.row_id)
        if table_row is None:
            return
        text_widget = self.table_window.table_widget.cellWidget(table_row, self.table_window.COL_DIALOGUE)
        if text_widget:
            text_widget.blockSignals(True)
            text_widget.setPlainText(self.original_text)
            text_widget.blockSignals(False)
            self.table_window.adjust_row_height(table_row)

        # Eliminar la nueva fila
        new_df_row = self.table_window.find_dataframe_index_by_id(self.new_row_id)
        if new_df_row is not None:
            self.table_window.dataframe = self.table_window.dataframe.drop(new_df_row).reset_index(drop=True)

        new_table_row = self.table_window.find_table_row_by_id(self.new_row_id)
        if new_table_row is not None:
            self.table_window.table_widget.removeRow(new_table_row)

    def redo(self):
        # Asignar la parte "before" al texto de la fila original
        df_row = self.table_window.find_dataframe_index_by_id(self.row_id)
        if df_row is None:
            return
        self.table_window.dataframe.at[df_row, 'DIÁLOGO'] = self.before_text

        table_row = self.table_window.find_table_row_by_id(self.row_id)
        if table_row is None:
            return
        text_widget = self.table_window.table_widget.cellWidget(table_row, self.table_window.COL_DIALOGUE)
        if text_widget:
            text_widget.blockSignals(True)
            text_widget.setPlainText(self.before_text)
            text_widget.blockSignals(False)
            self.table_window.adjust_row_height(table_row)

        # Insertar la nueva fila en el DataFrame
        df_new_row = df_row + 1
        new_df = pd.DataFrame([self.new_row_data])
        self.table_window.dataframe = pd.concat([
            self.table_window.dataframe.iloc[:df_new_row],
            new_df,
            self.table_window.dataframe.iloc[df_new_row:]
        ]).reset_index(drop=True)

        # Insertar la nueva fila en la tabla
        table_new_row = table_row + 1
        self.table_window.table_widget.insertRow(table_new_row)
        for col_index, col_name in enumerate(self.table_window.columns):
            if col_name == "DIÁLOGO":
                dialogo_text = self.new_row_data['DIÁLOGO']
                dialogo_item = self.table_window.create_text_edit(dialogo_text, table_new_row,
                                                                  self.table_window.COL_DIALOGUE)
                self.table_window.table_widget.setCellWidget(table_new_row, self.table_window.COL_DIALOGUE,
                                                              dialogo_item)
            else:
                value = self.table_window.dataframe.at[df_new_row, col_name]
                item = self.table_window.create_table_item(str(value), col_index)
                self.table_window.table_widget.setItem(table_new_row, col_index, item)
        self.table_window.adjust_row_height(table_new_row)


class MergeInterventionsCommand(QUndoCommand):
    """
    Comando para juntar la intervención de la fila seleccionada con la siguiente.
    """
    def __init__(self, table_window, row, merged_dialog):
        super().__init__()
        self.table_window = table_window
        self.row = row
        self.merged_dialog = merged_dialog
        self.next_row_data = self.table_window.dataframe.iloc[row + 1].copy()
        self.original_dialog = self.table_window.dataframe.at[row, 'DIÁLOGO']
        self.setText("Juntar intervenciones")

    def undo(self):
        # Restaurar el diálogo original
        command = EditCommand(self.table_window, self.row,
                              self.table_window.COL_DIALOGUE,
                              self.merged_dialog, self.original_dialog)
        self.table_window.undo_stack.push(command)

        # Restaurar la fila eliminada
        self.table_window.table_widget.insertRow(self.row + 1)
        for col_index, col_name in enumerate(self.table_window.columns):
            if col_name == "DIÁLOGO":
                dialogo_text = self.next_row_data[col_name]
                dialogo_item = self.table_window.create_text_edit(dialogo_text,
                                                                  self.row + 1,
                                                                  self.table_window.COL_DIALOGUE)
                self.table_window.table_widget.setCellWidget(self.row + 1,
                                                             self.table_window.COL_DIALOGUE,
                                                             dialogo_item)
            else:
                value = self.next_row_data[col_name]
                item = self.table_window.create_table_item(str(value), col_index)
                self.table_window.table_widget.setItem(self.row + 1, col_index, item)

        self.table_window.adjust_row_height(self.row + 1)

        # Insertar datos en el DataFrame
        upper_df = self.table_window.dataframe.iloc[:self.row + 1]
        lower_df = self.table_window.dataframe.iloc[self.row + 1:]
        new_df = pd.DataFrame([self.next_row_data.to_dict()])
        self.table_window.dataframe = pd.concat([upper_df, new_df, lower_df], ignore_index=True)

    def redo(self):
        # Actualizar diálogo de la fila seleccionada
        command = EditCommand(self.table_window, self.row,
                              self.table_window.COL_DIALOGUE,
                              self.original_dialog, self.merged_dialog)
        self.table_window.undo_stack.push(command)

        # Eliminar la fila siguiente
        self.table_window.table_widget.removeRow(self.row + 1)
        self.table_window.dataframe = self.table_window.dataframe.drop(self.row + 1).reset_index(drop=True)


class ChangeSceneCommand(QUndoCommand):
    """
    Comando para cambiar el número de escena en la fila seleccionada y todas las subsiguientes.
    """
    def __init__(self, table_window, selected_row):
        super().__init__()
        self.table_window = table_window
        self.selected_row = selected_row
        self.setText("Cambiar número de escena")

        # Escenas antiguas
        self.old_scene_numbers = self.table_window.dataframe['SCENE'].iloc[selected_row:].tolist()
        try:
            self.old_scene_numbers = [int(scene) for scene in self.old_scene_numbers]
        except ValueError:
            QMessageBox.warning(
                self.table_window,
                "Error de Tipo",
                f"Uno o más valores en 'SCENE' no son enteros válidos."
            )
            self.old_scene_numbers = [1 for _ in self.old_scene_numbers]

        # Escenas nuevas (incrementadas en +1)
        self.new_scene_numbers = [scene + 1 for scene in self.old_scene_numbers]

    def undo(self):
        # Restaurar escenas antiguas
        for idx, scene_number in enumerate(self.old_scene_numbers):
            row = self.selected_row + idx
            self.table_window.dataframe.at[row, 'SCENE'] = scene_number
            item = self.table_window.table_widget.item(row, self.table_window.COL_SCENE)
            if item:
                item.setText(str(scene_number))
                if idx == 0:
                    for col in range(self.table_window.table_widget.columnCount()):
                        cell_item = self.table_window.table_widget.item(row, col)
                        if cell_item:
                            cell_item.setBackground(Qt.white)

    def redo(self):
        # Asignar escenas nuevas
        total_rows = self.table_window.table_widget.rowCount()
        for idx, row in enumerate(range(self.selected_row, total_rows)):
            new_number = self.new_scene_numbers[idx]
            self.table_window.dataframe.at[row, 'SCENE'] = new_number
            item = self.table_window.table_widget.item(row, self.table_window.COL_SCENE)
            if item:
                item.setText(str(new_number))
                # Resaltar la fila donde se produce el cambio
                if row == self.selected_row:
                    for col in range(self.table_window.table_widget.columnCount()):
                        cell_item = self.table_window.table_widget.item(row, col)
                        if cell_item:
                            cell_item.setBackground(QColor("#FFD700"))  # Amarillo dorado
