import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QSlider, QLabel,
    QMessageBox, QHBoxLayout
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput # QAudioOutput es necesario
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QKeySequence, QFont, QShortcut, QFontMetrics, QIcon

class VideoPlayerWidget(QWidget):
    in_out_signal = pyqtSignal(str, int)
    out_released = pyqtSignal()
    detach_requested = pyqtSignal(QWidget)
    set_position_signal = pyqtSignal(int)

    def __init__(self, get_icon_func=None): # Añadir get_icon_func
        super().__init__()
        self._audio_output_handler = None
        self._shortcuts_list = []
        self.get_icon = get_icon_func # Guardar la función

        # --- Mover la definición de iconos aquí, ANTES de init_ui ---
        if self.get_icon:
            self.play_icon = self.get_icon("play_icon.svg")
            self.pause_icon = self.get_icon("pause_icon.svg")
            self.volume_up_icon = self.get_icon("volume_up_icon.svg")
            self.volume_off_icon = self.get_icon("volume_off_icon.svg") # Para Mute si lo implementas
        else: # Fallback si no se pasa get_icon
            self.play_icon = QIcon()
            self.pause_icon = QIcon()
            self.volume_up_icon = QIcon()
            self.volume_off_icon = QIcon()
        # --- Fin de la definición de iconos movida ---

        self.init_ui()
        self.load_stylesheet()
        self.setup_shortcuts()
        self.setup_timers()
        self.f6_pressed = False
        
        self.out_timer = QTimer(self)
        self.out_timer.setInterval(40)
        self.out_timer.timeout.connect(self.mark_out)
        self.out_timer.setSingleShot(False)

    def init_ui(self) -> None:
        self.media_player = QMediaPlayer()
        if not self.media_player.audioOutput():
            self._audio_output_handler = QAudioOutput()
            self.media_player.setAudioOutput(self._audio_output_handler)
        
        self.setup_controls() # Ahora setup_controls puede usar self.play_icon etc.

        if self.media_player.audioOutput():
            self.media_player.audioOutput().volumeChanged.connect(self.update_volume_slider)
            initial_volume_percent = int(self.media_player.audioOutput().volume() * 100)
            self.volume_slider_vertical.setValue(initial_volume_percent)
        else:
            if hasattr(self, 'volume_slider_vertical'):
                self.volume_slider_vertical.setValue(100)

        self.video_widget = QVideoWidget()
        self.media_player.setVideoOutput(self.video_widget)

        # La definición de self.play_icon, self.pause_icon etc. se movió al __init__
        # ya no es necesaria aquí.

        self.media_player.playbackStateChanged.connect(self.update_play_button)
        self.media_player.positionChanged.connect(self.update_slider)
        self.media_player.durationChanged.connect(self.update_slider_range)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.media_player.errorOccurred.connect(self.on_media_error)

        self.setup_layouts()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()


    def setup_controls(self) -> None:
        button_font = QFont()
        button_font.setPointSize(12) 

        icon_size = QSize(20, 20) 
        icon_only_button_size = QSize(36, 36) 

        self.play_button = QPushButton() 
        # self.play_icon ya está definido
        self.play_button.setIcon(self.play_icon) # Icono inicial
        self.play_button.setIconSize(icon_size)
        self.play_button.setFixedSize(icon_only_button_size)
        self.play_button.setObjectName("play_button")
        self.play_button.setToolTip("Reproducir/Pausar (F8)")
        self.play_button.clicked.connect(self.toggle_play)

        self.rewind_button = QPushButton() 
        if self.get_icon: # Añadir comprobación por si get_icon no está disponible
            self.rewind_button.setIcon(self.get_icon("rewind_icon.svg"))
        self.rewind_button.setIconSize(icon_size)
        self.rewind_button.setFixedSize(icon_only_button_size)
        self.rewind_button.setObjectName("rewind_button")
        self.rewind_button.setToolTip("Retroceder (F7)")
        self.rewind_button.clicked.connect(lambda: self.change_position(-5000))

        self.forward_button = QPushButton() 
        if self.get_icon: # Añadir comprobación
            self.forward_button.setIcon(self.get_icon("forward_icon.svg"))
        self.forward_button.setIconSize(icon_size)
        self.forward_button.setFixedSize(icon_only_button_size)
        self.forward_button.setObjectName("forward_button")
        self.forward_button.setToolTip("Avanzar (F9)")
        self.forward_button.clicked.connect(lambda: self.change_position(5000))

        self.detach_button = QPushButton(" Separar") 
        if self.get_icon: # Añadir comprobación
            self.detach_button.setIcon(self.get_icon("detach_video_icon.svg"))
        self.detach_button.setIconSize(icon_size)
        self.detach_button.setObjectName("detach_button")
        self.detach_button.clicked.connect(self.detach_widget)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("position_slider")
        self.slider.sliderMoved.connect(self.set_position)

        self.volume_button = QPushButton() 
        # self.volume_up_icon ya está definido
        self.volume_button.setIcon(self.volume_up_icon) # Icono inicial
        self.volume_button.setIconSize(icon_size)
        self.volume_button.setFixedSize(icon_only_button_size)
        self.volume_button.setObjectName("volume_button")
        self.volume_button.setToolTip("Volumen")
        self.volume_button.clicked.connect(self.toggle_volume_slider)

        self.volume_slider_vertical = QSlider(Qt.Orientation.Vertical)
        self.volume_slider_vertical.setRange(0, 100)
        self.volume_slider_vertical.setObjectName("volume_slider_vertical")
        self.volume_slider_vertical.setVisible(False)
        self.volume_slider_vertical.valueChanged.connect(self.set_volume_from_slider)

        self.time_code_label = QLabel("00:00:00:00")
        self.time_code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_code_label.setObjectName("time_code_label")
        time_code_font = QFont("Arial", 18)
        self.time_code_label.setFont(time_code_font)
        
        font_metrics_height = QFontMetrics(self.time_code_label.font()).height()
        self.time_code_label.setFixedHeight(int(font_metrics_height * 1.5)) 

        self.in_button = QPushButton(" IN") 
        if self.get_icon: # Añadir comprobación
            self.in_button.setIcon(self.get_icon("mark_in_icon.svg"))
        self.in_button.setIconSize(icon_size)
        self.in_button.setObjectName("in_button")
        self.in_button.setToolTip("Marcar IN (F5)")
        self.in_button.clicked.connect(self.mark_in)

        self.out_button = QPushButton(" OUT") 
        if self.get_icon: # Añadir comprobación
            self.out_button.setIcon(self.get_icon("mark_out_icon.svg"))
        self.out_button.setIconSize(icon_size)
        self.out_button.setObjectName("out_button")
        self.out_button.setToolTip("Marcar OUT (Mantener F6)")
        self.out_button.pressed.connect(self.start_out_timer)
        self.out_button.released.connect(self.stop_out_timer)

    def setup_layouts(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        top_info_layout = QVBoxLayout()
        top_info_layout.addWidget(self.time_code_label)
        layout.addLayout(top_info_layout)

        layout.addWidget(self.video_widget, 1) # Stretch factor 1 para que se expanda

        layout.addWidget(self.slider) 

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)

        button_widgets = [
            self.detach_button, self.play_button, self.rewind_button, self.forward_button,
            self.in_button, self.out_button
        ]
        for btn in button_widgets:
            buttons_layout.addWidget(btn)
        
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.volume_button)
        buttons_layout.addWidget(self.volume_slider_vertical)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def load_stylesheet(self) -> None:
        try:
            # Asumiendo que la estructura es:
            # project_root/
            #   main.py
            #   guion_editor/
            #     widgets/
            #       video_player_widget.py
            #     styles/
            #       main.css
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            styles_dir = os.path.join(current_file_dir, '..', 'styles')
            css_path = os.path.join(styles_dir, 'main.css')

            if not os.path.exists(css_path):
                # Probar una ruta alternativa común si `guion_editor` es el root del paquete
                # project_root/
                #   guion_editor/
                #     main_script_o_paquete_principal/
                #     widgets/
                #     styles/
                alt_css_path = os.path.join(os.path.dirname(current_file_dir), 'styles', 'main.css')
                if os.path.exists(alt_css_path):
                    css_path = alt_css_path
                else:
                    # print(f"Stylesheet no encontrado en: {css_path} ni en {alt_css_path}") # Reemplazar con logging o manejo de error
                    return

            with open(css_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error de Estilos", f"Error al cargar stylesheet: {str(e)}")

    def setup_shortcuts(self) -> None:
        shortcuts_map = {
            "F8": self.toggle_play,
            "F7": lambda: self.change_position(-5000),
            "F9": lambda: self.change_position(5000),
            "F5": self.mark_in,
        }
        self._shortcuts_list.clear() # Limpiar por si se llama múltiples veces
        for key_str, slot_func in shortcuts_map.items():
            shortcut = QShortcut(QKeySequence(key_str), self)
            shortcut.activated.connect(slot_func)
            self._shortcuts_list.append(shortcut) # Guardar referencia

    def setup_timers(self) -> None:
        self.display_update_timer = QTimer(self)
        self.display_update_timer.setInterval(int(1000 / 30)) # Actualizar UI a ~30fps
        self.display_update_timer.timeout.connect(self.update_time_code)
        self.display_update_timer.start()
        
    def start_out_timer(self):
        if not self.out_timer.isActive():
            self.out_timer.start()
            self.mark_out() # Marcar OUT inmediatamente al iniciar el timer también

    def stop_out_timer(self):
        if self.out_timer.isActive():
            self.out_timer.stop()
            # self.mark_out() # Opcional: Marcar OUT al final también
            self.out_released.emit() # Señal para TableWindow

    def mark_in(self) -> None:
        try:
            position_ms = self.media_player.position()
            self.in_out_signal.emit("IN", position_ms)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error en mark_in: {str(e)}")

    def mark_out(self) -> None: # Llamado por el out_timer
        try:
            position_ms = self.media_player.position()
            self.in_out_signal.emit("OUT", position_ms)
        except Exception as e:
            # Evitar QMessageBox dentro de un timer frecuente
            print(f"Error en mark_out (timer): {str(e)}")


    def toggle_play(self) -> None:
        current_state = self.media_player.playbackState()
        if current_state == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        elif current_state == QMediaPlayer.PlaybackState.PausedState or \
             current_state == QMediaPlayer.PlaybackState.StoppedState:
            if self.media_player.source().isEmpty():
                return
            self.media_player.play()


    def change_position(self, change_ms: int) -> None:
        if self.media_player.duration() <= 0:
            return
        current_pos = self.media_player.position()
        new_position = current_pos + change_ms
        new_position = max(0, min(new_position, self.media_player.duration()))
        self.media_player.setPosition(new_position)

    def set_position(self, position: int) -> None:
        # No buscar si la duración no es válida, excepto si se va a la posición 0
        if self.media_player.duration() <= 0 and position > 0:
             # Restaurar el slider a la posición actual del player si es posible, o a 0
             self.slider.blockSignals(True)
             self.slider.setValue(self.media_player.position() if self.media_player.duration() > 0 else 0)
             self.slider.blockSignals(False)
             return
        self.media_player.setPosition(position)

    def set_volume_from_slider(self, volume_percent: int) -> None:
        if self.media_player and self.media_player.audioOutput():
            volume_float = volume_percent / 100.0
            # La señal volumeChanged del audioOutput se disparará y llamará a update_volume_slider
            self.media_player.audioOutput().setVolume(volume_float)

    def update_volume_slider(self, volume_float: float):
        volume_percent = int(volume_float * 100)
        self.volume_slider_vertical.blockSignals(True) # Evitar bucle de señales
        self.volume_slider_vertical.setValue(volume_percent)
        self.volume_slider_vertical.blockSignals(False)


    def update_play_button(self, state: QMediaPlayer.PlaybackState) -> None:
        # self.play_button.setText("Pausa" if state == QMediaPlayer.PlaybackState.PlayingState else "Play")
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setIcon(self.pause_icon)
            self.play_button.setToolTip("Pausar (F8)")
        else:
            self.play_button.setIcon(self.play_icon)
            self.play_button.setToolTip("Reproducir (F8)")

    def update_slider(self, position: int) -> None:
        # Solo actualizar el slider si el usuario no lo está moviendo activamente
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True) # Evitar que esto dispare set_position innecesariamente
            self.slider.setValue(position)
            self.slider.blockSignals(False)

    def update_slider_range(self, duration: int) -> None:
        self.slider.setRange(0, duration)

    def update_time_code(self) -> None:
        position = self.media_player.position()
        fps = 25.0 # Usar float para el cálculo de msecs_per_frame
        msecs_per_frame = 1000.0 / fps

        hours = 0
        minutes = 0
        seconds = 0
        frames = 0

        if position >= 0:
            total_seconds = position // 1000
            msecs = position % 1000
            
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            frames = int(msecs / msecs_per_frame)
        
        self.time_code_label.setText(f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}:{int(frames):02}")


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
            
            if not self.media_player.audioOutput():
                if not self._audio_output_handler:
                    self._audio_output_handler = QAudioOutput()
                self.media_player.setAudioOutput(self._audio_output_handler)
            
            audio_out = self.media_player.audioOutput()
            if audio_out:
                # Usamos un flag en el propio objeto audioOutput para evitar múltiples conexiones
                if not getattr(audio_out, '_volume_signal_connected_vp', False): # Flag específico
                    audio_out.volumeChanged.connect(self.update_volume_slider)
                    setattr(audio_out, '_volume_signal_connected_vp', True)
                
                # Establecer el valor del slider de volumen basado en el estado actual del audioOutput
                self.volume_slider_vertical.setValue(int(audio_out.volume() * 100))

            self.media_player.play()
        except Exception as e:
            QMessageBox.critical(self, "Error Crítico", f"Error crítico al cargar el video: {str(e)}")

    def on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # Actualizar el slider de volumen si el medio se carga exitosamente
            if self.media_player.audioOutput():
                current_volume_percent = int(self.media_player.audioOutput().volume() * 100)
                self.volume_slider_vertical.setValue(current_volume_percent)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Opcional: mover al inicio y pausar, o detener.
            self.media_player.setPosition(0)
            self.media_player.pause()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            QMessageBox.warning(self, "Error de Medio", "El archivo de video es inválido o no soportado.")


    def on_media_error(self, error_code: QMediaPlayer.Error, error_string: str) -> None:
        if error_code != QMediaPlayer.Error.NoError:
            # Usar el error_string proporcionado por la señal, es más descriptivo
            msg = error_string if error_string else f"Error desconocido en el reproductor (código: {error_code})."
            QMessageBox.warning(self, "Error de Reproducción", msg)


    def set_position_public(self, milliseconds: int) -> None:
        try:
            duration = self.media_player.duration()
            if duration > 0:
                if 0 <= milliseconds <= duration:
                    self.media_player.setPosition(milliseconds)
            elif milliseconds == 0:
                self.media_player.setPosition(milliseconds)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al establecer la posición del video: {str(e)}")


    def detach_widget(self) -> None:
        self.detach_requested.emit(self)


    def toggle_volume_slider(self) -> None:
        self.volume_slider_vertical.setVisible(not self.volume_slider_vertical.isVisible())


    def update_fonts(self, font_size: int) -> None:
        base_font = QFont()
        base_font.setPointSize(font_size)

        controls_to_update = [
            self.play_button, self.rewind_button, self.forward_button,
            self.detach_button, self.in_button, self.out_button, self.volume_button
        ]
        for control in controls_to_update:
            # Verificar que el atributo exista y no sea None
            if hasattr(self, control.objectName()) and control:
                control.setFont(base_font)

        if hasattr(self, 'time_code_label') and self.time_code_label:
            tc_font = QFont()
            # Ajustar el tamaño del timecode label, por ejemplo, un poco más grande o más pequeño.
            # Podrías hacerlo proporcional o con un mínimo/máximo.
            # Ejemplo: font_size para botones, font_size+2 para timecode, con mínimo de 10.
            tc_font_size = max(font_size + 2, 10) 
            tc_font.setPointSize(tc_font_size)
            self.time_code_label.setFont(tc_font)
            
            font_metrics_height = QFontMetrics(tc_font).height()
            self.time_code_label.setFixedHeight(int(font_metrics_height * 1.5))