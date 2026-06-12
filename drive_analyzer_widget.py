import numpy as np
import collections
from PySide6 import QtCore, QtWidgets, QtGui
from ui_utils import FrequencyPlotWidget

class DriveAnalyzer:
    def __init__(self):
        self.fs = 48000
        self.fft_size = 16384
        self.out_ch = 2
        self.in_ch = 0
        
        self.mode = "THD" # "THD" o "IMD"
        self.send_level_db = -8.0
        
        self.capture_buffer = np.zeros(self.fft_size, dtype=np.float32)
        self.capture_pos = 0
        self.sample_count = 0
        self.manual_offset_adj = 0.0
        
        self.analyzer_active = False
        self.result_ready = False
        
        self.freqs = np.fft.rfftfreq(self.fft_size, 1.0 / self.fs)
        self.magnitude_db = np.full(len(self.freqs), -100.0, dtype=np.float32)
        
        # Métricas
        self.thd_percent = 0.0
        self.ratio_even = 0.0
        self.ratio_odd = 0.0
        self.imd_percent = 0.0

    def set_sample_rate(self, fs):
        if fs != self.fs:
            self.fs = fs
            self.freqs = np.fft.rfftfreq(self.fft_size, 1.0 / self.fs)
            self.magnitude_db = np.full(len(self.freqs), -100.0, dtype=np.float32)
            self.capture_buffer = np.zeros(self.fft_size, dtype=np.float32)
            self.capture_pos = 0
            self.sample_count = 0
            self.result_ready = False

    def audio_callback(self, indata, outdata, frames, time, status):
        outdata.fill(0)
        
        if not self.analyzer_active:
            return
            
        if outdata.shape[1] > self.out_ch and indata.shape[1] > self.in_ch:
            amplitude = 10.0 ** (self.send_level_db / 20.0)
            t = (np.arange(frames) + self.sample_count) / self.fs
            self.sample_count += frames
            
            if self.mode == "THD":
                outdata[:, self.out_ch] = np.sin(2 * np.pi * 1000.0 * t) * amplitude
            elif self.mode == "IMD":
                outdata[:, self.out_ch] = (np.sin(2 * np.pi * 900.0 * t) + np.sin(2 * np.pi * 1100.0 * t)) * (amplitude / 2.0)
                
            in_data = indata[:, self.in_ch]
            
            offset = 0
            remaining = frames
            while remaining > 0:
                chunk = min(remaining, self.fft_size - self.capture_pos)
                self.capture_buffer[self.capture_pos:self.capture_pos+chunk] = in_data[offset:offset+chunk]
                self.capture_pos += chunk
                offset += chunk
                remaining -= chunk
                
                if self.capture_pos >= self.fft_size:
                    self.compute_metrics()
                    self.capture_pos = 0

    def compute_metrics(self):
        window = np.hanning(self.fft_size)
        gated_signal = self.capture_buffer * window
        
        fft_data = np.fft.rfft(gated_signal)
        # Normalización Hanning (* 2) y tamaño FFT (/ N) para mantener amplitud pico de seno original
        mag = np.abs(fft_data) / (self.fft_size / 4.0)
        
        # Suavizado EMA suave en crudo
        new_mag_db = 20.0 * np.log10(np.maximum(mag, 1e-6))
        ema_coeff = 0.6
        if self.result_ready:
            self.magnitude_db = ema_coeff * self.magnitude_db + (1.0 - ema_coeff) * new_mag_db
        else:
            self.magnitude_db = new_mag_db
            
        self.result_ready = True
        
        df = self.fs / self.fft_size
        def get_amp(freq):
            bin_idx = int(round(freq / df))
            search_range = max(1, int(round(15.0 / df))) # Buscar pico en ventana +- 15 Hz
            start = max(0, bin_idx - search_range)
            end = min(len(self.magnitude_db), bin_idx + search_range + 1)
            # Retornar el valor lineal del array suavizado en dB para el cálculo de THD
            max_db = np.max(self.magnitude_db[start:end])
            return 10.0 ** (max_db / 20.0)
            
        if self.mode == "THD":
            f0_amp = get_amp(1000)
            if f0_amp < 1e-4: return
            
            even_freqs = [2000, 4000, 6000, 8000]
            odd_freqs = [3000, 5000, 7000, 9000]
            
            even_amps = [get_amp(f) for f in even_freqs]
            odd_amps = [get_amp(f) for f in odd_freqs]
            
            even_sum_sq = sum(a**2 for a in even_amps)
            odd_sum_sq = sum(a**2 for a in odd_amps)
            total_harmonics_sq = even_sum_sq + odd_sum_sq
            
            self.thd_percent = (np.sqrt(total_harmonics_sq) / f0_amp) * 100.0
            
            if total_harmonics_sq > 1e-10:
                self.ratio_even = (even_sum_sq / total_harmonics_sq) * 100.0
                self.ratio_odd = (odd_sum_sq / total_harmonics_sq) * 100.0
            else:
                self.ratio_even = 0.0
                self.ratio_odd = 0.0
                
        elif self.mode == "IMD":
            f1_amp = get_amp(900)
            f2_amp = get_amp(1100)
            
            imd_freqs = [200, 700, 1300]
            imd_amps = [get_amp(f) for f in imd_freqs]
            
            fund_sum_sq = f1_amp**2 + f2_amp**2
            if fund_sum_sq < 1e-8: return
            
            imd_sum_sq = sum(a**2 for a in imd_amps)
            self.imd_percent = (np.sqrt(imd_sum_sq) / np.sqrt(fund_sum_sq)) * 100.0


