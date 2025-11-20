# guion_editor/widgets/waveform_widget.py
import subprocess
import numpy as np
import logging
import sys
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

# Altura relativa de la onda
HEIGHT_SCALE = 0.95 

class StreamScannerWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path

    def run(self):
        streams = []
        try:
            command = ['ffmpeg', '-i', self.video_path]
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, startupinfo=startupinfo
            )
            _, err_data = process.communicate()
            output = err_data.decode('utf-8', errors='ignore')
            
            audio_lines = [line for line in output.split('\n') if "Audio:" in line and "Stream #" in line]
            for idx, line in enumerate(audio_lines):
                info = line.strip().split("Audio:")[1].strip()
                if len(info) > 45: info = info[:45] + "..."
                streams.append(f"Pista {idx + 1}: {info}")

        except Exception as e:
            logging.error(f"Error escaneando streams: {e}")
            streams.append("Pista 1 (Default)")
            
        self.finished.emit(streams)


class AudioExtractorWorker(QThread):
    finished = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)

    def __init__(self, video_path, stream_index=0, samples_per_sec=1000): 
        super().__init__()
        self.video_path = video_path
        self.stream_index = stream_index
        self.samples_per_sec = samples_per_sec 

    def run(self):
        try:
            map_cmd = f'0:a:{self.stream_index}'
            
            # Filtro optimizado para visualización de diálogo
            filter_cmd = f'highpass=f=120,aresample={self.samples_per_sec}'
            
            command = [
                'ffmpeg', '-v', 'error', '-i', self.video_path,
                '-vn', '-ac', '1', 
                '-filter:a', filter_cmd, 
                '-map', map_cmd,
                '-c:a', 'pcm_s16le', 
                '-f', 'data', '-'
            ]
            
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, startupinfo=startupinfo
            )
            
            raw_data, err_data = process.communicate()
            
            if process.returncode != 0:
                err_msg = err_data.decode('utf-8', errors='ignore')
                if not raw_data:
                    self.error.emit(f"FFmpeg Error: {err_msg}")
                    return

            if not raw_data:
                self.error.emit(f"La pista {self.stream_index + 1} no tiene datos.")
                return

            # Convertir bytes a int16
            audio_data = np.frombuffer(raw_data, dtype=np.int16)
            
            # Normalización
            # Usamos valor absoluto para simplificar cálculos de picos
            audio_data_abs = np.abs(audio_data)
            
            max_val = np.max(audio_data_abs)
            if max_val == 0: max_val = 1
            
            normalized_data = audio_data_abs / max_val
            
            self.finished.emit(normalized_data)

        except Exception as e:
            logging.error(f"Error extrayendo waveform: {e}")
            self.error.emit(f"Error: {str(e)}")


