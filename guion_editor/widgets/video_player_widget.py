# guion_editor/widgets/video_player_widget.py
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QSlider, QLabel,
    QMessageBox, QHBoxLayout, QStackedLayout, QCheckBox
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal, QSize, QKeyCombination
from PyQt6.QtGui import QKeySequence, QFont, QIcon, QKeyEvent, QFontMetrics, QMouseEvent

from .time_code_edit import TimeCodeEdit

class VideoPlayerWidget(QWidget):
    in_out_signal = pyqtSignal(str, int)
    out_released = pyqtSignal()
    detach_requested = pyqtSignal(QWidget)

    FPS_RATE = 25.0 # Definir como atributo de clase o instancia para consistencia

    def __init__(self, get_icon_func=None, main_window=None):
        super().__init__()
        self._audio_output_handler = None
        self.get_icon = get_icon_func
        self.main_window = main_window
        self.f6_key_pressed_internally = False

        self._me_audio_output_handler = None # For M+E audio
        self.me_player = None # Player for M+E
        self.use_me_audio = False # Flag to indicate M+E usage
        self.user_volume_float = 1.0 # Store user's desired volume (0.0 to 1.0)

        if self.get_icon:
            self.play_icon = self.get_icon("play_icon.svg")
            self.pause_icon = self.get_icon("pause_icon.svg")
            self.volume_up_icon = self.get_icon("volume_up_icon.svg")
            self.volume_off_icon = self.get_icon("volume_off_icon.svg")
            self.load_audio_icon = self.get_icon("load_audio_icon.svg") # New icon

        else:
            self.play_icon, self.pause_icon, self.volume_up_icon, self.volume_off_icon, self.load_audio_icon = QIcon(), QIcon(), QIcon(), QIcon(), QIcon()

        self.init_ui()
        self.setup_timers()
        
        self.out_timer = QTimer(self)
        self.out_timer.setInterval(40) 
        self.out_timer.timeout.connect(self.mark_out_continuous)
        self.out_timer.setSingleShot(False)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def init_ui(self) -> None:
        self.media_player = QMediaPlayer()
        if not self.media_player.audioOutput():
            self._audio_output_handler = QAudioOutput()
            self.media_player.setAudioOutput(self._audio_output_handler)
        
        self.setup_controls()

        audio_output = self.media_player.audioOutput()
        if audio_output:
            # Make sure this connection is only made once or is robust to multiple calls
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

        self.media_player.playbackStateChanged.connect(self.update_play_button_icon)
        self.media_player.positionChanged.connect(self.update_slider_position)
        self.media_player.durationChanged.connect(self.update_slider_range)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.media_player.errorOccurred.connect(self.on_media_error)

        self.setup_layouts()
        # self.setup_timers() # Movido a __init__ para asegurar que display_update_timer se cree antes

    def setup_controls(self) -> None:
        # Tamaño estándar para los iconos dentro de los botones del reproductor
        player_icon_size = QSize(20, 20) # Mantener el tamaño original o ajustarlo
        # La altura objetivo para los botones será definida en CSS, ej: 36px

        self.play_button = QPushButton() 
        if self.get_icon: self.play_button.setIcon(self.play_icon) # play_icon ya debería estar cargado
        self.play_button.setIconSize(player_icon_size)
        # self.play_button.setFixedSize(icon_only_button_size) # <--- ELIMINAR
        self.play_button.setObjectName("play_button")
        self.play_button.setToolTip("Reproducir/Pausar (Ver Shortcuts)")
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setProperty("iconOnlyButton", True) # Indicar que es solo icono

        self.rewind_button = QPushButton() 
        if self.get_icon: self.rewind_button.setIcon(self.get_icon("rewind_icon.svg"))
        self.rewind_button.setIconSize(player_icon_size)
        # self.rewind_button.setFixedSize(icon_only_button_size) # <--- ELIMINAR
        self.rewind_button.setObjectName("rewind_button")
        self.rewind_button.setToolTip("Retroceder (Ver Shortcuts)")
        self.rewind_button.clicked.connect(lambda: self.change_position(-5000))
        self.rewind_button.setProperty("iconOnlyButton", True)

        self.forward_button = QPushButton() 
        if self.get_icon: self.forward_button.setIcon(self.get_icon("forward_icon.svg"))
        self.forward_button.setIconSize(player_icon_size)
        # self.forward_button.setFixedSize(icon_only_button_size) # <--- ELIMINAR
        self.forward_button.setObjectName("forward_button")
        self.forward_button.setToolTip("Avanzar (Ver Shortcuts)")
        self.forward_button.clicked.connect(lambda: self.change_position(5000))
        self.forward_button.setProperty("iconOnlyButton", True)

        self.detach_button = QPushButton(" Separar") # Este tiene texto
        if self.get_icon: self.detach_button.setIcon(self.get_icon("detach_video_icon.svg"))
        self.detach_button.setIconSize(player_icon_size) # El icono es 20x20
        self.detach_button.setObjectName("detach_button")
        self.detach_button.setToolTip("Separar/Adjuntar Video")
        self.detach_button.clicked.connect(self.detach_widget)
        # No necesita setProperty("iconOnlyButton", True)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("position_slider")
        self.slider.sliderMoved.connect(self.set_position_from_slider_move)

        self.volume_button = QPushButton() 
        if self.get_icon: self.volume_button.setIcon(self.volume_up_icon) # volume_up_icon ya cargado
        self.volume_button.setIconSize(player_icon_size)
        # self.volume_button.setFixedSize(icon_only_button_size) # <--- ELIMINAR
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
        time_code_font = QFont("Arial", 18, QFont.Weight.Bold) # Definir la fuente una vez
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

        self.in_button = QPushButton(" IN") # Tiene texto
        if self.get_icon: self.in_button.setIcon(self.get_icon("mark_in_icon.svg"))
        self.in_button.setIconSize(player_icon_size)
        self.in_button.setObjectName("in_button")
        self.in_button.setToolTip("Marcar IN (Ver Shortcuts)")
        self.in_button.clicked.connect(self.mark_in)

        self.out_button = QPushButton(" OUT") # Tiene texto
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
        self.me_toggle_checkbox.setEnabled(False) # Disabled until M+E is loaded
    
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
        layout.addWidget(self.video_widget, 1) # video_widget ocupa el espacio sobrante
        layout.addWidget(self.slider) 

        # --- Crear el QWidget contenedor para los controles del video ---
        self.video_controls_bar_widget = QWidget()
        self.video_controls_bar_widget.setObjectName("video_controls_bar") # Para el CSS

        # Layout para *dentro* de video_controls_bar_widget
        video_buttons_internal_layout = QHBoxLayout(self.video_controls_bar_widget)
        video_buttons_internal_layout.setContentsMargins(0, 0, 0, 0)
        video_buttons_internal_layout.setSpacing(6) # Espacio entre botones del reproductor

        # Añadir botones al layout interno
        video_buttons_internal_layout.addWidget(self.detach_button)
        video_buttons_internal_layout.addWidget(self.play_button)
        video_buttons_internal_layout.addWidget(self.rewind_button)
        video_buttons_internal_layout.addWidget(self.forward_button)
        video_buttons_internal_layout.addWidget(self.in_button)
        video_buttons_internal_layout.addWidget(self.out_button)
        video_buttons_internal_layout.addWidget(self.me_toggle_checkbox) 
        video_buttons_internal_layout.addStretch(1) # Empuja el botón de volumen a la derecha
        video_buttons_internal_layout.addWidget(self.volume_button)
        video_buttons_internal_layout.addWidget(self.volume_slider_vertical) # Este se muestra/oculta

        # Añadir el widget contenedor al layout principal
        layout.addWidget(self.video_controls_bar_widget)
        self.setLayout(layout)


    def update_key_listeners(self):
        pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self.main_window or not hasattr(self.main_window, 'mark_out_hold_key_sequence'):
            super().keyPressEvent(event)
            return

        current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence
            
        key_match = False
        if not current_mark_out_shortcut.isEmpty():
            if event.keyCombination() == current_mark_out_shortcut[0]: 
                key_match = True
        
        if key_match and not event.isAutoRepeat() and not self.f6_key_pressed_internally:
            self.f6_key_pressed_internally = True
            self.handle_out_button_pressed() 
            event.accept()
            return
        
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if not self.main_window or not hasattr(self.main_window, 'mark_out_hold_key_sequence'):
            super().keyReleaseEvent(event)
            return

        current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence

        key_match = False
        if not current_mark_out_shortcut.isEmpty():
            if event.keyCombination() == current_mark_out_shortcut[0]:
                key_match = True
            
        if key_match and not event.isAutoRepeat() and self.f6_key_pressed_internally:
            self.f6_key_pressed_internally = False
            self.handle_out_button_released()
            event.accept()
            return
        
        super().keyReleaseEvent(event)

    def setup_timers(self) -> None:
        self.display_update_timer = QTimer(self)
        self.display_update_timer.setInterval(int(1000 / 30)) 
        self.display_update_timer.timeout.connect(self.update_time_code_display)
        self.display_update_timer.start()
        
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
                self.me_player.setPosition(self.media_player.position()) # Ensure sync

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
                # self.user_volume_float is the master, audio_out.volume() reflects it after _update_audio_outputs
                self.volume_slider_vertical.setValue(int(self.user_volume_float * 100))


            self._update_audio_outputs() # Ensure correct volume/mute applied
            self.media_player.play()
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
        if not main_audio: # Si la salida de audio principal no está lista, no podemos hacer nada.
            return

        # Determinar si el reproductor M+E está listo para usarse (tiene fuente y salida de audio)
        me_player_ready_for_audio = (
            self.me_player is not None and
            not self.me_player.source().isEmpty() and
            self.me_player.audioOutput() is not None
        )
        me_audio = self.me_player.audioOutput() if me_player_ready_for_audio else None

        if self.use_me_audio and me_player_ready_for_audio and me_audio:
            # Modo M+E activo y reproductor M+E listo.
            main_audio.setMuted(True)
            me_audio.setMuted(False)
            me_audio.setVolume(self.user_volume_float)

            # Sincronizar estado de reproducción
            if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.me_player.play()
                self.me_player.setPosition(self.media_player.position())
            else:
                self.me_player.pause()
                self.me_player.setPosition(self.media_player.position())
        else:
            # Modo V.O. (audio original) o M+E seleccionado pero no listo.
            main_audio.setMuted(False)
            main_audio.setVolume(self.user_volume_float) # Aplicar volumen al principal

            # Si el reproductor M+E está listo, asegurarse de que esté silenciado y pausado.
            if me_player_ready_for_audio and me_audio:
                me_audio.setMuted(True)
                self.me_player.pause() # Pausar ya que tiene fuente.
                # Opcional: mantener sincronizada la posición del M+E.
                # self.me_player.setPosition(self.media_player.position())

    def on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # Cuando un nuevo medio se carga en media_player, actualizamos el volumen
            # y la interfaz del slider para reflejar self.user_volume_float.
            self._update_audio_outputs() # Asegura que el volumen correcto se aplique
            if self.media_player.audioOutput():
                self.volume_slider_vertical.setValue(int(self.user_volume_float * 100))

        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.media_player.setPosition(0)
            self.media_player.pause()
            if self.me_player and not self.me_player.source().isEmpty():
                self.me_player.setPosition(0)
                self.me_player.pause()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            QMessageBox.warning(self, "Error de Medio", "El archivo de video es inválido o no soportado.")
        elif status == QMediaPlayer.MediaStatus.NoMedia: 
            self.time_code_label.setText("00:00:00:00")
            self.slider.setValue(0)
            if self.me_player:
                self.me_player.setSource(QUrl())
            self.me_toggle_checkbox.setEnabled(False)
            self.me_toggle_checkbox.setChecked(False)
            self.use_me_audio = False
            # Asegurarse que el volumen del reproductor principal (ahora sin medio) esté bien
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
        except Exception as e: QMessageBox.warning(self, "Error", f"Error al establecer la posición del video: {str(e)}")
        
    def detach_widget(self) -> None:
        self.detach_requested.emit(self)

    def toggle_volume_slider_visibility(self) -> None:
        self.volume_slider_vertical.setVisible(not self.volume_slider_vertical.isVisible())

    def update_fonts(self, font_size: int) -> None:
        base_font = QFont(); base_font.setPointSize(font_size)
        controls_to_update = [ self.play_button, self.rewind_button, self.forward_button, self.detach_button, self.in_button, self.out_button, self.volume_button ]
        for control_name_str in controls_to_update: # Iterar por nombres de atributo si son QPushButton
            control = getattr(self, control_name_str.objectName(), None) if hasattr(control_name_str, 'objectName') else getattr(self, control_name_str, None)

            if isinstance(control, QPushButton): # Asegurarse que es un botón
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

            if duration_msecs > 0 and (target_msecs < 0 or target_msecs > duration_msecs):
                QMessageBox.warning(self, "Tiempo Inválido",
                                    f"El tiempo '{new_tc_str}' está fuera del rango del vídeo (00:00:00:00 a {self.convert_milliseconds_to_time_code_str(duration_msecs)}).")
            elif not self.media_player.isSeekable() and target_msecs != self.media_player.position():
                 QMessageBox.warning(self, "No Modificable", "El vídeo actual no permite cambiar la posición de esta manera.")
            elif self.media_player.isSeekable() or target_msecs == self.media_player.position(): 
                self.media_player.setPosition(target_msecs)
                if self.me_player and not self.me_player.source().isEmpty():
                    self.me_player.setPosition(target_msecs)
            # Eliminado el else que mostraba "No Modificable" incorrectamente. Si es seekable, se hace. Si no, ya se advirtió.

        except ValueError as e:
            QMessageBox.warning(self, "Formato Inválido", str(e))
        except Exception as e_gen:
            QMessageBox.critical(self, "Error", f"Error al procesar el timecode: {e_gen}")
        finally:
            self.time_code_display_stack.setCurrentWidget(self.time_code_label)
            self.display_update_timer.start()

    def convert_milliseconds_to_time_code_str(self, ms: int) -> str:
        if ms < 0: ms = 0
        h, m, s, f = self._convert_ms_to_tc_parts(ms)
        return f"{h:02}:{m:02}:{s:02}:{f:02}"