class DriveAnalyzerWidget(QtWidgets.QWidget):
    def __init__(self, analyzer, main_window):
        super().__init__()
        self.analyzer = analyzer
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Top Header
        header = QtWidgets.QHBoxLayout()
        self.lbl_title = QtWidgets.QLabel("DRIVE ANALYZER  |  Distortion Characteristics")
        self.lbl_title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #FFAC41;")
        
        self.lbl_routing = QtWidgets.QLabel("Desconectado")
        self.lbl_routing.setStyleSheet("font-size: 9pt; color: #666666;")
        
        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_routing)
        layout.addLayout(header)
        
        # Metrics Panel
        metrics_panel = QtWidgets.QHBoxLayout()
        self.lbl_thd = QtWidgets.QLabel("THD: 0.00%")
        self.lbl_ratio = QtWidgets.QLabel("Even: 0% / Odd: 0%")
        self.lbl_imd = QtWidgets.QLabel("IMD: 0.00%")
        
        metric_style = "font-size: 16pt; font-family: 'Consolas'; font-weight: bold; color: #00ADB5; background: #222; padding: 10px; border-radius: 5px; min-width: 200px;"
        self.lbl_thd.setStyleSheet(metric_style)
        self.lbl_ratio.setStyleSheet(metric_style)
        self.lbl_imd.setStyleSheet(metric_style)
        
        self.lbl_thd.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_ratio.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_imd.setAlignment(QtCore.Qt.AlignCenter)
        
        metrics_panel.addWidget(self.lbl_thd)
        metrics_panel.addWidget(self.lbl_ratio)
        metrics_panel.addWidget(self.lbl_imd)
        metrics_panel.addStretch()
        
        layout.addLayout(metrics_panel)
        
        # Plot
        self.plot_widget = FrequencyPlotWidget(y_range=(-100, 10))
        self.curve = self.plot_widget.add_curve("Spectrum", color='#00ADB5')
        layout.addWidget(self.plot_widget)
        
        # Configurar colores para IMD y THD bands en FrequencyPlotWidget
        self.setup_target_bands()
        
        # Bottom controls
        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Mode:"))
        self.mode_sel = QtWidgets.QComboBox()
        self.mode_sel.addItems(["THD Analysis (Signal A)", "IMD Analysis (Signal B)"])
        self.mode_sel.currentTextChanged.connect(self.on_mode_changed)
        controls.addWidget(self.mode_sel)
        
        controls.addSpacing(20)
        
        controls.addWidget(QtWidgets.QLabel("Send Level:"))
        self.send_level_spin = QtWidgets.QDoubleSpinBox()
        self.send_level_spin.setRange(-40.0, 0.0)
        self.send_level_spin.setValue(-8.0)
        self.send_level_spin.setSuffix(" dB")
        self.send_level_spin.valueChanged.connect(self.on_send_level_changed)
        controls.addWidget(self.send_level_spin)
        
        controls.addSpacing(15)
        
        self.btn_auto_zero = QtWidgets.QPushButton("Set 0dB")
        self.btn_auto_zero.setToolTip("Alinea la curva al 0dB compensando la pérdida del hardware.")
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
        layout.addLayout(controls)
        
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)
        
    def setup_target_bands(self):
        pass

    def on_mode_changed(self, text):
        if "THD" in text:
            self.analyzer.mode = "THD"
            self.lbl_imd.hide()
            self.lbl_thd.show()
            self.lbl_ratio.show()
            
            ranges = [
                {'name': 'FUND', 'min_freq': 950.0, 'max_freq': 1050.0, 'color': '#00FA9A'},
                {'name': '2k (E)', 'min_freq': 1950.0, 'max_freq': 2050.0, 'color': '#FF4B2B'},
                {'name': '3k (O)', 'min_freq': 2950.0, 'max_freq': 3050.0, 'color': '#FFAC41'},
                {'name': '4k (E)', 'min_freq': 3950.0, 'max_freq': 4050.0, 'color': '#FF4B2B'},
                {'name': '5k (O)', 'min_freq': 4950.0, 'max_freq': 5050.0, 'color': '#FFAC41'},
                {'name': '6k (E)', 'min_freq': 5950.0, 'max_freq': 6050.0, 'color': '#FF4B2B'},
            ]
            self.plot_widget.set_target_ranges(ranges)
            
        else:
            self.analyzer.mode = "IMD"
            self.lbl_thd.hide()
            self.lbl_ratio.hide()
            self.lbl_imd.show()
            
            ranges = [
                {'name': 'IMD 2nd', 'min_freq': 190.0, 'max_freq': 210.0, 'color': '#FF4B2B'},
                {'name': 'IMD 3rd', 'min_freq': 690.0, 'max_freq': 710.0, 'color': '#FFAC41'},
                {'name': 'FUND 1', 'min_freq': 890.0, 'max_freq': 910.0, 'color': '#00FA9A'},
                {'name': 'FUND 2', 'min_freq': 1090.0, 'max_freq': 1110.0, 'color': '#00FA9A'},
                {'name': 'IMD 3rd', 'min_freq': 1290.0, 'max_freq': 1310.0, 'color': '#FFAC41'},
            ]
            self.plot_widget.set_target_ranges(ranges)

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
        if not self.analyzer.result_ready:
            return
            
        current_median = np.median(self.analyzer.magnitude_db)
        new_offset = self.analyzer.send_level_db - current_median
        
        self.analyzer.manual_offset_adj = new_offset
        
        settings = self.main_window.load_settings()
        if "user_preferences" not in settings: settings["user_preferences"] = {}
        settings["user_preferences"]["calib_db"] = float(new_offset)
        self.main_window.save_settings(settings)

    def showEvent(self, event):
        self.load_send_level_preference()
        self.load_calib_preference()
        self.analyzer.analyzer_active = True
        self.on_mode_changed(self.mode_sel.currentText())
        super().showEvent(event)

    def hideEvent(self, event):
        self.analyzer.analyzer_active = False
        super().hideEvent(event)

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
            
        if self.analyzer.result_ready:
            calibrated_mag = np.clip(self.analyzer.magnitude_db - self.analyzer.send_level_db + self.analyzer.manual_offset_adj, -100.0, 24.0)
            self.curve.setData(self.analyzer.freqs, calibrated_mag)
            
            if self.analyzer.mode == "THD":
                self.lbl_thd.setText(f"THD: {self.analyzer.thd_percent:.2f}%")
                self.lbl_ratio.setText(f"Even: {self.analyzer.ratio_even:.0f}% / Odd: {self.analyzer.ratio_odd:.0f}%")
            else:
                self.lbl_imd.setText(f"IMD: {self.analyzer.imd_percent:.2f}%")