class WaveformWidget(QWidget):
    tracks_found = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setFixedHeight(80)
        self.setStyleSheet("background-color: #202020; border-top: 1px solid #444;")
        
        self.waveform_data = None 
        self.samples_per_sec = 1000 # Valor por defecto
        self.current_time_ms = 0
        self.error_message = None 

        self.current_video_path = None
        self.current_stream_index = 0
        
        self.time_window_sec = 5.0
        self.amplitude_scale = 1.2 
        
        self.bg_color = QColor("#202020")
        self.wave_color = QColor("#569CD6") 
        self.center_line_color = QColor("#FF5555")
        self.error_text_color = QColor("#FF5555") 
        
        self.pen_wave = QPen(self.wave_color)
        self.pen_wave.setWidth(1)
        
        self.extractor_thread = None
        self.scanner_thread = None

    def set_sample_rate(self, rate):
        """Cambia la calidad y recarga si hay un video activo."""
        if rate != self.samples_per_sec:
            self.samples_per_sec = rate
            # Si ya tenemos un video cargado, recargamos la onda con la nueva calidad
            if self.current_video_path:
                self.load_audio_track(self.current_stream_index)

    def scan_audio_tracks(self, video_path):
        self.current_video_path = video_path
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_thread.terminate()
            self.scanner_thread.wait()
        self.scanner_thread = StreamScannerWorker(video_path)
        self.scanner_thread.finished.connect(self._on_scan_finished)
        self.scanner_thread.start()

    def _on_scan_finished(self, tracks):
        self.tracks_found.emit(tracks)
        if tracks: self.load_audio_track(0)

    def load_audio_track(self, stream_index):
        if not self.current_video_path: return
        self.current_stream_index = stream_index
        self.clear(keep_path=True)
        
        if self.extractor_thread and self.extractor_thread.isRunning():
            self.extractor_thread.terminate()
            self.extractor_thread.wait()
        
        self.extractor_thread = AudioExtractorWorker(self.current_video_path, stream_index, self.samples_per_sec)
        self.extractor_thread.finished.connect(self._on_extraction_finished)
        self.extractor_thread.error.connect(self._on_extraction_error)
        self.extractor_thread.start()
        self.update()

    def clear(self, keep_path=False):
        self.waveform_data = None
        self.error_message = None
        if not keep_path: self.current_video_path = None
        self.update()

    def has_data(self):
        return self.waveform_data is not None and len(self.waveform_data) > 0

    def _on_extraction_finished(self, data):
        self.waveform_data = data
        self.error_message = None
        self.update()

    def _on_extraction_error(self, msg):
        self.waveform_data = None
        self.error_message = msg
        self.update()

    def set_position(self, position_ms):
        if self.current_time_ms != position_ms:
            self.current_time_ms = position_ms
            if self.isVisible():
                self.update()

    def wheelEvent(self, event):
        if not self.has_data(): return
        angle = event.angleDelta().y()
        modifiers = event.modifiers()
        zoom_factor = 1.1 

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if angle > 0: self.amplitude_scale *= zoom_factor
            else: self.amplitude_scale /= zoom_factor
            self.amplitude_scale = max(0.5, min(self.amplitude_scale, 50.0))
        else:
            if angle > 0: self.time_window_sec /= zoom_factor
            else: self.time_window_sec *= zoom_factor
            self.time_window_sec = max(0.5, min(self.time_window_sec, 300.0))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), self.bg_color)
        
        if self.error_message:
            painter.setPen(self.error_text_color)
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, self.error_message)
            return

        if not self.has_data():
            if self.extractor_thread and self.extractor_thread.isRunning():
                painter.setPen(Qt.GlobalColor.gray)
                painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, f"Cargando Pista {self.current_stream_index + 1} ({self.samples_per_sec}Hz)...")
            elif self.scanner_thread and self.scanner_thread.isRunning():
                painter.setPen(Qt.GlobalColor.gray)
                painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, "Analizando audio...")
            return

        rect = self.rect()
        width = rect.width()
        height = rect.height()
        mid_y = height / 2
        
        center_sample_idx = int((self.current_time_ms / 1000.0) * self.samples_per_sec)
        samples_in_half_screen = int((self.time_window_sec / 2) * self.samples_per_sec)
        
        start_idx = center_sample_idx - samples_in_half_screen
        end_idx = center_sample_idx + samples_in_half_screen
        
        data_start_idx = max(0, start_idx)
        data_end_idx = min(len(self.waveform_data), end_idx)
        
        if data_end_idx <= data_start_idx: return

        # --- PEAK DETECTION ALGORITHM (Estable en Zoom Out) ---
        
        # Segmento crudo
        raw_chunk = self.waveform_data[data_start_idx:data_end_idx]
        
        # Calcular ancho de dibujo en pantalla
        x_start = 0
        if start_idx < 0:
            x_start = abs(start_idx) * (width / (samples_in_half_screen * 2))
            
        # Ancho estimado en píxeles que ocupará raw_chunk
        # Proporción: (muestras_chunk / muestras_ventana_total) * ancho_pantalla
        total_window_samples = samples_in_half_screen * 2
        if total_window_samples == 0: total_window_samples = 1
        draw_width = (len(raw_chunk) / total_window_samples) * width
        
        pixel_width = int(draw_width)
        if pixel_width <= 0: return

        lines = []
        half_height = height * HEIGHT_SCALE / 2
        amp_scale = self.amplitude_scale

        # Ratio: Muestras por Píxel
        samples_per_pixel = len(raw_chunk) / pixel_width

        if samples_per_pixel < 1.0:
            # ZOOM IN: Interpolación (hay más píxeles que muestras)
            step_x = 1 / samples_per_pixel
            for i, sample in enumerate(raw_chunk):
                val = (sample ** 0.8) * amp_scale
                val = min(val, 1.0)
                h_val = val * half_height
                x_pos = x_start + (i * step_x)
                
                lines.append(QPoint(int(x_pos), int(mid_y - h_val)))
                lines.append(QPoint(int(x_pos), int(mid_y + h_val)))
        else:
            # ZOOM OUT: Peak Detection (hay más muestras que píxeles)
            # Agrupamos muestras en bloques del tamaño de 1 píxel y sacamos el máximo.
            chunk_size = int(samples_per_pixel)
            
            # Ajustamos el array para que sea divisible por chunk_size
            limit = (len(raw_chunk) // chunk_size) * chunk_size
            if limit == 0: return
            
            process_data = raw_chunk[:limit]
            num_pixels = limit // chunk_size
            
            # Reshape para tener (num_pixels, chunk_size)
            reshaped = process_data.reshape((num_pixels, chunk_size))
            
            # Máximo de cada bloque
            peaks = np.max(reshaped, axis=1)
            
            # Pintamos un pico por píxel
            for i, peak in enumerate(peaks):
                val = (peak ** 0.8) * amp_scale
                val = min(val, 1.0)
                h_val = val * half_height
                
                # Aquí 'i' es exactamente el avance en píxeles relativo al chunk
                x_pos = x_start + (i * (draw_width / num_pixels))
                
                lines.append(QPoint(int(x_pos), int(mid_y - h_val)))
                lines.append(QPoint(int(x_pos), int(mid_y + h_val)))

        painter.setPen(self.pen_wave)
        painter.drawLines(lines)

        painter.setPen(QPen(self.center_line_color, 1))
        painter.drawLine(int(width / 2), 0, int(width / 2), height)
        
        painter.setPen(QColor(255, 255, 255, 80))
        painter.drawText(5, 15, f"x{self.amplitude_scale:.1f} | {self.samples_per_sec}Hz")