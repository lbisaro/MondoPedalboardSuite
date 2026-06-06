import os
import json
import numpy as np
import sounddevice as sd
from PySide6 import QtCore, QtWidgets, QtGui
import qtawesome as qta
from pathlib import Path
from ui_utils import FrequencyPlotWidget, apply_smoothing, sanitize_filename
from audio_comparator import AudioComparator

# --- CONFIGURACIÓN DE AUDIO Y DSP ---
SAMPLE_RATE = 48000
BLOCK_SIZE = 2048
CHANNELS = 2
SMOOTHING_FRACTION = 6

class AudioAnalyzer:
    """Motor de procesamiento de audio en tiempo real basado en el Block Analyzer de la especificación C++."""
    def __init__(self):
        self.fs = SAMPLE_RATE
        self.block_size = BLOCK_SIZE
        self.out_ch = 2 
        self.in_ch = 0  
        self.f1 = 20.0
        self.f2 = 20000.0
        self.num_bins = 512
        
        # Escala logarítmica mapeada a frecuencias (para la UI)
        norm_bins = np.arange(self.num_bins) / (self.num_bins - 1)
        self.freqs = self.f1 * (self.f2 / self.f1) ** norm_bins
        
        self.magnitude_db = np.zeros(self.num_bins, dtype=np.float32)
        self.calibrated_mag = np.zeros(self.num_bins, dtype=np.float32)
        self.smoothed_magnitude_db = np.zeros(self.num_bins, dtype=np.float32)
        
        self.sweep_buffer = np.zeros(self.block_size, dtype=np.float32)
        self.inv_fft_complex = np.zeros(self.block_size // 2 + 1, dtype=np.complex64)
        
        self.capture_buffer = np.zeros(self.block_size, dtype=np.float32)
        self.sweep_write_pos = 0
        self.capture_pos = 0
        self.analyzer_active = False
        
        self.result_ready = False
        
        # Modo de análisis
        self.mode = "Stepped Sine Sweep" # "Stepped Sine Sweep" o "Exponential Sine Sweep"
        self.send_level_db = -8.0 # Nivel por defecto
        
        # Ajuste manual en dBs (SpinBox)
        self.manual_offset_adj = 0.0
        
        # Variables para Stepped Sine
        self.stepped_fraction = SMOOTHING_FRACTION
        self.stepped_freqs = np.array([])
        self.stepped_mags = np.array([])
        self.current_step_idx = 0
        self.stepped_sample_count = 0
        self.stepped_accum_sq = 0.0
        self.current_stepped_freq = 0.0
        
        self.build_sweep_and_inverse_filter()
        self.build_stepped_frequencies(self.stepped_fraction)

    def build_stepped_frequencies(self, fraction):
        if fraction <= 0:
            fraction = 6 # Default fallback
            
        self.stepped_fraction = fraction
        # Calculamos frecuencias de 1/fraction de octava
        num_octaves = np.log2(self.f2 / self.f1)
        num_steps = int(num_octaves * fraction) + 1
        self.stepped_freqs = self.f1 * (2 ** (np.arange(num_steps) / fraction))
        
        # Inicializar array de magnitudes a un valor bajo
        self.stepped_mags = np.full(len(self.stepped_freqs), -64.0, dtype=np.float32)
        
        # Configurar tiempos: 50ms para asentar, 50ms para medir
        self.stepped_settle_samples = int(0.05 * self.fs)
        self.stepped_measure_samples = int(0.05 * self.fs)
        self.stepped_total_samples_per_step = self.stepped_settle_samples + self.stepped_measure_samples
        
        self.current_step_idx = 0
        self.stepped_sample_count = 0
        self.stepped_accum_sq = 0.0
        if len(self.stepped_freqs) > 0:
            self.current_stepped_freq = self.stepped_freqs[0]
            
    def update_stepped_calibrated_mag(self):
        # Interpolar los puntos del barrido escalonado a los 512 bins para mantener compatibilidad
        if len(self.stepped_freqs) > 0:
            interp_mag = np.interp(self.freqs, self.stepped_freqs, self.stepped_mags).astype(np.float32)
            self.magnitude_db = interp_mag
            
            # Matemáticamente: Ganancia = Nivel_Recibido - Nivel_Enviado + Calibración_Manual
            self.calibrated_mag = np.clip(self.magnitude_db - self.send_level_db + self.manual_offset_adj, -100.0, 24.0)
            self.result_ready = True


    def build_sweep_and_inverse_filter(self):
        T = self.block_size / self.fs
        R = np.log(self.f2 / self.f1)
        
        t = np.arange(self.block_size, dtype=np.float64) / self.fs
        phase = 2.0 * np.pi * (self.f1 * T / R) * (np.exp(t * R / T) - 1.0)
        self.sweep_buffer = np.sin(phase).astype(np.float32)
        
        fade_len = min(int(0.001 * self.fs), self.block_size // 16)
        if fade_len > 0:
            w = np.arange(fade_len, dtype=np.float32) / fade_len
            self.sweep_buffer[:fade_len] *= w
            self.sweep_buffer[-fade_len:] *= w[::-1]
            
        sweep_fft = np.fft.rfft(self.sweep_buffer)
        
        nyq = self.fs / 2.0
        freqs = np.fft.rfftfreq(self.block_size, 1.0 / self.fs)
        
        power = np.abs(sweep_fft) ** 2
        eps = 1e-4
        
        bp = np.ones_like(freqs, dtype=np.float32)
        lf_mask = freqs < 15.0
        bp[lf_mask] = np.maximum(0.0, (freqs[lf_mask] - 5.0) / 10.0)
        hf_mask = freqs > 21000.0
        bp[hf_mask] = np.maximum(0.0, (nyq - freqs[hf_mask]) / (nyq - 21000.0))
        
        self.inv_fft_complex = (np.conj(sweep_fft) / (power + eps)) * bp

    def set_sample_rate(self, fs):
        if self.fs != fs:
            self.fs = fs
            self.magnitude_db = np.zeros(self.num_bins, dtype=np.float32)
            self.calibrated_mag = np.zeros(self.num_bins, dtype=np.float32)
            self.smoothed_magnitude_db = np.zeros(self.num_bins, dtype=np.float32)
            self.capture_buffer = np.zeros(self.block_size, dtype=np.float32)
            self.sweep_write_pos = 0
            self.capture_pos = 0
            self.result_ready = False
            self.manual_offset_adj = 0.0
            self.build_sweep_and_inverse_filter()
            self.build_stepped_frequencies(self.stepped_fraction)

    def audio_callback(self, indata, outdata, frames, time, status):
        outdata.fill(0)
        
        if not self.analyzer_active:
            return
            
        if outdata.shape[1] > self.out_ch and indata.shape[1] > self.in_ch:
            in_data = indata[:, self.in_ch]
            
            # Amplitud de salida basada en send_level_db
            amplitude = 10.0 ** (self.send_level_db / 20.0)
            
            if self.mode == "Exponential Sine Sweep":
                offset = 0
                remaining = frames
                
                while remaining > 0:
                    chunk = min(remaining, self.block_size - self.sweep_write_pos)
                    
                    # Cargar barrido (atenuado según send_level)
                    outdata[offset:offset+chunk, self.out_ch] = self.sweep_buffer[self.sweep_write_pos:self.sweep_write_pos+chunk] * amplitude
                    
                    # Capturar
                    self.capture_buffer[self.capture_pos:self.capture_pos+chunk] = in_data[offset:offset+chunk]
                    
                    self.sweep_write_pos += chunk
                    self.capture_pos += chunk
                    
                    offset += chunk
                    remaining -= chunk
                    
                    if self.sweep_write_pos >= self.block_size:
                        self.sweep_write_pos = 0
                        
                    if self.capture_pos >= self.block_size:
                        self.compute_transfer_function()
                        self.capture_pos = 0
            
            elif self.mode == "Stepped Sine Sweep":
                if len(self.stepped_freqs) == 0:
                    return
                    
                freq = self.stepped_freqs[self.current_step_idx]
                self.current_stepped_freq = freq
                
                # Generar señal de salida
                t = (self.stepped_sample_count + np.arange(frames)) / self.fs
                outdata[:, self.out_ch] = np.sin(2 * np.pi * freq * t) * amplitude
                
                # Medir entrada
                start_meas = max(0, self.stepped_settle_samples - self.stepped_sample_count)
                end_meas = min(frames, self.stepped_total_samples_per_step - self.stepped_sample_count)
                
                if start_meas < end_meas:
                    self.stepped_accum_sq += np.sum(in_data[start_meas:end_meas]**2)
                    
                self.stepped_sample_count += frames
                
                if self.stepped_sample_count >= self.stepped_total_samples_per_step:
                    # Finalizó la medición de este paso
                    rms = np.sqrt(self.stepped_accum_sq / self.stepped_measure_samples)
                    db = 20.0 * np.log10(max(rms, 1e-6))
                    self.stepped_mags[self.current_step_idx] = db
                    
                    self.current_step_idx += 1
                    if self.current_step_idx >= len(self.stepped_freqs):
                        self.current_step_idx = 0
                        
                    self.update_stepped_calibrated_mag()
                        
                    # Los samples sobrantes se cuentan para el próximo paso
                    leftover = self.stepped_sample_count - self.stepped_total_samples_per_step
                    self.stepped_sample_count = leftover
                    self.stepped_accum_sq = 0.0

    def compute_transfer_function(self):
        # Compuerta de ruido (evitar computar FFT si no hay señal)
        rms = np.sqrt(np.mean(self.capture_buffer**2))
        if rms < 0.0005:  # ~ -66 dBFS
            self.calibrated_mag.fill(-64.0)
            return

        # 1. FFT de la señal capturada
        cap_fft = np.fft.rfft(self.capture_buffer)
        
        # 2. Deconvolución circular
        ir_spec = cap_fft * self.inv_fft_complex
        
        # 3. IFFT para IR
        ir = np.fft.irfft(ir_spec)
        
        # 4. Pico dinámico absoluto (inmunidad a latencia en cada frame)
        peak_idx = int(np.argmax(np.abs(ir)))
        
        # 5. Compuerta Tukey (64 pre, 384 post = 448 total)
        gate_left = 64
        gate_right = 384
        gate_size = gate_left + gate_right
        
        tukey_win = np.ones(gate_size, dtype=np.float32)
        tukey_win[:32] = 0.5 * (1.0 - np.cos(np.pi * np.arange(32) / 32.0))
        tukey_win[-64:] = 0.5 * (1.0 - np.cos(np.pi * (gate_size - np.arange(gate_size - 64, gate_size)) / 64.0))
        
        # Extracción vectorizada para máxima performance en thread de audio
        indices = (np.arange(gate_size) + peak_idx - gate_left) % self.block_size
        gated_ir = np.zeros(self.block_size, dtype=np.float32)
        gated_ir[:gate_size] = ir[indices] * tukey_win
            
        # 6. FFT IR Ventaneada
        gated_fft = np.fft.rfft(gated_ir)
        
        # 7. Mapeo logarítmico a 512 bandas
        nyq = self.fs / 2.0
        half_bins = self.block_size // 2
        
        norm_bins = np.arange(self.num_bins) / (self.num_bins - 1)
        target_freqs = self.f1 * (self.f2 / self.f1) ** norm_bins
        target_freqs = np.minimum(target_freqs, nyq * 0.999)
        
        k_indices = (target_freqs / nyq * half_bins).astype(np.int32)
        k_indices = np.clip(k_indices, 1, half_bins - 1)
        
        # Para que el nivel de ESS coincida con el Stepped Sine (que mide RMS),
        # necesitamos dividir la amplitud pico por sqrt(2). El / block_size original
        # estaba hundiendo la gráfica en -66dB.
        mags = np.abs(gated_fft[k_indices]) / np.sqrt(2.0)
        new_mag = 20.0 * np.log10(np.maximum(mags, 1e-6))
        
        # 8. Suavizado espectral fijo 1/12 octava (vectorizado)
        W = 3
        pad_mag = np.pad(new_mag, (W, W), mode='edge')
        window = np.ones(2*W+1, dtype=np.float32) / (2*W+1)
        new_mag = np.convolve(pad_mag, window, mode='valid').astype(np.float32)
        
        # 9. Suavizado EMA temporal EN CRUDO (antes del offset para estabilidad absoluta)
        ema_coeff = 0.35
        if self.result_ready:
            self.magnitude_db = ema_coeff * self.magnitude_db + (1.0 - ema_coeff) * new_mag
        else:
            self.magnitude_db = new_mag
            self.result_ready = True
            
        # 10. Ganancia Relativa con calibración manual
        self.calibrated_mag = np.clip(self.magnitude_db - self.send_level_db + self.manual_offset_adj, -100.0, 24.0)

    def get_smoothed_curve(self, fraction=SMOOTHING_FRACTION):
        ui_ema = 0.70
        self.smoothed_magnitude_db = ui_ema * self.smoothed_magnitude_db + (1.0 - ui_ema) * self.calibrated_mag
        return apply_smoothing(self.freqs, self.smoothed_magnitude_db, fraction)

class ReferenceItemWidget(QtWidgets.QWidget):
    """Widget para cada item de la lista de referencias con toggle de visibilidad."""
    def __init__(self, name, parent_list_widget, parent_module):
        super().__init__()
        self.name = name
        self.parent_list_widget = parent_list_widget
        self.parent_module = parent_module
        self.is_visible = False
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)
        
        # Botón Mostrar/Ocultar (Ojo)
        self.btn_toggle = QtWidgets.QPushButton()
        self.btn_toggle.setFixedSize(24, 24)
        self.btn_toggle.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_toggle.setStyleSheet("background: transparent; border: none;")
        self.btn_toggle.clicked.connect(self.toggle_visibility)
        
        # Nombre
        self.lbl_name = QtWidgets.QLabel(name)
        self.lbl_name.setStyleSheet("color: #EAEAEA; font-size: 9pt;")
        
        # Botón Eliminar
        self.btn_delete = QtWidgets.QPushButton(qta.icon('fa5s.times', color='#666'), "")
        self.btn_delete.setFixedSize(20, 20)
        self.btn_delete.setStyleSheet("background: transparent; border: none;")
        self.btn_delete.clicked.connect(lambda: self.parent_module.delete_reference(self.name))
        
        layout.addWidget(self.btn_toggle)
        layout.addWidget(self.lbl_name)
        layout.addStretch()
        layout.addWidget(self.btn_delete)

        # Ahora sí, actualizamos el icono y color (ya que lbl_name existe)
        self.update_icon()

    def update_icon(self):
        icon_name = 'fa5s.eye' if self.is_visible else 'fa5s.eye-slash'
        color = '#00ADB5' if self.is_visible else '#666'
        self.btn_toggle.setIcon(qta.icon(icon_name, color=color))
        
        # Cambiar el color del texto para que coincida con la curva (naranja/amarillo)
        if self.is_visible:
            self.lbl_name.setStyleSheet("color: #FFAC41; font-size: 9pt; font-weight: bold;")
        else:
            self.lbl_name.setStyleSheet("color: #EAEAEA; font-size: 9pt; font-weight: normal;")

    def toggle_visibility(self):
        self.is_visible = not self.is_visible
        self.update_icon()
        self.parent_module.toggle_reference_visibility(self.name, self.is_visible)

class EQAnalyzerWidget(QtWidgets.QWidget):
    """Módulo de Analizador de EQ con Sidebar de Referencias."""
    def __init__(self, analyzer, main_window):
        super().__init__()
        self.analyzer = analyzer
        self.main_window = main_window
        # Diccionario de {nombre: objeto_curva_de_pyqtgraph}
        self.active_ref_curves = {} 
        self.comparator = AudioComparator()
        self.refs_path = Path("./user_data/eq_references")
        self.refs_path.mkdir(parents=True, exist_ok=True)
        
        self.init_ui()
        self.refresh_ref_list()

    def init_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # --- SIDEBAR IZQUIERDO ---
        self.sidebar = QtWidgets.QWidget()
        self.sidebar.setFixedWidth(240)
        side_layout = QtWidgets.QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(0, 0, 10, 0)
        
        header_ref = QtWidgets.QHBoxLayout()
        lbl_ref = QtWidgets.QLabel("REFERENCES")
        lbl_ref.setStyleSheet("font-weight: bold; color: #00ADB5; font-size: 10pt; letter-spacing: 1px;")
        
        self.btn_add_ref = QtWidgets.QPushButton(qta.icon('fa5s.plus', color='#00ADB5'), "")
        self.btn_add_ref.setFixedSize(24, 24)
        self.btn_add_ref.clicked.connect(self.capture_reference)
        self.btn_add_ref.setStyleSheet("background: transparent; border: 1px solid #333; border-radius: 4px;")
        
        header_ref.addWidget(lbl_ref)
        header_ref.addStretch()
        header_ref.addWidget(self.btn_add_ref)
        side_layout.addLayout(header_ref)
        
        self.list_refs = QtWidgets.QListWidget()
        self.list_refs.setObjectName("LoopList")
        self.list_refs.itemClicked.connect(self.on_ref_clicked)
        side_layout.addWidget(self.list_refs)
        
        main_layout.addWidget(self.sidebar)
        
        # --- PANEL DERECHO ---
        self.right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.right_panel)
        
        # --- TOP HEADER ROW ---
        header_layout = QtWidgets.QVBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)
        header_layout.setSpacing(5)
        
        row1 = QtWidgets.QHBoxLayout()
        self.lbl_title = QtWidgets.QLabel("EQ TRANSFER FUNCTION  |  Exponential Sine Sweep (Farina Method)")
        self.lbl_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #FFAC41;")
        
        row1.addWidget(self.lbl_title)
        row1.addStretch()
        header_layout.addLayout(row1)
        
        row2 = QtWidgets.QHBoxLayout()
        self.lbl_routing = QtWidgets.QLabel("Desconectado")
        self.lbl_routing.setStyleSheet("font-size: 9pt; color: #666666;")
        
        target_container = QtWidgets.QHBoxLayout()
        lbl_target = QtWidgets.QLabel("TARGET PROFILE:")
        lbl_target.setStyleSheet("font-size: 9pt; font-weight: bold; color: #888888;")
        
        self.target_sel = QtWidgets.QComboBox()
        self.target_sel.setObjectName("TargetProfileCombo")
        self.target_sel.addItems(["None", "AMBIENT", "RHYTHM", "LEAD"])
        self.target_sel.setStyleSheet("""
            QComboBox#TargetProfileCombo {
                background-color: #222;
                border: 1px solid #444;
                border-radius: 4px;
                color: #FFF;
                font-weight: bold;
                padding: 3px 20px 3px 10px;
                min-width: 100px;
            }
            QComboBox#TargetProfileCombo:hover {
                border-color: #00ADB5;
            }
        """)
        self.target_sel.currentTextChanged.connect(self.on_target_changed)
        
        target_container.addWidget(lbl_target)
        target_container.addWidget(self.target_sel)
        
        row2.addWidget(self.lbl_routing)
        row2.addStretch()
        row2.addLayout(target_container)
        header_layout.addLayout(row2)
        
        right_layout.addLayout(header_layout)
        
        self.plot_widget = FrequencyPlotWidget(y_range=(-16, 16))
        self.curve = self.plot_widget.add_curve("Muestreo", color='#00ADB5')
        # Ya no usaremos self.ref_curve fija, sino dinámicas
        right_layout.addWidget(self.plot_widget)
        
        controls = QtWidgets.QHBoxLayout()
        
        # Modo de barrido
        controls.addWidget(QtWidgets.QLabel("Mode:"))
        self.mode_sel = QtWidgets.QComboBox()
        self.mode_sel.addItems(["Stepped Sine Sweep", "Exponential Sine Sweep"])
        self.mode_sel.currentTextChanged.connect(self.on_mode_changed)
        controls.addWidget(self.mode_sel)
        controls.addSpacing(10)
        
        controls.addWidget(QtWidgets.QLabel("Smoothing:"))
        self.smooth_sel = QtWidgets.QComboBox()
        self.smooth_sel.addItems(["None", "1/3 Octave", "1/6 Octave", "1/12 Octave"])
        
        # Cargar preferencia del usuario
        settings = self.main_window.load_settings()
        pref_smooth = settings.get("user_preferences", {}).get("smoothing", "1/6 Octave")
        self.smooth_sel.setCurrentText(pref_smooth)
        self.smooth_sel.currentTextChanged.connect(self.save_smoothing_preference)
        
        controls.addWidget(self.smooth_sel)
        controls.addSpacing(10)
        
        # Nivel de Señal
        controls.addWidget(QtWidgets.QLabel("Send Level:"))
        self.send_level_spin = QtWidgets.QDoubleSpinBox()
        self.send_level_spin.setObjectName("SendLevelSpin")
        self.send_level_spin.setRange(-25.0, -6.0)
        self.send_level_spin.setSingleStep(1.0)
        self.send_level_spin.setValue(-8.0)
        self.send_level_spin.setSuffix(" dB")
        self.send_level_spin.setDecimals(1)
        self.send_level_spin.setFixedWidth(100)
        self.send_level_spin.valueChanged.connect(self.on_send_level_changed)
        controls.addWidget(self.send_level_spin)
        
        # Separador / Espacio
        controls.addSpacing(15)
        
        # Botón para Auto-Calibrar a 0dB
        self.btn_auto_zero = QtWidgets.QPushButton("Set 0dB")
        self.btn_auto_zero.setToolTip("Alinea la curva actual exactamente al 0dB compensando la pérdida del hardware.")
        self.btn_auto_zero.setFixedWidth(80)
        self.btn_auto_zero.setStyleSheet("""
            QPushButton {
                background-color: #00ADB5;
                color: #111;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #008C94;
            }
        """)
        self.btn_auto_zero.clicked.connect(self.on_auto_zero)
        controls.addWidget(self.btn_auto_zero)
        
        controls.addStretch()
        right_layout.addLayout(controls)
        
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(30)

    def showEvent(self, event):
        """Activar el ruido y recargar preferencias cuando el widget se muestra."""
        self.load_smoothing_preference()
        self.load_target_preference()
        self.load_mode_preference()
        self.load_send_level_preference()
        self.load_calib_preference()
        
        self.analyzer.analyzer_active = True
        super().showEvent(event)

    def hideEvent(self, event):
        """Desactivar el ruido cuando el widget se oculta."""
        self.analyzer.analyzer_active = False
        super().hideEvent(event)

    def load_smoothing_preference(self):
        settings = self.main_window.load_settings()
        pref_smooth = settings.get("user_preferences", {}).get("smoothing", "1/6 Octave")
        self.smooth_sel.blockSignals(True)
        self.smooth_sel.setCurrentText(pref_smooth)
        self.smooth_sel.blockSignals(False)

    def save_smoothing_preference(self, text):
        settings = self.main_window.load_settings()
        if "user_preferences" not in settings: settings["user_preferences"] = {}
        settings["user_preferences"]["smoothing"] = text
        self.main_window.save_settings(settings)
        
        # Si estamos en Stepped Sine, hay que reconstruir las frecuencias
        fraction = 0
        if "1/3" in text: fraction = 3
        elif "1/6" in text: fraction = 6
        elif "1/12" in text: fraction = 12
        if fraction > 0:
            self.analyzer.build_stepped_frequencies(fraction)
            
    def load_mode_preference(self):
        settings = self.main_window.load_settings()
        pref_mode = settings.get("user_preferences", {}).get("analyzer_mode", "Stepped Sine Sweep")
        self.mode_sel.blockSignals(True)
        self.mode_sel.setCurrentText(pref_mode)
        self.mode_sel.blockSignals(False)
        self.on_mode_changed(pref_mode)
        
    def on_mode_changed(self, mode_text):
        self.analyzer.mode = mode_text
        if mode_text == "Stepped Sine Sweep":
            self.lbl_title.setText("EQ TRANSFER FUNCTION  |  Stepped Sine Sweep")
            self.plot_widget.set_sweep_frequency(self.analyzer.current_stepped_freq)
        else:
            self.lbl_title.setText("EQ TRANSFER FUNCTION  |  Exponential Sine Sweep (Farina Method)")
            self.plot_widget.set_sweep_frequency(0) # Hide
            
        settings = self.main_window.load_settings()
        if "user_preferences" not in settings: settings["user_preferences"] = {}
        settings["user_preferences"]["analyzer_mode"] = mode_text
        self.main_window.save_settings(settings)
        
    def load_send_level_preference(self):
        settings = self.main_window.load_settings()
        pref_level = settings.get("user_preferences", {}).get("send_level_db", -8.0)
        self.send_level_spin.blockSignals(True)
        self.send_level_spin.setValue(pref_level)
        self.send_level_spin.blockSignals(False)
        self.analyzer.send_level_db = pref_level

    def on_send_level_changed(self, value):
        self.analyzer.send_level_db = value
        settings = self.main_window.load_settings()
        if "user_preferences" not in settings: settings["user_preferences"] = {}
        settings["user_preferences"]["send_level_db"] = value
        self.main_window.save_settings(settings)

    def load_calib_preference(self):
        settings = self.main_window.load_settings()
        pref_calib = settings.get("user_preferences", {}).get("calib_db", 0.0)
        self.analyzer.manual_offset_adj = pref_calib

    def on_auto_zero(self):
        """Calcula el offset necesario para que la curva actual promedie 0dB y lo guarda."""
        if not self.analyzer.result_ready:
            return
            
        # Tomamos la mediana de la magnitud bruta para ignorar picos locos
        current_median = np.median(self.analyzer.magnitude_db)
        
        # Queremos que: current_median - send_level_db + new_offset = 0
        new_offset = self.analyzer.send_level_db - current_median
        
        self.analyzer.manual_offset_adj = new_offset
        
        settings = self.main_window.load_settings()
        if "user_preferences" not in settings: settings["user_preferences"] = {}
        settings["user_preferences"]["calib_db"] = float(new_offset)
        self.main_window.save_settings(settings)

        
    def update_plot(self):
        settings = self.main_window.load_settings()
        conn = settings.get("connection", {})
        if conn:
            device = conn.get("device_name", "Helix")
            in_ch = conn.get("in_channel", "?")
            out_ch = conn.get("out_channel", "?")
            self.lbl_routing.setText(f"Output -> {device}: USB {out_ch}/{out_ch+1}  |  Input <- {device}: USB {in_ch}/{in_ch+1}")
        else:
            self.lbl_routing.setText("Audio Desconectado")

        smooth_txt = self.smooth_sel.currentText()
        fraction = 0
        if "1/3" in smooth_txt: fraction = 3
        elif "1/6" in smooth_txt: fraction = 6
        elif "1/12" in smooth_txt: fraction = 12
        
        smoothed = self.analyzer.get_smoothed_curve(fraction)
        if smoothed is not None:
            self.curve.setData(self.analyzer.freqs, smoothed)
            
        if self.analyzer.mode == "Stepped Sine Sweep":
            self.plot_widget.set_sweep_frequency(self.analyzer.current_stepped_freq)
        else:
            self.plot_widget.set_sweep_frequency(0)
            
        # Actualizar todas las curvas de referencia activas
        for name, curve_obj in self.active_ref_curves.items():
            path = self.refs_path / f"{name}.mndEqRef"
            if path.exists():
                try:
                    # En una app real, podríamos cachear los datos en memoria
                    # para no leer del disco 30 veces por segundo.
                    # Por ahora lo dejamos así o cacheamos en la clase.
                    if not hasattr(self, '_ref_cache'): self._ref_cache = {}
                    if name not in self._ref_cache:
                        freqs, values = self.comparator.load_eq_reference(str(path))
                        self._ref_cache[name] = (freqs, values)
                    
                    freqs, values = self._ref_cache[name]
                    curve_obj.setData(freqs, values)
                except: pass

    def refresh_ref_list(self):
        self.list_refs.clear()
        self.migrate_references_to_files()
        
        for f in self.refs_path.glob("*.mndEqRef"):
            name = f.stem
            item = QtWidgets.QListWidgetItem(self.list_refs)
            widget = ReferenceItemWidget(name, self.list_refs, self)
            item.setSizeHint(widget.sizeHint())
            self.list_refs.addItem(item)
            self.list_refs.setItemWidget(item, widget)

    def migrate_references_to_files(self):
        """Migra referencias de settings.json a archivos .mndEqRef"""
        settings = self.main_window.load_settings()
        refs = settings.get("references", {})
        if not refs: return
        
        migrated = False
        for name, data in refs.items():
            safe_name = sanitize_filename(name)
            path = self.refs_path / f"{safe_name}.mndEqRef"
            if not path.exists():
                try:
                    self.comparator.save_eq_reference(str(path), np.array(data["freqs"]), np.array(data["values"]))
                    migrated = True
                except Exception as e:
                    print(f"Error migrando referencia {name}: {e}")
        
        if migrated:
            # settings.pop("references", None)
            # self.main_window.save_settings(settings)
            pass

    def toggle_reference_visibility(self, name, visible):
        if visible:
            if name not in self.active_ref_curves:
                # Añadir curva al gráfico (usamos un color naranja/amarillo para refs)
                new_curve = self.plot_widget.add_curve(name, color='#FFAC41', width=1.5)
                self.active_ref_curves[name] = new_curve
                # Limpiar cache para forzar recarga
                if hasattr(self, '_ref_cache') and name in self._ref_cache:
                    del self._ref_cache[name]
        else:
            if name in self.active_ref_curves:
                # Quitar curva del gráfico
                self.plot_widget.plotItem.removeItem(self.active_ref_curves[name])
                del self.active_ref_curves[name]
                if hasattr(self, '_ref_cache') and name in self._ref_cache:
                    del self._ref_cache[name]

    def on_ref_clicked(self, item):
        # Al hacer click en el item, disparamos el toggle del widget (ojo)
        widget = self.list_refs.itemWidget(item)
        if widget:
            widget.toggle_visibility()

    def capture_reference(self):
        # Forzar suavizado de 1/12 para el guardado persistente
        smoothed = self.analyzer.get_smoothed_curve(12)
        if smoothed is None or not np.any(smoothed):
            QtWidgets.QMessageBox.warning(self, "Referencias", "No hay audio activo para capturar.")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(self, "Guardar Referencia", "Nombre de la curva:")
        if ok and name.strip():
            safe_name = sanitize_filename(name.strip())
            path = self.refs_path / f"{safe_name}.mndEqRef"
            
            if path.exists():
                reply = QtWidgets.QMessageBox.question(self, "Referencia existente", 
                                                     f"La referencia '{safe_name}' ya existe. ¿Sobrescribir?",
                                                     QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if reply == QtWidgets.QMessageBox.No: return
            
            try:
                self.comparator.save_eq_reference(str(path), self.analyzer.freqs, smoothed)
                self.refresh_ref_list()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo guardar: {e}")

    def delete_reference(self, name): 
        # Asegurarse de quitar la curva si estaba visible
        self.toggle_reference_visibility(name, False)
        
        path = self.refs_path / f"{name}.mndEqRef"
        if path.exists():
            try:
                os.remove(path)
                self.refresh_ref_list()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo eliminar: {e}")

    def on_target_changed(self, target_name):
        self.update_target_bands(target_name)
        settings = self.main_window.load_settings()
        if "user_preferences" not in settings:
            settings["user_preferences"] = {}
        settings["user_preferences"]["target_profile"] = target_name
        self.main_window.save_settings(settings)

    def load_target_profiles(self):
        json_path = Path("./utils/target_profiles.json")
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading target profiles: {e}")
        return {
            "AMBIENT": {"brightness_min": 600.0, "brightness_max": 1500.0},
            "RHYTHM": {"brightness_min": 1200.0, "brightness_max": 2000.0},
            "LEAD": {"brightness_min": 1900.0, "brightness_max": 2700.0}
        }

    def update_target_bands(self, target_name):
        if target_name == "None" or not target_name:
            self.plot_widget.set_target_ranges([])
            return
            
        profiles = self.load_target_profiles()
        profile = profiles.get(target_name, {})
        
        ranges = [
            {'name': 'BODY', 'min_freq': 100.0, 'max_freq': 500.0, 'color': '#9370DB'},
            {'name': 'CUT', 'min_freq': 2000.0, 'max_freq': 5000.0, 'color': '#00FA9A'}
        ]
        
        b_min = profile.get("brightness_min")
        b_max = profile.get("brightness_max")
        if b_min is not None and b_max is not None:
            ranges.append({
                'name': 'BRIGHTNESS',
                'min_freq': b_min,
                'max_freq': b_max,
                'color': '#FFA500'
            })
            
        self.plot_widget.set_target_ranges(ranges)

    def load_target_preference(self):
        settings = self.main_window.load_settings()
        pref_target = settings.get("user_preferences", {}).get("target_profile", "None")
        self.target_sel.blockSignals(True)
        self.target_sel.setCurrentText(pref_target)
        self.target_sel.blockSignals(False)
        self.update_target_bands(pref_target)
