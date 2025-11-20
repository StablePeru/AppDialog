# guion_editor/widgets/video_player_widget.py
import os
import bisect 

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QSlider, QLabel,
    QMessageBox, QHBoxLayout, QStackedLayout, QCheckBox, QComboBox,
    QSplitter, QSizePolicy
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal, QSize, QKeyCombination
from PyQt6.QtGui import QKeySequence, QFont, QIcon, QKeyEvent, QFontMetrics, QMouseEvent, QColor

from .time_code_edit import TimeCodeEdit
from guion_editor.widgets.waveform_widget import WaveformWidget

class VideoPlayerWidget(QWidget):
    in_out_signal = pyqtSignal(str, int)
    out_released = pyqtSignal()
    detach_requested = pyqtSignal(QWidget)

    FPS_RATE = 25.0

    def __init__(self, get_icon_func=None, main_window=None):
        super().__init__()
        self._audio_output_handler = None
        self.get_icon = get_icon_func
        self.main_window = main_window
        self.f6_key_pressed_internally = False

        self._me_audio_output_handler = None
        self.me_player = None
        self.use_me_audio = False
        self.user_volume_float = 1.0

        self.table_window_ref = None
        
        self.subtitle_timeline = [] 
        self.subtitle_start_times = [] 
        self.current_subtitle_timeline_idx = -1 
        self.subtitle_source_column = 'DIÁLOGO'

        if self.get_icon:
            self.play_icon = self.get_icon("play_icon.svg")
            self.pause_icon = self.get_icon("pause_icon.svg")
            self.volume_up_icon = self.get_icon("volume_up_icon.svg")
            self.volume_off_icon = self.get_icon("volume_off_icon.svg")
            self.load_audio_icon = self.get_icon("load_audio_icon.svg")
        else:
            self.play_icon, self.pause_icon, self.volume_up_icon, self.volume_off_icon, self.load_audio_icon = QIcon(), QIcon(), QIcon(), QIcon(), QIcon()

        self.init_ui()
        self.setup_timers()
        
        self.out_timer = QTimer(self)
        self.out_timer.setInterval(40) 
        self.out_timer.timeout.connect(self.mark_out_continuous)
        self.out_timer.setSingleShot(False)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_table_window_reference(self, table_window):
        self.table_window_ref = table_window
        if self.table_window_ref and hasattr(self.table_window_ref, 'pandas_model'):
            model = self.table_window_ref.pandas_model
            model.modelReset.connect(self._refresh_subtitle_timeline)
            model.layoutChanged.connect(self._refresh_subtitle_timeline)
            if hasattr(self.table_window_ref, '_recache_timer'):
                self.table_window_ref._recache_timer.timeout.connect(self._refresh_subtitle_timeline)


    def init_ui(self) -> None:
        # 1. Inicializamos el Widget de Onda
        self.waveform_widget = WaveformWidget(self)
        self.waveform_widget.setVisible(False) 
        self.waveform_widget.tracks_found.connect(self.populate_audio_tracks)

        self.media_player = QMediaPlayer()
        if not self.media_player.audioOutput():
            self._audio_output_handler = QAudioOutput()
            self.media_player.setAudioOutput(self._audio_output_handler)
        
        self.setup_controls()

        audio_output = self.media_player.audioOutput()
        if audio_output:
            if not getattr(audio_output, '_volume_signal_connected_vpw', False):
                audio_output.volumeChanged.connect(self.update_volume_slider_display)
                setattr(audio_output, '_volume_signal_connected_vpw', True)
            initial_volume_percent = int(audio_output.volume() * 100)
            if hasattr(self, 'volume_slider_vertical'):
                self.volume_slider_vertical.setValue(initial_volume_percent)
        elif hasattr(self, 'volume_slider_vertical'):
            self.volume_slider_vertical.setValue(100)

        self.video_widget = QVideoWidget()
        self.video_widget.setObjectName("video_widget")
        self.media_player.setVideoOutput(self.video_widget)

        self.subtitle_container = QWidget()
        self.subtitle_container.setObjectName("subtitle_container")
        subtitle_layout = QHBoxLayout(self.subtitle_container) 
        subtitle_layout.setContentsMargins(10, 5, 10, 5)

        self.subtitle_display_label = QLabel("") 
        self.subtitle_display_label.setObjectName("subtitle_display_label_in_container") 
        self.subtitle_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_display_label.setWordWrap(True)
        subtitle_layout.addWidget(self.subtitle_display_label)
        
        self.update_fonts(9)
        self.subtitle_container.setVisible(False)

        self.media_player.playbackStateChanged.connect(self.update_play_button_icon)
        self.media_player.positionChanged.connect(self.update_slider_position)
        self.media_player.positionChanged.connect(self._trigger_subtitle_update) 
        
        # Sincronizar la posición de la onda con el video
        self.media_player.positionChanged.connect(self.waveform_widget.set_position)

        self.media_player.durationChanged.connect(self.update_slider_range)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.media_player.errorOccurred.connect(self.on_media_error)

        self.setup_layouts()


    def setup_controls(self) -> None:
        player_icon_size = QSize(20, 20)

        self.play_button = QPushButton() 
        if self.get_icon: self.play_button.setIcon(self.play_icon)
        self.play_button.setIconSize(player_icon_size)
        self.play_button.setObjectName("play_button")
        self.play_button.setToolTip("Reproducir/Pausar (Ver Shortcuts)")
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setProperty("iconOnlyButton", True)

        self.rewind_button = QPushButton() 
        if self.get_icon: self.rewind_button.setIcon(self.get_icon("rewind_icon.svg"))
        self.rewind_button.setIconSize(player_icon_size)
        self.rewind_button.setObjectName("rewind_button")
        self.rewind_button.setToolTip("Retroceder (Ver Shortcuts)")
        self.rewind_button.clicked.connect(lambda: self.change_position(-5000))
        self.rewind_button.setProperty("iconOnlyButton", True)

        self.forward_button = QPushButton() 
        if self.get_icon: self.forward_button.setIcon(self.get_icon("forward_icon.svg"))
        self.forward_button.setIconSize(player_icon_size)
        self.forward_button.setObjectName("forward_button")
        self.forward_button.setToolTip("Avanzar (Ver Shortcuts)")
        self.forward_button.clicked.connect(lambda: self.change_position(5000))
        self.forward_button.setProperty("iconOnlyButton", True)

        self.detach_button = QPushButton(" Separar")
        if self.get_icon: self.detach_button.setIcon(self.get_icon("detach_video_icon.svg"))
        self.detach_button.setIconSize(player_icon_size)
        self.detach_button.setObjectName("detach_button")
        self.detach_button.setToolTip("Separar/Adjuntar Video")
        self.detach_button.clicked.connect(self.detach_widget)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("position_slider")
        self.slider.sliderMoved.connect(self.set_position_from_slider_move)

        self.volume_button = QPushButton() 
        if self.get_icon: self.volume_button.setIcon(self.volume_up_icon)
        self.volume_button.setIconSize(player_icon_size)
        self.volume_button.setObjectName("volume_button")
        self.volume_button.setToolTip("Volumen")
        self.volume_button.clicked.connect(self.toggle_volume_slider_visibility)
        self.volume_button.setProperty("iconOnlyButton", True)

        self.volume_slider_vertical = QSlider(Qt.Orientation.Vertical)
        self.volume_slider_vertical.setRange(0, 100)
        self.volume_slider_vertical.setObjectName("volume_slider_vertical")
        self.volume_slider_vertical.setVisible(False)
        self.volume_slider_vertical.valueChanged.connect(self.set_volume_from_slider_value)

        self.time_code_label = QLabel("00:00:00:00")
        self.time_code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_code_label.setObjectName("time_code_label")
        time_code_font = QFont("Arial", 18, QFont.Weight.Bold)
        self.time_code_label.setFont(time_code_font)
        
        font_metrics_height = QFontMetrics(time_code_font).height()
        target_height = int(font_metrics_height * 1.5)
        self.time_code_label.setFixedHeight(target_height)
        self.time_code_label.mouseDoubleClickEvent = self.edit_time_code_label 

        self.time_code_editor = TimeCodeEdit(self)
        self.time_code_editor.setFont(time_code_font) 
        self.time_code_editor.setFixedHeight(target_height)
        self.time_code_editor.setVisible(False)
        self.time_code_editor.editingFinished.connect(self.finish_edit_time_code)

        self.in_button = QPushButton(" IN")
        if self.get_icon: self.in_button.setIcon(self.get_icon("mark_in_icon.svg"))
        self.in_button.setIconSize(player_icon_size)
        self.in_button.setObjectName("in_button")
        self.in_button.setToolTip("Marcar IN (Ver Shortcuts)")
        self.in_button.clicked.connect(self.mark_in)

        self.out_button = QPushButton(" OUT")
        if self.get_icon: self.out_button.setIcon(self.get_icon("mark_out_icon.svg"))
        self.out_button.setIconSize(player_icon_size)
        self.out_button.setObjectName("out_button")
        self.out_button.setToolTip("Marcar OUT (Mantener - Ver Shortcuts)")
        self.out_button.pressed.connect(self.handle_out_button_pressed)
        self.out_button.released.connect(self.handle_out_button_released)

        self.me_toggle_checkbox = QCheckBox("Usar M+E")
        self.me_toggle_checkbox.setObjectName("me_toggle_checkbox")
        self.me_toggle_checkbox.setToolTip("Alternar entre audio original (V.O.) y Música+Efectos (M+E)")
        self.me_toggle_checkbox.stateChanged.connect(self.toggle_me_audio_source)
        self.me_toggle_checkbox.setEnabled(False)

        self.subtitle_toggle_checkbox = QCheckBox("Subtítulos")
        self.subtitle_toggle_checkbox.setObjectName("subtitle_toggle_checkbox")
        self.subtitle_toggle_checkbox.setToolTip("Mostrar/Ocultar subtítulos del guion")
        self.subtitle_toggle_checkbox.stateChanged.connect(self._handle_subtitle_toggle)

        # --- CONTROLES DE ONDA DE AUDIO ---
        self.waveform_toggle_checkbox = QCheckBox("Onda")
        self.waveform_toggle_checkbox.setObjectName("waveform_toggle_checkbox")
        self.waveform_toggle_checkbox.setToolTip("Mostrar/Ocultar visualización de onda de audio")
        self.waveform_toggle_checkbox.stateChanged.connect(self._handle_waveform_toggle)

        self.audio_track_combo = QComboBox()
        self.audio_track_combo.setToolTip("Seleccionar pista de audio")
        self.audio_track_combo.setFixedWidth(120)
        self.audio_track_combo.setVisible(False) 
        self.audio_track_combo.currentIndexChanged.connect(self._handle_audio_track_change)

        # --- SELECTOR DE CALIDAD ---
        self.quality_combo = QComboBox()
        self.quality_combo.setToolTip("Calidad de la onda (Muestras/segundo)")
        self.quality_combo.setFixedWidth(100)
        
        # Opciones de calidad (Nombre, Valor Hz)
        self.quality_combo.addItem("Baja (100)", 100)
        self.quality_combo.addItem("Media (400)", 400)
        self.quality_combo.addItem("Alta (1000)", 1000)
        self.quality_combo.addItem("Ultra (3000)", 3000)
        self.quality_combo.addItem("Mega (5000)", 5000)   # NUEVO
        self.quality_combo.addItem("Extrema (10000)", 10000) # NUEVO
        
        self.quality_combo.setCurrentIndex(2) # Por defecto Alta (1000)
        self.quality_combo.setVisible(False)
        self.quality_combo.currentIndexChanged.connect(self._handle_quality_change)
        # ---------------------------------

        self.subtitle_source_selector = QComboBox()
        self.subtitle_source_selector.setObjectName("subtitle_source_selector")
        self.subtitle_source_selector.addItems(["Diálogo", "Euskera"])
        self.subtitle_source_selector.setToolTip("Seleccionar la columna de origen para los subtítulos")
        self.subtitle_source_selector.setEnabled(False)
        self.subtitle_source_selector.currentIndexChanged.connect(self._handle_subtitle_source_change)
    
    def setup_layouts(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.time_code_display_stack = QStackedLayout()
        self.time_code_display_stack.addWidget(self.time_code_label)
        self.time_code_display_stack.addWidget(self.time_code_editor)
        self.time_code_display_stack.setCurrentIndex(0)

        top_info_layout_container = QWidget()
        top_info_layout_container.setLayout(self.time_code_display_stack)
        
        layout.addWidget(top_info_layout_container)

        self.video_splitter = QSplitter(Qt.Orientation.Vertical)
        self.video_splitter.addWidget(self.video_widget)
        self.video_splitter.addWidget(self.waveform_widget)
        self.video_splitter.addWidget(self.subtitle_container)
        self.video_splitter.setSizes([700, 80, 120]) 
        self.video_splitter.setCollapsible(0, False) 
        self.video_splitter.setCollapsible(1, True) 
        self.video_splitter.setCollapsible(2, True)
        layout.addWidget(self.video_splitter, 1)

        layout.addWidget(self.slider) 

        self.video_controls_bar_widget = QWidget()
        self.video_controls_bar_widget.setObjectName("video_controls_bar") 

        video_buttons_internal_layout = QHBoxLayout(self.video_controls_bar_widget)
        video_buttons_internal_layout.setContentsMargins(0, 0, 0, 0)
        video_buttons_internal_layout.setSpacing(6) 

        video_buttons_internal_layout.addWidget(self.detach_button)
        video_buttons_internal_layout.addWidget(self.play_button)
        video_buttons_internal_layout.addWidget(self.rewind_button)
        video_buttons_internal_layout.addWidget(self.forward_button)
        video_buttons_internal_layout.addWidget(self.in_button)
        video_buttons_internal_layout.addWidget(self.out_button)
        video_buttons_internal_layout.addWidget(self.me_toggle_checkbox) 
        video_buttons_internal_layout.addWidget(self.subtitle_toggle_checkbox)
        
        video_buttons_internal_layout.addWidget(self.waveform_toggle_checkbox)
        video_buttons_internal_layout.addWidget(self.audio_track_combo)
        video_buttons_internal_layout.addWidget(self.quality_combo) # Añadido al layout
        
        video_buttons_internal_layout.addWidget(self.subtitle_source_selector)
        video_buttons_internal_layout.addStretch(1) 
        video_buttons_internal_layout.addWidget(self.volume_button)
        video_buttons_internal_layout.addWidget(self.volume_slider_vertical)

        layout.addWidget(self.video_controls_bar_widget)
        self.setLayout(layout)

    def _handle_waveform_toggle(self, state: int):
        is_checked = (Qt.CheckState(state) == Qt.CheckState.Checked)
        self.waveform_widget.setVisible(is_checked)
        self.audio_track_combo.setVisible(is_checked)
        self.quality_combo.setVisible(is_checked)
        
        if is_checked:
            if not self.waveform_widget.has_data() and not self.media_player.source().isEmpty():
                file_path = self.media_player.source().toLocalFile()
                if file_path:
                    self.waveform_widget.scan_audio_tracks(file_path)

    def populate_audio_tracks(self, tracks):
        self.audio_track_combo.blockSignals(True)
        self.audio_track_combo.clear()
        
        if tracks:
            self.audio_track_combo.addItems(tracks)
            self.audio_track_combo.setEnabled(True)
            self.audio_track_combo.setCurrentIndex(0)
            self.waveform_widget.load_audio_track(0)
        else:
            self.audio_track_combo.addItem("Sin Audio")
            self.audio_track_combo.setEnabled(False)
            
        self.audio_track_combo.blockSignals(False)

    def _handle_audio_track_change(self, index):
        if index >= 0:
            self.waveform_widget.load_audio_track(index)

    def _handle_quality_change(self, index):
        """Cambia la calidad de la onda."""
        quality_hz = self.quality_combo.currentData()
        if quality_hz:
            self.waveform_widget.set_sample_rate(quality_hz)

    def _handle_subtitle_toggle(self, state: int):
        is_checked = (Qt.CheckState(state) == Qt.CheckState.Checked)
        self.subtitle_source_selector.setEnabled(is_checked)
        self.subtitle_container.setVisible(is_checked)

        if is_checked:
            self._handle_subtitle_source_change() 
            self._trigger_subtitle_update(self.media_player.position())
        else:
            self.subtitle_display_label.setText("")

    def _handle_subtitle_source_change(self):
        if not self.table_window_ref:
            return
        selected_text = self.subtitle_source_selector.currentText()
        if selected_text == "Diálogo":
            self.subtitle_source_column = 'DIÁLOGO'
        elif selected_text == "Euskera":
            self.subtitle_source_column = 'EUSKERA' 
        self.table_window_ref.trigger_recache_with_source(self.subtitle_source_column)

    def _refresh_subtitle_timeline(self):
        if not self.table_window_ref:
            self.subtitle_timeline = []
            self.subtitle_start_times = []
            return
        self.subtitle_timeline = self.table_window_ref.get_subtitle_timeline()
        self.subtitle_start_times = [item[0] for item in self.subtitle_timeline]
        self.current_subtitle_timeline_idx = -1
        self._trigger_subtitle_update(self.media_player.position())

    def _trigger_subtitle_update(self, position_ms: int):
        if not self.subtitle_toggle_checkbox.isChecked() or not self.subtitle_timeline:
            return
        idx = bisect.bisect_right(self.subtitle_start_times, position_ms)
        found_subtitle_idx = -1
        text_to_display = ""
        if idx > 0:
            candidate_idx = idx - 1
            start_ms, end_ms, dialogue = self.subtitle_timeline[candidate_idx]
            if start_ms <= position_ms < end_ms:
                found_subtitle_idx = candidate_idx
                text_to_display = dialogue
        if self.current_subtitle_timeline_idx != found_subtitle_idx:
            self.subtitle_display_label.setText(text_to_display)
            self.current_subtitle_timeline_idx = found_subtitle_idx

    def load_video(self, video_path: str) -> None:
        try:
            if not os.path.exists(video_path):
                QMessageBox.warning(self, "Error", f"Archivo de video no encontrado: {video_path}")
                return
            media_url = QUrl.fromLocalFile(video_path)
            if media_url.isEmpty() or not media_url.isValid():
                 QMessageBox.warning(self, "Error", f"No se pudo crear una URL válida para: {video_path}")
                 return
            
            self.media_player.setSource(media_url)

            self.audio_track_combo.clear()
            self.audio_track_combo.setVisible(self.waveform_toggle_checkbox.isChecked())
            self.quality_combo.setVisible(self.waveform_toggle_checkbox.isChecked())

            if self.waveform_toggle_checkbox.isChecked():
                self.waveform_widget.scan_audio_tracks(video_path)
            else:
                self.waveform_widget.clear()
                self.waveform_widget.current_video_path = video_path 

            if self.me_player:
                self.me_player.setSource(QUrl()) 
            self.me_toggle_checkbox.setEnabled(False)
            self.me_toggle_checkbox.setChecked(False) 
            self.use_me_audio = False
            
            audio_out = self.media_player.audioOutput()
            if not audio_out:
                if not self._audio_output_handler: self._audio_output_handler = QAudioOutput()
                self.media_player.setAudioOutput(self._audio_output_handler)
                audio_out = self.media_player.audioOutput()

            if audio_out:
                if not getattr(audio_out, '_volume_signal_connected_vpw', False):
                    audio_out.volumeChanged.connect(self.update_volume_slider_display)
                    setattr(audio_out, '_volume_signal_connected_vpw', True)
                self.volume_slider_vertical.setValue(int(self.user_volume_float * 100))

            self._update_audio_outputs() 
            self.media_player.play()
            self._refresh_subtitle_timeline()
        except Exception as e: QMessageBox.critical(self, "Error Crítico", f"Error crítico al cargar el video: {str(e)}")

    def load_me_file(self, audio_path: str) -> None:
        try:
            if not os.path.exists(audio_path):
                QMessageBox.warning(self, "Error", f"Archivo de audio M+E no encontrado: {audio_path}")
                return
            media_url = QUrl.fromLocalFile(audio_path)
            if media_url.isEmpty() or not media_url.isValid():
                QMessageBox.warning(self, "Error", f"No se pudo crear una URL válida para M+E: {audio_path}")
                return

            if not self.me_player: 
                self.me_player = QMediaPlayer()
                if not self.me_player.audioOutput():
                    self._me_audio_output_handler = QAudioOutput()
                    self.me_player.setAudioOutput(self._me_audio_output_handler)
            
            self.me_player.setSource(media_url)
            if not self.media_player.source().isEmpty():
                self.me_player.setPosition(self.media_player.position())
                if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    if self.use_me_audio: 
                        self.me_player.play()
                else:
                    self.me_player.pause()

            self.me_toggle_checkbox.setEnabled(True)
            self._update_audio_outputs() 
            QMessageBox.information(self, "M+E Cargado", f"Archivo M+E '{os.path.basename(audio_path)}' cargado.")

        except Exception as e:
            QMessageBox.critical(self, "Error Crítico", f"Error crítico al cargar el audio M+E: {str(e)}")
            self.me_toggle_checkbox.setEnabled(False)
            if self.me_player:
                self.me_player.setSource(QUrl())

    def toggle_me_audio_source(self, state: int) -> None:
        self.use_me_audio = (Qt.CheckState(state) == Qt.CheckState.Checked)
        self._update_audio_outputs()

    def _update_audio_outputs(self) -> None:
        main_audio = self.media_player.audioOutput()
        if not main_audio: 
            return

        me_player_ready_for_audio = (
            self.me_player is not None and
            not self.me_player.source().isEmpty() and
            self.me_player.audioOutput() is not None
        )
        me_audio = self.me_player.audioOutput() if me_player_ready_for_audio else None

        if self.use_me_audio and me_player_ready_for_audio and me_audio:
            main_audio.setMuted(True)
            me_audio.setMuted(False)
            me_audio.setVolume(self.user_volume_float)

            if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.me_player.play()
                self.me_player.setPosition(self.media_player.position())
            else:
                self.me_player.pause()
                self.me_player.setPosition(self.media_player.position())
        else:
            main_audio.setMuted(False)
            main_audio.setVolume(self.user_volume_float)

            if me_player_ready_for_audio and me_audio:
                me_audio.setMuted(True)
                self.me_player.pause()
                
    def on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._update_audio_outputs() 
            if self.media_player.audioOutput():
                self.volume_slider_vertical.setValue(int(self.user_volume_float * 100))
            self._refresh_subtitle_timeline()

        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.media_player.setPosition(0)
            self.media_player.pause()
            if self.me_player and not self.me_player.source().isEmpty():
                self.me_player.setPosition(0)
                self.me_player.pause()
            self.subtitle_display_label.setText("") 
            self.current_subtitle_timeline_idx = -1
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            QMessageBox.warning(self, "Error de Medio", "El archivo de video es inválido o no soportado.")
            self.subtitle_display_label.setText("")
            self._refresh_subtitle_timeline()
        elif status == QMediaPlayer.MediaStatus.NoMedia: 
            self.time_code_label.setText("00:00:00:00")
            self.slider.setValue(0)
            if self.me_player:
                self.me_player.setSource(QUrl())
            self.me_toggle_checkbox.setEnabled(False)
            self.me_toggle_checkbox.setChecked(False)
            self.use_me_audio = False
            self.subtitle_display_label.setText("") 
            self._refresh_subtitle_timeline()
            self._update_audio_outputs()

    def on_media_error(self, error_code: QMediaPlayer.Error, error_string: str) -> None:
        if error_code != QMediaPlayer.Error.NoError:
            msg = error_string if error_string else f"Error desconocido en el reproductor (código: {error_code})."
            QMessageBox.warning(self, "Error de Reproducción", msg)

    def set_position_public(self, milliseconds: int) -> None:
        try:
            duration = self.media_player.duration()
            new_pos = 0
            if duration > 0:
                new_pos = max(0, min(milliseconds, duration))
            elif milliseconds == 0:
                new_pos = 0
            else: 
                new_pos = max(0, milliseconds)

            self.media_player.setPosition(new_pos)
            if self.me_player and not self.me_player.source().isEmpty():
                self.me_player.setPosition(new_pos)
            self._trigger_subtitle_update(new_pos)
        except Exception as e: QMessageBox.warning(self, "Error", f"Error al establecer la posición del video: {str(e)}")
        
    def detach_widget(self) -> None:
        self.detach_requested.emit(self)

    def toggle_volume_slider_visibility(self) -> None:
        self.volume_slider_vertical.setVisible(not self.volume_slider_vertical.isVisible())

    def update_fonts(self, font_size: int) -> None:
        base_font = QFont(); base_font.setPointSize(font_size)
        button_attribute_names = [
            "play_button", "rewind_button", "forward_button", "detach_button",
            "in_button", "out_button", "volume_button"
        ]
        controls_to_update = [getattr(self, name) for name in button_attribute_names if hasattr(self, name)]
        
        for control in controls_to_update:
            if isinstance(control, QPushButton):
                 control.setFont(base_font)
        
        if hasattr(self, 'time_code_label') and self.time_code_label:
            tc_font = QFont("Arial", max(font_size + 6, 10), QFont.Weight.Bold)
            self.time_code_label.setFont(tc_font)
            if hasattr(self, 'time_code_editor') and self.time_code_editor:
                self.time_code_editor.setFont(tc_font)

            font_metrics_height = QFontMetrics(tc_font).height()
            target_height = int(font_metrics_height * 1.5)
            self.time_code_label.setFixedHeight(target_height)
            if hasattr(self, 'time_code_editor') and self.time_code_editor:
                self.time_code_editor.setFixedHeight(target_height)

        if hasattr(self, 'subtitle_display_label'):
             subtitle_font = QFont()
             subtitle_font.setPointSize(max(font_size + 3, 14))
             subtitle_font.setBold(True)
             self.subtitle_display_label.setFont(subtitle_font)
             
             font_metrics = QFontMetrics(subtitle_font)
             line_height = font_metrics.height()
             
             layout_margins = self.subtitle_container.layout().contentsMargins()
             top_margin = layout_margins.top()
             bottom_margin = layout_margins.bottom()
             
             min_height = (line_height * 5) + top_margin + bottom_margin
             self.subtitle_container.setMinimumHeight(min_height)

             self.resizeEvent(None) 

    def edit_time_code_label(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            current_tc = self.time_code_label.text()
            self.time_code_editor.set_time_code(current_tc)
            self.time_code_editor.selectAll()
            self.time_code_display_stack.setCurrentWidget(self.time_code_editor)
            self.time_code_editor.setFocus()
            self.display_update_timer.stop()

    def finish_edit_time_code(self) -> None:
        new_tc_str = self.time_code_editor.get_time_code()
        
        try:
            parts = new_tc_str.split(':')
            if len(parts) != 4 or not all(len(p) == 2 and p.isdigit() for p in parts):
                raise ValueError("Formato de Timecode inválido.")
            
            h, m, s, f = map(int, parts)
            
            if not (0 <= m < 60 and 0 <= s < 60 and 0 <= f < self.FPS_RATE):
                raise ValueError(f"Valores de tiempo inválidos (MM:SS deben ser < 60, FF < {int(self.FPS_RATE)}).")

            msecs_per_frame = 1000.0 / self.FPS_RATE
            target_msecs = int(round(((h * 3600 + m * 60 + s) * 1000) + (f * msecs_per_frame)))

            duration_msecs = self.media_player.duration()

            position_changed = False
            if duration_msecs > 0 and (target_msecs < 0 or target_msecs > duration_msecs):
                QMessageBox.warning(self, "Tiempo Inválido",
                                    f"El tiempo '{new_tc_str}' está fuera del rango del vídeo (00:00:00:00 a {self.convert_milliseconds_to_time_code_str(duration_msecs)}).")
            elif not self.media_player.isSeekable() and target_msecs != self.media_player.position():
                 QMessageBox.warning(self, "No Modificable", "El vídeo actual no permite cambiar la posición de esta manera.")
            elif self.media_player.isSeekable() or target_msecs == self.media_player.position(): 
                self.media_player.setPosition(target_msecs)
                if self.me_player and not self.me_player.source().isEmpty():
                    self.me_player.setPosition(target_msecs)
                position_changed = True
            
            if position_changed: 
                self._trigger_subtitle_update(target_msecs)


        except ValueError as e:
            QMessageBox.warning(self, "Formato Inválido", str(e))
        except Exception as e_gen:
            QMessageBox.critical(self, "Error", f"Error al procesar el timecode: {e_gen}")
        finally:
            self.time_code_display_stack.setCurrentWidget(self.time_code_label)
            self.display_update_timer.start()

    def toggle_play(self) -> None:
        current_state = self.media_player.playbackState()
        if self.media_player.source().isEmpty() and current_state != QMediaPlayer.PlaybackState.PlayingState:
            return
            
        if current_state == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            if self.me_player and not self.me_player.source().isEmpty():
                self.me_player.pause()
        else:
            self.media_player.play()
            if self.me_player and not self.me_player.source().isEmpty() and self.use_me_audio:
                self.me_player.play()
                self.me_player.setPosition(self.media_player.position())

    def change_position(self, change_ms: int) -> None:
        if self.media_player.duration() <= 0 and self.media_player.source().isEmpty(): return
        current_pos = self.media_player.position()
        new_position = current_pos + change_ms
        
        if self.media_player.duration() > 0 :
            new_position = max(0, min(new_position, self.media_player.duration()))
        else:
            new_position = max(0, new_position)
        self.media_player.setPosition(new_position)
        if self.me_player and not self.me_player.source().isEmpty():
            self.me_player.setPosition(new_position)
        self._trigger_subtitle_update(new_position)

    def set_position_from_slider_move(self, position: int) -> None:
        if self.media_player.duration() <= 0 and position > 0:
            self.slider.blockSignals(True)
            current_player_pos = self.media_player.position()
            self.slider.setValue(current_player_pos if current_player_pos >= 0 else 0)
            self.slider.blockSignals(False)
            return
        if self.media_player.isSeekable():
            self.media_player.setPosition(position)
            if self.me_player and not self.me_player.source().isEmpty():
                self.me_player.setPosition(position)
            self._trigger_subtitle_update(position)

    def set_volume_from_slider_value(self, volume_percent: int) -> None:
        self.user_volume_float = volume_percent / 100.0
        self._update_audio_outputs()

    def update_volume_slider_display(self, volume_float: float):
        volume_percent_user = int(self.user_volume_float * 100)
        self.volume_slider_vertical.blockSignals(True)
        self.volume_slider_vertical.setValue(volume_percent_user)
        self.volume_slider_vertical.blockSignals(False)

    def update_play_button_icon(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setIcon(self.pause_icon); self.play_button.setToolTip("Pausar (Ver Shortcuts)")
        else:
            self.play_button.setIcon(self.play_icon); self.play_button.setToolTip("Reproducir (Ver Shortcuts)")

    def update_slider_position(self, position: int) -> None:
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(position)
            self.slider.blockSignals(False)

    def update_slider_range(self, duration: int) -> None:
        self.slider.setRange(0, duration if duration > 0 else 0)

    def _convert_ms_to_tc_parts(self, position_ms: int) -> tuple[int, int, int, int]:
        hours, minutes, seconds, frames = 0, 0, 0, 0
        if position_ms >= 0:
            msecs_per_frame = 1000.0 / self.FPS_RATE
            total_seconds, msecs = divmod(position_ms, 1000)
            hours, rem_seconds = divmod(total_seconds, 3600)
            minutes, seconds = divmod(rem_seconds, 60)
            frames = int(round(msecs / msecs_per_frame))
            if frames >= self.FPS_RATE: frames = int(self.FPS_RATE - 1)
        return int(hours), int(minutes), int(seconds), int(frames)

    def update_time_code_display(self) -> None:
        if self.time_code_display_stack.currentWidget() == self.time_code_label:
            position = self.media_player.position()
            h, m, s, f = self._convert_ms_to_tc_parts(position)
            self.time_code_label.setText(f"{h:02}:{m:02}:{s:02}:{f:02}")

    def handle_out_button_pressed(self):
        if not self.out_timer.isActive():
            self.out_timer.start()
            self.mark_out_continuous()

    def handle_out_button_released(self):
        if self.out_timer.isActive():
            self.out_timer.stop()
            self.out_released.emit() 

    def mark_in(self) -> None:
        try:
            position_ms = self.media_player.position()
            self.in_out_signal.emit("IN", position_ms)
        except Exception as e: QMessageBox.warning(self, "Error", f"Error en mark_in: {str(e)}")

    def mark_out_continuous(self) -> None:
        try:
            position_ms = self.media_player.position()
            self.in_out_signal.emit("OUT", position_ms)
        except Exception as e: print(f"Error en mark_out_continuous (timer): {str(e)}")

    def convert_milliseconds_to_time_code_str(self, ms: int) -> str:
        if ms < 0: ms = 0
        h, m, s, f = self._convert_ms_to_tc_parts(ms)
        return f"{h:02}:{m:02}:{s:02}:{f:02}"

    def setup_timers(self) -> None:
        self.display_update_timer = QTimer(self)
        self.display_update_timer.setInterval(int(1000 / 30)) 
        self.display_update_timer.timeout.connect(self.update_time_code_display)
        self.display_update_timer.start()

    def update_time_code_display(self) -> None:
        if self.time_code_display_stack.currentWidget() == self.time_code_label:
            position = self.media_player.position()
            h, m, s, f = self._convert_ms_to_tc_parts(position)
            self.time_code_label.setText(f"{h:02}:{m:02}:{s:02}:{f:02}")

    def update_key_listeners(self):
        pass