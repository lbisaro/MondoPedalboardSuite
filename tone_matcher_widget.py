import os
import json
import time
import numpy as np
import soundfile as sf
import sounddevice as sd
import mido
from PySide6 import QtCore, QtWidgets, QtGui
import qtawesome as qta
from audio_comparator import AudioComparator
from ui_utils import FrequencyPlotWidget, apply_smoothing

class OptimizeCancelled(Exception):
    pass

class AmpOptimizeWorker(QtCore.QThread):
    request_eval_sig = QtCore.Signal(list)       # [bass, mid, treble, presence]
    status_sig = QtCore.Signal(int, str)         # progress pct, status text
    finished_sig = QtCore.Signal(bool, str, list) # success, message, best_x

    def __init__(self, ccs, target_data, native_sr):
        super().__init__()
        self.ccs = ccs
        self.target_data = target_data
        self.native_sr = native_sr
        self.is_cancelled = False
        
        self.mutex = QtCore.QMutex()
        self.wait_cond = QtCore.QWaitCondition()
        self.eval_ready = False
        self.eval_result = None
        self.eval_metrics = None
        self.eval_count = 0
        self.max_evals = 35

    def cancel(self):
        self.is_cancelled = True
        self.mutex.lock()
        self.eval_ready = True
        self.wait_cond.wakeAll()
        self.mutex.unlock()

    def set_evaluation_result(self, error_val, metrics):
        self.mutex.lock()
        self.eval_result = error_val
        self.eval_metrics = metrics
        self.eval_ready = True
        self.wait_cond.wakeAll()
        self.mutex.unlock()

    def cost_function(self, x):
        if self.is_cancelled:
            raise OptimizeCancelled("Cancelado")
            
        self.eval_count += 1
        pct = min(99, int((self.eval_count / self.max_evals) * 100))
        self.status_sig.emit(pct, f"Evaluación {self.eval_count}/{self.max_evals}: Probando B={int(x[0])}, M={int(x[1])}, T={int(x[2])}, P={int(x[3])}...")
        
        cc_vals = [int(np.clip(v, 0, 127)) for v in x]
        
        self.mutex.lock()
        self.eval_ready = False
        self.request_eval_sig.emit(cc_vals)
        
        while not self.eval_ready:
            self.wait_cond.wait(self.mutex)
            
        if self.is_cancelled:
            self.mutex.unlock()
            raise OptimizeCancelled("Cancelado")
            
        res = self.eval_result
        self.mutex.unlock()
        return res

    def run(self):
        from scipy.optimize import minimize
        x0 = [64, 64, 64, 64] # Start at 50% parameters
        try:
            res = minimize(
                self.cost_function,
                x0,
                method='Nelder-Mead',
                options={'maxfev': self.max_evals, 'xatol': 3.0, 'fatol': 1.0}
            )
            if self.is_cancelled:
                self.finished_sig.emit(False, "Proceso cancelado por el usuario.", None)
                return
            best_x = [int(np.clip(v, 0, 127)) for v in res.x]
            self.finished_sig.emit(True, f"Optimización finalizada en {self.eval_count} pasos.\nSeteado final: Graves={best_x[0]}, Medios={best_x[1]}, Agudos={best_x[2]}, Presencia={best_x[3]}", best_x)
        except OptimizeCancelled:
            self.finished_sig.emit(False, "Proceso cancelado por el usuario.", None)
        except Exception as e:
            self.finished_sig.emit(False, f"Error en optimización: {str(e)}", None)

class MetricCard(QtWidgets.QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setStyleSheet("""
            QFrame#MetricCard {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 6px;
                padding: 6px;
            }
            QLabel {
                background: transparent;
            }
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        self.lbl_title = QtWidgets.QLabel(title)
        self.lbl_title.setStyleSheet("color: #888888; font-size: 8pt; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;")
        
        val_layout = QtWidgets.QHBoxLayout()
        val_layout.setSpacing(6)
        
        self.lbl_target = QtWidgets.QLabel("---")
        self.lbl_target.setStyleSheet("color: #FFAC41; font-size: 11pt; font-weight: bold;")
        
        self.lbl_sep = QtWidgets.QLabel("|")
        self.lbl_sep.setStyleSheet("color: #444444; font-size: 10pt;")
        
        self.lbl_processed = QtWidgets.QLabel("---")
        self.lbl_processed.setStyleSheet("color: #00ADB5; font-size: 11pt; font-weight: bold;")
        
        val_layout.addWidget(self.lbl_target)
        val_layout.addWidget(self.lbl_sep)
        val_layout.addWidget(self.lbl_processed)
        val_layout.addStretch()
        
        self.lbl_delta = QtWidgets.QLabel("")
        self.lbl_delta.setStyleSheet("color: #888888; font-size: 8pt;")
        
        layout.addWidget(self.lbl_title)
        layout.addLayout(val_layout)
        layout.addWidget(self.lbl_delta)
        
    def set_values(self, target_val, processed_val, delta_val=None, color_delta=None):
        self.lbl_target.setText(str(target_val))
        self.lbl_processed.setText(str(processed_val))
        if delta_val:
            self.lbl_delta.setText(f"Δ: {delta_val}")
            if color_delta == "green":
                self.lbl_delta.setStyleSheet("color: #00FFAB; font-size: 8pt; font-weight: bold;")
            elif color_delta == "red":
                self.lbl_delta.setStyleSheet("color: #FF4B2B; font-size: 8pt; font-weight: bold;")
            else:
                self.lbl_delta.setStyleSheet("color: #888888; font-size: 8pt;")
        else:
            self.lbl_delta.setText("")

class ToneMatcherWidget(QtWidgets.QWidget):
    def __init__(self, analyzer, main_window):
        super().__init__()
        self.analyzer = analyzer
        self.main_window = main_window
        self.comparator = AudioComparator()

        self.target_data = None
        self.di_audio = None
        self.di_sr = None

        # State machine variables for matching loop (runs on main thread)
        self.is_running = False
        self.is_looping = False
        self.goal_type = None
        self.midi_port = None
        
        # Goal 1 state variables
        self.g1_cc = 17
        self.g1_steps = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        self.g1_current_idx = 0
        self.g1_best_diff = float('inf')
        self.g1_best_cc_val = 0
        self.g1_best_centroid = 0
        
        # Audio routing parameters
        self.audio_settings = None
        self.actual_in_id = None
        self.actual_out_id = None
        self.send_ch = None
        self.receive_ch = None
        self.num_in = None
        self.num_out = None
        self.native_sr = None
        
        # Temporary buffers for non-blocking playrec
        self.play_array = None
        self.record_array = None
        
        # Audio loop QTimer
        self.loop_timer = QtCore.QTimer(self)
        self.loop_timer.setSingleShot(True)
        self.loop_timer.timeout.connect(self.process_loop_iteration)

        self.init_ui()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # --- TOP HEADER ROW ---
        header_layout = QtWidgets.QHBoxLayout()
        self.lbl_title = QtWidgets.QLabel("TONE MATCHER")
        self.lbl_title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #00ADB5; letter-spacing: 1px;")
        header_layout.addWidget(self.lbl_title)
        
        # MIDI Device Selection
        header_layout.addStretch()
        header_layout.addWidget(QtWidgets.QLabel("Helix MIDI Port:"))
        self.midi_port_combo = QtWidgets.QComboBox()
        self.midi_port_combo.setMinimumWidth(200)
        self.refresh_midi_ports()
        header_layout.addWidget(self.midi_port_combo)
        
        self.btn_refresh_midi = QtWidgets.QPushButton(qta.icon('fa5s.sync-alt', color='#00ADB5'), "")
        self.btn_refresh_midi.setToolTip("Refrescar puertos MIDI")
        self.btn_refresh_midi.clicked.connect(self.refresh_midi_ports)
        header_layout.addWidget(self.btn_refresh_midi)
        
        main_layout.addLayout(header_layout)

        # --- METRIC CARDS GRID (6 Cards) ---
        grid_layout = QtWidgets.QGridLayout()
        grid_layout.setSpacing(10)
        
        self.card_lufs = MetricCard("Loudness (LUFS)")
        self.card_plr = MetricCard("Dynamics (PLR)")
        self.card_peak = MetricCard("Max Peak (dBFS)")
        self.card_sat = MetricCard("Saturation (Gain)")
        self.card_bright = MetricCard("Brightness (Hz)")
        self.card_sustain = MetricCard("Sustain (%)")
        
        grid_layout.addWidget(self.card_lufs, 0, 0)
        grid_layout.addWidget(self.card_plr, 0, 1)
        grid_layout.addWidget(self.card_peak, 0, 2)
        grid_layout.addWidget(self.card_sat, 1, 0)
        grid_layout.addWidget(self.card_bright, 1, 1)
        grid_layout.addWidget(self.card_sustain, 1, 2)
        
        main_layout.addLayout(grid_layout)

        # --- SPLIT LAYOUT PANEL (Left: Controls, Right: FFT Plot) ---
        split_layout = QtWidgets.QHBoxLayout()
        split_layout.setSpacing(15)

        # LEFT SIDE: Controls Panel
        left_panel = QtWidgets.QWidget()
        left_panel.setFixedWidth(420)
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        # File loaders card
        files_frame = QtWidgets.QFrame()
        files_frame.setObjectName("MetricCard")
        files_frame.setStyleSheet("""
            QFrame#MetricCard {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 6px;
            }
        """)
        files_layout = QtWidgets.QGridLayout(files_frame)
        files_layout.setContentsMargins(15, 12, 15, 12)
        files_layout.setSpacing(10)

        # Target file loader
        files_layout.addWidget(QtWidgets.QLabel("Target:"), 0, 0)
        self.lbl_target_file = QtWidgets.QLabel("Vacio")
        self.lbl_target_file.setStyleSheet("color: #888;")
        files_layout.addWidget(self.lbl_target_file, 0, 1)
        self.btn_load_target = QtWidgets.QPushButton("Cargar .wav")
        self.btn_load_target.clicked.connect(self.load_target_file)
        files_layout.addWidget(self.btn_load_target, 0, 2)

        # DI file loader
        files_layout.addWidget(QtWidgets.QLabel("Guitar DI:"), 1, 0)
        self.lbl_di_file = QtWidgets.QLabel("Vacio")
        self.lbl_di_file.setStyleSheet("color: #888;")
        files_layout.addWidget(self.lbl_di_file, 1, 1)
        self.btn_load_di = QtWidgets.QPushButton("Cargar .wav")
        self.btn_load_di.clicked.connect(self.load_di_file)
        files_layout.addWidget(self.btn_load_di, 1, 2)

        left_layout.addWidget(files_frame)

        # Tab Widget for Goals
        self.tabs = QtWidgets.QTabWidget()
        
        # Tab 1: Ajuste Manual
        self.tab_brightness = QtWidgets.QWidget()
        self.setup_brightness_tab()
        self.tabs.addTab(self.tab_brightness, "Ajuste Manual")

        # Tab 2: Amp EQ (Initially disabled)
        self.tab_amp = QtWidgets.QWidget()
        self.setup_amp_tab()
        self.tabs.addTab(self.tab_amp, "Amp EQ")
        self.tabs.setTabEnabled(1, False)

        # Tab 3: EQ (Initially disabled)
        self.tab_eq = QtWidgets.QWidget()
        self.setup_eq_tab()
        self.tabs.addTab(self.tab_eq, "Surgical EQ & Nivel")
        self.tabs.setTabEnabled(2, False)

        left_layout.addWidget(self.tabs)
        split_layout.addWidget(left_panel)

        # RIGHT SIDE: Plot Panel
        self.plot_widget = FrequencyPlotWidget(y_range=(-80, 0))
        self.target_curve = self.plot_widget.add_curve("Target FFT", color='#FFAC41', width=2)
        self.di_curve = self.plot_widget.add_curve("Processed DI FFT", color='#00ADB5', width=2)
        
        split_layout.addWidget(self.plot_widget)
        main_layout.addLayout(split_layout)

        # --- PROGRESS & STATUS BAR ---
        status_layout = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(15)
        status_layout.addWidget(self.progress_bar)

        self.lbl_status = QtWidgets.QLabel("Esperando carga de archivos...")
        self.lbl_status.setStyleSheet("color: #FFAC41; font-weight: bold;")
        status_layout.addWidget(self.lbl_status)

        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_matching)
        status_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(status_layout)

    def refresh_midi_ports(self):
        self.midi_port_combo.clear()
        try:
            ports = mido.get_output_names()
            unique_ports = sorted(list(set(ports)))
            self.midi_port_combo.addItems(unique_ports)
            
            for idx, p in enumerate(unique_ports):
                if "helix" in p.lower():
                    self.midi_port_combo.setCurrentIndex(idx)
                    break
        except Exception as e:
            print(f"Error loading MIDI ports: {e}")

    def load_target_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Seleccionar Target File", "", "Audio Files (*.wav)")
        if path:
            try:
                data, sr = sf.read(path)
                if data.ndim > 1:
                    data = np.mean(data, axis=1)
                
                self.comparator.set_sample_rate(sr)
                self.target_data = self.comparator.calculate_metrics(data)
                
                # Normalizar curva FFT del Target sumándole/restándole la diferencia entre su LUFS original
                # y el LUFS objetivo del perfil actual seleccionado (si hay un perfil activo)
                self.normalize_target_fft()
                
                self.lbl_target_file.setText(os.path.basename(path))
                self.lbl_target_file.setStyleSheet("color: #00ADB5; font-weight: bold;")
                self.lbl_status.setText("Target cargado con éxito.")
                
                # Plot target FFT
                target_spec = self.target_data['normalized_spectrum']
                target_db = 20 * np.log10(target_spec + 1e-12)
                self.target_curve.setData(self.target_data['freqs'], target_db)
                self.plot_widget.auto_scale()
                
                self.update_metrics_cards(target_only=True)
                self.update_ui_state()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo cargar el target: {e}")

    def load_di_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Seleccionar Guitar DI", "", "Audio Files (*.wav)")
        if path:
            try:
                data, sr = sf.read(path)
                if data.ndim > 1:
                    data = np.mean(data, axis=1)

                self.di_audio = data
                self.di_sr = sr
                self.lbl_di_file.setText(os.path.basename(path))
                self.lbl_di_file.setStyleSheet("color: #00ADB5; font-weight: bold;")
                self.lbl_status.setText("Guitar DI cargado en memoria RAM.")
                self.update_ui_state()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo cargar el Guitar DI: {e}")

    def update_ui_state(self):
        ready = (self.target_data is not None) and (self.di_audio is not None)
        self.btn_start_loop.setEnabled(ready)
        if ready:
            self.lbl_status.setText("Listo para iniciar el Ajuste Manual.")

    def setup_brightness_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_brightness)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Profile selection
        profile_layout = QtWidgets.QHBoxLayout()
        profile_layout.addWidget(QtWidgets.QLabel("Target Profile:"))
        self.target_sel = QtWidgets.QComboBox()
        self.target_sel.addItems(["None", "AMBIENT", "RHYTHM", "LEAD"])
        self.target_sel.currentTextChanged.connect(self.on_profile_changed)
        profile_layout.addWidget(self.target_sel)
        layout.addLayout(profile_layout)

        info = QtWidgets.QLabel(
            "Inicia el loop en tiempo real y mueve manualmente los parámetros del amplificador\n"
            "o el micrófono en tu Helix para aproximar la respuesta espectral y métricas."
        )
        info.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(info)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_start_loop = QtWidgets.QPushButton("Iniciar Loop")
        self.btn_start_loop.setObjectName("AccentButton")
        self.btn_start_loop.setEnabled(False)
        self.btn_start_loop.clicked.connect(self.toggle_manual_loop)
        
        self.btn_fix_manual = QtWidgets.QPushButton("Fijar Ajuste y Continuar")
        self.btn_fix_manual.setEnabled(False)
        self.btn_fix_manual.clicked.connect(self.fix_manual_and_continue)
        
        btn_layout.addWidget(self.btn_start_loop)
        btn_layout.addWidget(self.btn_fix_manual)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def setup_amp_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_amp)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        form = QtWidgets.QFormLayout()
        self.cc_bass = QtWidgets.QSpinBox()
        self.cc_bass.setRange(0, 127)
        self.cc_bass.setValue(18)
        self.cc_mid = QtWidgets.QSpinBox()
        self.cc_mid.setRange(0, 127)
        self.cc_mid.setValue(19)
        self.cc_treble = QtWidgets.QSpinBox()
        self.cc_treble.setRange(0, 127)
        self.cc_treble.setValue(20)
        self.cc_presence = QtWidgets.QSpinBox()
        self.cc_presence.setRange(0, 127)
        self.cc_presence.setValue(21)

        form.addRow("MIDI CC Graves:", self.cc_bass)
        form.addRow("MIDI CC Medios:", self.cc_mid)
        form.addRow("MIDI CC Agudos:", self.cc_treble)
        form.addRow("MIDI CC Presencia:", self.cc_presence)
        layout.addLayout(form)

        self.btn_start_amp = QtWidgets.QPushButton("Iniciar Optimización de Amplificador")
        self.btn_start_amp.setObjectName("AccentButton")
        self.btn_start_amp.clicked.connect(self.start_goal_2)
        layout.addWidget(self.btn_start_amp)
        layout.addStretch()

    def setup_eq_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_eq)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QFormLayout(scroll_content)

        freqs = [31.25, 62.5, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
        default_ccs = [30, 31, 33, 34, 35, 36, 37, 38, 39, 40]  # Skips reserved CC 32
        
        self.cc_bands = []
        for i, f in enumerate(freqs):
            spin = QtWidgets.QSpinBox()
            spin.setRange(0, 127)
            spin.setValue(default_ccs[i])
            scroll_layout.addRow(f"MIDI CC Banda {f} Hz:", spin)
            self.cc_bands.append(spin)

        self.cc_eq_level = QtWidgets.QSpinBox()
        self.cc_eq_level.setRange(0, 127)
        self.cc_eq_level.setValue(41)
        scroll_layout.addRow("MIDI CC Level (Gain):", self.cc_eq_level)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self.btn_start_eq = QtWidgets.QPushButton("Iniciar Match de EQ y Nivel")
        self.btn_start_eq.setObjectName("AccentButton")
        self.btn_start_eq.clicked.connect(self.start_goal_3)
        layout.addWidget(self.btn_start_eq)

    def load_target_profiles(self):
        json_path = os.path.join("utils", "target_profiles.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading target profiles: {e}")
        return {
            "AMBIENT": {"brightness_min": 600.0, "brightness_max": 1500.0, "lufs_min": -22.0, "lufs_max": -16.0},
            "RHYTHM": {"brightness_min": 1200.0, "brightness_max": 2000.0, "lufs_min": -18.0, "lufs_max": -14.0},
            "LEAD": {"brightness_min": 1900.0, "brightness_max": 2700.0, "lufs_min": -16.0, "lufs_max": -12.0}
        }

    def normalize_target_fft(self):
        if not self.target_data:
            return
            
        profile_name = self.target_sel.currentText()
        target_lufs = self.target_data['lufs'] # Default
        
        if profile_name != "None" and profile_name:
            profiles = self.load_target_profiles()
            profile = profiles.get(profile_name, {})
            l_min = profile.get("lufs_min")
            l_max = profile.get("lufs_max")
            if l_min is not None and l_max is not None:
                target_lufs = (l_min + l_max) / 2.0
                
        # Offset de diferencia de ganancia
        gain_db = target_lufs - self.target_data['lufs']
        gain_linear = 10 ** (gain_db / 20.0)
        self.target_data['normalized_spectrum'] = self.target_data['avg_spectrum'] * gain_linear

    def on_profile_changed(self, profile_name):
        # 1. Ajustar bandas visuales en el gráfico
        if profile_name == "None" or not profile_name:
            self.plot_widget.set_target_ranges([])
        else:
            profiles = self.load_target_profiles()
            profile = profiles.get(profile_name, {})
            
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
            
        # 2. Re-normalizar el espectro y actualizar el trazado del Target en tiempo real
        if self.target_data:
            self.normalize_target_fft()
            target_spec = self.target_data['normalized_spectrum']
            target_db = 20 * np.log10(target_spec + 1e-12)
            self.target_curve.setData(self.target_data['freqs'], target_db)
            self.plot_widget.auto_scale()

    def update_metrics_cards(self, target_only=False, processed_metrics=None):
        if not self.target_data:
            return
            
        # Target metrics (usar LUFS normalizado según el perfil en vez del crudo de entrada)
        profile_name = self.target_sel.currentText()
        t_lufs = self.target_data['lufs'] # Default
        
        if profile_name != "None" and profile_name:
            profiles = self.load_target_profiles()
            profile = profiles.get(profile_name, {})
            l_min = profile.get("lufs_min")
            l_max = profile.get("lufs_max")
            if l_min is not None and l_max is not None:
                t_lufs = (l_min + l_max) / 2.0

        t_plr = self.target_data['plr']
        t_peak = self.target_data['max_peak_db']
        t_sat = self.target_data.get('saturation', 0.0)
        t_bright = self.target_data.get('centroid', 0.0)
        t_sust = self.target_data.get('sustain', 0.0)
        
        if target_only or not processed_metrics:
            self.card_lufs.set_values(f"{t_lufs:.1f}", "---")
            self.card_plr.set_values(f"{t_plr:.1f}", "---")
            self.card_peak.set_values(f"{t_peak:.1f}", "---")
            self.card_sat.set_values(f"{t_sat:.0f}%", "---")
            self.card_bright.set_values(f"{t_bright:.0f} Hz", "---")
            self.card_sustain.set_values(f"{t_sust:.0f}%", "---")
            return
            
        # Processed metrics
        p_lufs = processed_metrics['lufs']
        p_plr = processed_metrics['plr']
        p_peak = processed_metrics['max_peak_db']
        p_sat = processed_metrics.get('saturation', 0.0)
        p_bright = processed_metrics.get('centroid', 0.0)
        p_sust = processed_metrics.get('sustain', 0.0)
        
        # Calculate deltas
        d_lufs = p_lufs - t_lufs
        d_plr = p_plr - t_plr
        d_peak = p_peak - t_peak
        d_sat = p_sat - t_sat
        d_bright = p_bright - t_bright
        d_sust = p_sust - t_sust
        
        # Set card values
        self.card_lufs.set_values(f"{t_lufs:.1f}", f"{p_lufs:.1f}", f"{d_lufs:+.1f} dB", "green" if abs(d_lufs) < 1.0 else "red")
        self.card_plr.set_values(f"{t_plr:.1f}", f"{p_plr:.1f}", f"{d_plr:+.1f}", "green" if abs(d_plr) < 1.5 else "red")
        self.card_peak.set_values(f"{t_peak:.1f}", f"{p_peak:.1f}", f"{d_peak:+.1f} dB", "green" if p_peak <= 0.0 else "red")
        self.card_sat.set_values(f"{t_sat:.0f}%", f"{p_sat:.0f}%", f"{d_sat:+.0f}%", "green" if abs(d_sat) < 10 else "red")
        self.card_bright.set_values(f"{t_bright:.0f} Hz", f"{p_bright:.0f} Hz", f"{d_bright:+.0f} Hz", "green" if abs(d_bright) < 150 else "red")
        self.card_sustain.set_values(f"{t_sust:.0f}%", f"{p_sust:.0f}%", f"{d_sust:+.0f}%", "green" if abs(d_sust) < 10 else "red")

    def send_midi(self, cc, value):
        if not self.midi_port:
            return
        try:
            with mido.open_output(self.midi_port) as port:
                msg = mido.Message('control_change', control=int(cc), value=int(value))
                port.send(msg)
        except Exception as e:
            print(f"Error sending MIDI CC {cc} = {value}: {e}")

    def prepare_audio_routing(self):
        self.audio_settings = self.main_window.conn_mgr.load_settings().get("connection")
        if not self.audio_settings:
            raise Exception("No hay un dispositivo de audio configurado.")

        in_id, out_id = self.audio_settings["device_id"]
        self.send_ch = self.audio_settings["out_channel"] - 1
        self.receive_ch = self.audio_settings["in_channel"] - 1

        self.actual_in_id = in_id if in_id is not None else out_id
        self.actual_out_id = out_id if out_id is not None else in_id

        self.num_in = self.receive_ch + 1
        self.num_out = self.send_ch + 1

        in_info = sd.query_devices(self.actual_in_id)
        self.native_sr = int(in_info['default_samplerate'])

        di_audio = self.di_audio
        if self.di_sr != self.native_sr:
            self.lbl_status.setText(f"Resampleando DI de {self.di_sr}Hz a {self.native_sr}Hz...")
            QtWidgets.QApplication.processEvents()
            from scipy.signal import resample
            num_samples = int(len(di_audio) * self.native_sr / self.di_sr)
            self.working_di_audio = resample(di_audio, num_samples).astype(np.float32)
        else:
            self.working_di_audio = di_audio

        self.play_array = np.zeros((len(self.working_di_audio), self.num_out), dtype=np.float32)
        self.play_array[:, self.send_ch] = self.working_di_audio

    # --- GOAL 1 / REAL-TIME LOOP IMPLEMENTATION ---
    def toggle_manual_loop(self):
        if self.is_looping:
            self.stop_manual_loop()
        else:
            self.start_manual_loop()

    def start_manual_loop(self):
        try:
            self.is_looping = True
            self.is_running = True
            self.goal_type = 'goal_1'
            self.midi_port = self.midi_port_combo.currentText()
            
            self.btn_start_loop.setText("Detener Loop")
            self.btn_start_loop.setStyleSheet("background-color: #FF4B2B; color: white; font-weight: bold;")
            self.btn_fix_manual.setEnabled(False)
            self.set_working_state(True)
            
            self.lbl_status.setText("Liberando dispositivo de audio...")
            QtWidgets.QApplication.processEvents()
            self.main_window.conn_mgr.stop_audio()
            
            self.prepare_audio_routing()
            
            self.lbl_status.setText("Loop en Tiempo Real activo (Reproduciendo/Grabando)...")
            # Iniciar primera vuelta del loop
            QtCore.QTimer.singleShot(1000, self.trigger_loop_iteration)
        except Exception as e:
            self.on_process_error(str(e))

    def stop_manual_loop(self):
        self.is_looping = False
        self.is_running = False
        self.loop_timer.stop()
        try:
            sd.stop()
        except:
            pass
        self.btn_start_loop.setText("Iniciar Loop")
        self.btn_start_loop.setStyleSheet("")
        self.btn_fix_manual.setEnabled(True)
        self.set_working_state(False)
        self.lbl_status.setText("Loop detenido. Ajustes listos para fijar.")
        
        # Reactivar el monitor normal de audio
        if self.audio_settings:
            QtCore.QTimer.singleShot(1200, lambda: self.main_window.conn_mgr.start_audio(self.audio_settings))

    def trigger_loop_iteration(self):
        if not self.is_looping:
            return
            
        try:
            self.record_array = np.zeros((len(self.play_array), self.num_in), dtype=np.float32)
            
            sd.playrec(
                self.play_array,
                samplerate=self.native_sr,
                device=(self.actual_in_id, self.actual_out_id),
                channels=self.num_in,
                out=self.record_array,
                blocking=False
            )
            
            # Programar el timer para procesar cuando termine la reproducción
            duration_ms = int((len(self.working_di_audio) / self.native_sr) * 1000)
            self.loop_timer.start(duration_ms + 150)
        except Exception as e:
            self.on_process_error(str(e))

    def process_loop_iteration(self):
        try:
            sd.stop()
        except:
            pass
            
        if not self.is_looping:
            return
            
        try:
            recorded_mono = self.record_array[:, self.receive_ch]
            
            comparator = AudioComparator(self.native_sr)
            metrics = comparator.calculate_metrics(recorded_mono)
            current_centroid = metrics.get('centroid', 0.0)
            
            # Plot processed DI FFT
            di_spec = metrics['avg_spectrum']
            di_db = 20 * np.log10(di_spec + 1e-12)
            self.di_curve.setData(metrics['freqs'], di_db)
            
            # Actualizar tarjetas de métricas
            self.update_metrics_cards(target_only=False, processed_metrics=metrics)
            
            # Guardar últimas métricas en el widget para la siguiente fase
            self.manual_di_metrics = metrics
            
            # Re-disparar el loop tras un breve respiro
            QtCore.QTimer.singleShot(150, self.trigger_loop_iteration)
        except Exception as e:
            self.on_process_error(str(e))

    def fix_manual_and_continue(self):
        # Desbloquear Amp EQ
        self.tabs.setTabEnabled(1, True)
        self.tabs.setCurrentIndex(1)
        QtWidgets.QMessageBox.information(self, "Ajuste Manual Completado", "Ajuste manual fijado correctamente. Pasando a optimización de Amp EQ.")

    # --- GOAL 2 (AMP EQ OPTIMIZATION) ---
    def start_goal_2(self):
        try:
            self.is_running = True
            self.goal_type = 'goal_2'
            self.midi_port = self.midi_port_combo.currentText()
            ccs = [self.cc_bass.value(), self.cc_mid.value(), self.cc_treble.value(), self.cc_presence.value()]

            self.set_working_state(True)
            self.lbl_status.setText("Reseteando amplificador y EQ en la Helix al 50% (0 dB)...")
            QtWidgets.QApplication.processEvents()

            # 1. Resetear Tonestack del Amplificador a 50% (valor 64)
            for cc in ccs:
                self.send_midi(cc, 64)
                time.sleep(0.05)

            # 2. Resetear las 10 bandas de EQ quirúrgico a 50% (0dB, valor 64)
            eq_ccs = [spin.value() for spin in self.cc_bands]
            for cc in eq_ccs:
                self.send_midi(cc, 64)
                time.sleep(0.05)

            # 3. Resetear el Level del EQ a 50% (0dB, valor 64)
            self.send_midi(self.cc_eq_level.value(), 64)
            time.sleep(0.1)

            self.lbl_status.setText("Liberando dispositivo de audio...")
            QtWidgets.QApplication.processEvents()
            
            self.main_window.conn_mgr.stop_audio()
            
            self.prepare_audio_routing()

            # Create and start worker
            self.g2_worker = AmpOptimizeWorker(ccs, self.target_data, self.native_sr)
            self.g2_worker.request_eval_sig.connect(self.on_g2_eval_request)
            self.g2_worker.status_sig.connect(self.on_worker_progress)
            self.g2_worker.finished_sig.connect(self.on_g2_finished)

            QtCore.QTimer.singleShot(1000, self.g2_worker.start)
        except Exception as e:
            self.on_process_error(str(e))

    def on_g2_eval_request(self, cc_vals):
        if not self.is_running:
            return
        
        # Send MIDI CCs: Bass, Mid, Treble, Presence
        ccs = [self.cc_bass.value(), self.cc_mid.value(), self.cc_treble.value(), self.cc_presence.value()]
        for cc, val in zip(ccs, cc_vals):
            self.send_midi(cc, val)
            
        QtCore.QTimer.singleShot(300, lambda: self.playrec_step_goal_2(cc_vals))

    def playrec_step_goal_2(self, cc_vals):
        if not self.is_running:
            return
            
        try:
            self.record_array = np.zeros((len(self.play_array), self.num_in), dtype=np.float32)
            
            sd.playrec(
                self.play_array,
                samplerate=self.native_sr,
                device=(self.actual_in_id, self.actual_out_id),
                channels=self.num_in,
                out=self.record_array,
                blocking=False
            )
            
            duration_ms = int((len(self.working_di_audio) / self.native_sr) * 1000)
            QtCore.QTimer.singleShot(duration_ms + 250, lambda: self.process_recorded_step_goal_2(cc_vals))
        except Exception as e:
            if self.g2_worker:
                self.g2_worker.set_evaluation_result(9999.0, {})

    def process_recorded_step_goal_2(self, cc_vals):
        try:
            sd.stop()
        except:
            pass
            
        if not self.is_running:
            return
            
        try:
            recorded_mono = self.record_array[:, self.receive_ch]
            
            comparator = AudioComparator(self.native_sr)
            metrics = comparator.calculate_metrics(recorded_mono)
            
            # Plot processed DI FFT
            di_spec = metrics['avg_spectrum']
            di_db = 20 * np.log10(di_spec + 1e-12)
            self.di_curve.setData(metrics['freqs'], di_db)
            
            self.update_metrics_cards(target_only=False, processed_metrics=metrics)
            
            # Calculate MSE in 62.5Hz - 10000Hz range
            freqs = metrics['freqs']
            mask = (freqs >= 62.5) & (freqs <= 10000)
            
            target_spec = self.target_data['normalized_spectrum']
            target_db = 20 * np.log10(target_spec + 1e-12)
            
            mse = np.mean((target_db[mask] - di_db[mask]) ** 2)
            
            # Return result to worker thread
            if self.g2_worker:
                self.g2_worker.set_evaluation_result(mse, metrics)
        except Exception as e:
            if self.g2_worker:
                self.g2_worker.set_evaluation_result(9999.0, {})

    def on_g2_finished(self, success, message, best_x):
        if success and best_x and self.is_running:
            ccs = [self.cc_bass.value(), self.cc_mid.value(), self.cc_treble.value(), self.cc_presence.value()]
            for cc, val in zip(ccs, best_x):
                self.send_midi(cc, val)
            
            self.lbl_status.setText("Realizando grabación de verificación final para Goal 2...")
            QtWidgets.QApplication.processEvents()
            QtCore.QTimer.singleShot(500, lambda: self.playrec_verification_goal_2(success, message))
        else:
            self.on_process_finished(success, message)

    def playrec_verification_goal_2(self, success, message):
        if not self.is_running:
            self.on_process_finished(False, "Cancelado por el usuario")
            return
            
        try:
            self.record_array = np.zeros((len(self.play_array), self.num_in), dtype=np.float32)
            sd.playrec(
                self.play_array,
                samplerate=self.native_sr,
                device=(self.actual_in_id, self.actual_out_id),
                channels=self.num_in,
                out=self.record_array,
                blocking=False
            )
            duration_ms = int((len(self.working_di_audio) / self.native_sr) * 1000)
            QtCore.QTimer.singleShot(duration_ms + 250, lambda: self.process_verification_goal_2(success, message))
        except Exception as e:
            self.on_process_finished(False, f"Error en verificación final Goal 2: {str(e)}")

    def process_verification_goal_2(self, success, message):
        try:
            sd.stop()
        except:
            pass
            
        if not self.is_running:
            return
            
        try:
            recorded_mono = self.record_array[:, self.receive_ch]
            comparator = AudioComparator(self.native_sr)
            metrics = comparator.calculate_metrics(recorded_mono)
            
            # Plot final verification processed DI FFT
            di_spec = metrics['avg_spectrum']
            di_db = 20 * np.log10(di_spec + 1e-12)
            self.di_curve.setData(metrics['freqs'], di_db)
            
            self.update_metrics_cards(target_only=False, processed_metrics=metrics)
        except Exception as e:
            print(f"Error procesando verificación Goal 2: {e}")
            
        self.on_process_finished(success, message)

    # --- GOAL 3 (SURGICAL EQ) & GOAL 4 (LOUDNESS LEVELING) ---
    def start_goal_3(self):
        try:
            self.is_running = True
            self.goal_type = 'goal_3'
            self.midi_port = self.midi_port_combo.currentText()

            self.set_working_state(True)
            self.lbl_status.setText("Liberando dispositivo de audio...")
            self.progress_bar.setValue(0)
            QtWidgets.QApplication.processEvents()
            
            self.main_window.conn_mgr.stop_audio()
            
            self.prepare_audio_routing()

            # Set EQ Level to 0dB (MIDI CC 41 = 64) before starting EQ correction
            self.send_midi(self.cc_eq_level.value(), 64)
            time.sleep(0.1)

            self.lbl_status.setText("Grabando estado actual (sin EQ quirúrgico) para análisis...")
            QtWidgets.QApplication.processEvents()
            
            QtCore.QTimer.singleShot(1000, self.playrec_step_1_goal_3)
        except Exception as e:
            self.on_process_error(str(e))

    def playrec_step_1_goal_3(self):
        if not self.is_running:
            self.on_process_finished(False, "Cancelado por el usuario")
            return

        try:
            self.record_array = np.zeros((len(self.play_array), self.num_in), dtype=np.float32)
            
            sd.playrec(
                self.play_array,
                samplerate=self.native_sr,
                device=(self.actual_in_id, self.actual_out_id),
                channels=self.num_in,
                out=self.record_array,
                blocking=False
            )
            
            duration_ms = int((len(self.working_di_audio) / self.native_sr) * 1000)
            QtCore.QTimer.singleShot(duration_ms + 250, self.process_recorded_step_1_goal_3)
        except Exception as e:
            self.on_process_error(str(e))

    def process_recorded_step_1_goal_3(self):
        try:
            sd.stop()
        except:
            pass

        if not self.is_running:
            self.on_process_finished(False, "Cancelado por el usuario")
            return

        try:
            recorded_mono = self.record_array[:, self.receive_ch]
            
            comparator = AudioComparator(self.native_sr)
            metrics = comparator.calculate_metrics(recorded_mono)
            
            # Frequencies of 10-band EQ
            eq_freqs = [31.25, 62.5, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
            
            # Convert spectrums to dB
            target_spec = self.target_data['normalized_spectrum']
            target_db = 20 * np.log10(target_spec + 1e-12)
            
            current_spec = metrics['avg_spectrum']
            current_db = 20 * np.log10(current_spec + 1e-12)
            
            # Interpolate to find values at exact EQ frequencies
            target_interp = np.interp(eq_freqs, self.target_data['freqs'], target_db)
            current_interp = np.interp(eq_freqs, metrics['freqs'], current_db)
            
            # Calculate dB difference
            diff_db = target_interp - current_interp
            
            self.lbl_status.setText("Calculando y enviando valores de EQ de 10 bandas a la Helix...")
            self.progress_bar.setValue(35)
            QtWidgets.QApplication.processEvents()
            
            # Send CCs
            ccs = [spin.value() for spin in self.cc_bands]
            for i, diff in enumerate(diff_db):
                freq = eq_freqs[i]
                if freq < 62.5 or freq > 10000.0:
                    diff = 0.0
                # Helix range is -15dB to +15dB. Linear mapping: -15dB -> CC 0, +15dB -> CC 127
                clipped_diff = np.clip(diff, -15.0, 15.0)
                cc_val = int(((clipped_diff + 15.0) / 30.0) * 127)
                self.send_midi(ccs[i], cc_val)
                print(f"Banda {eq_freqs[i]} Hz: Diff = {diff:+.2f} dB (Filtro 62.5-10k Hz), Enviando MIDI CC {ccs[i]} = {cc_val}")
                
            time.sleep(0.3)  # Wait for MIDI buffer to clean and Helix to apply
            
            self.lbl_status.setText("Realizando grabación intermedia para ajuste de volumen...")
            self.progress_bar.setValue(55)
            QtWidgets.QApplication.processEvents()
            
            QtCore.QTimer.singleShot(500, self.playrec_step_lufs_calib)
        except Exception as e:
            self.on_process_error(str(e))

    def playrec_step_lufs_calib(self):
        if not self.is_running:
            self.on_process_finished(False, "Cancelado por el usuario")
            return

        try:
            self.record_array = np.zeros((len(self.play_array), self.num_in), dtype=np.float32)
            
            sd.playrec(
                self.play_array,
                samplerate=self.native_sr,
                device=(self.actual_in_id, self.actual_out_id),
                channels=self.num_in,
                out=self.record_array,
                blocking=False
            )
            
            duration_ms = int((len(self.working_di_audio) / self.native_sr) * 1000)
            QtCore.QTimer.singleShot(duration_ms + 250, self.process_recorded_step_lufs_calib)
        except Exception as e:
            self.on_process_error(str(e))

    def process_recorded_step_lufs_calib(self):
        try:
            sd.stop()
        except:
            pass

        if not self.is_running:
            self.on_process_finished(False, "Cancelado por el usuario")
            return

        try:
            recorded_mono = self.record_array[:, self.receive_ch]
            comparator = AudioComparator(self.native_sr)
            metrics = comparator.calculate_metrics(recorded_mono)
            
            current_lufs = metrics['lufs']
            
            # --- GOAL 4 LUFS Target Calculation ---
            profile_name = self.target_sel.currentText()
            target_lufs = self.target_data['lufs'] # Default fallback
            
            if profile_name != "None" and profile_name:
                profiles = self.load_target_profiles()
                profile = profiles.get(profile_name, {})
                l_min = profile.get("lufs_min")
                l_max = profile.get("lufs_max")
                if l_min is not None and l_max is not None:
                    target_lufs = (l_min + l_max) / 2.0
                    print(f"LUFS Target según Perfil {profile_name}: {target_lufs:.1f} LUFS (Rango: {l_min} a {l_max})")

            delta_lufs = target_lufs - current_lufs
            print(f"Nivelación LUFS: Actual={current_lufs:.1f}, Objetivo={target_lufs:.1f}, Delta={delta_lufs:+.1f} dB")
            
            # EQ Level CC 41. Level parameter in Helix Graphic EQ goes from -15dB (0) to +15dB (127).
            # Initial state was 0dB (64).
            new_level_db = np.clip(delta_lufs, -15.0, 15.0)
            cc_val = int(((new_level_db + 15.0) / 30.0) * 127)
            
            self.lbl_status.setText(f"Nivelando volumen (Level EQ CC {self.cc_eq_level.value()} = {cc_val})...")
            self.progress_bar.setValue(75)
            QtWidgets.QApplication.processEvents()
            
            self.send_midi(self.cc_eq_level.value(), cc_val)
            time.sleep(0.3)
            
            self.lbl_status.setText("Realizando grabación de verificación final...")
            QtWidgets.QApplication.processEvents()
            QtCore.QTimer.singleShot(500, self.playrec_step_2_goal_3)
        except Exception as e:
            self.on_process_error(str(e))

    def playrec_step_2_goal_3(self):
        if not self.is_running:
            self.on_process_finished(False, "Cancelado por el usuario")
            return

        try:
            self.record_array = np.zeros((len(self.play_array), self.num_in), dtype=np.float32)
            
            sd.playrec(
                self.play_array,
                samplerate=self.native_sr,
                device=(self.actual_in_id, self.actual_out_id),
                channels=self.num_in,
                out=self.record_array,
                blocking=False
            )
            
            duration_ms = int((len(self.working_di_audio) / self.native_sr) * 1000)
            QtCore.QTimer.singleShot(duration_ms + 250, self.process_verification_goal_3)
        except Exception as e:
            self.on_process_error(str(e))

    def process_verification_goal_3(self):
        try:
            sd.stop()
        except:
            pass

        if not self.is_running:
            self.on_process_finished(False, "Cancelado por el usuario")
            return

        try:
            recorded_mono = self.record_array[:, self.receive_ch]
            
            comparator = AudioComparator(self.native_sr)
            metrics = comparator.calculate_metrics(recorded_mono)
            
            # Plot final verification processed DI FFT
            di_spec = metrics['avg_spectrum']
            di_db = 20 * np.log10(di_spec + 1e-12)
            self.di_curve.setData(metrics['freqs'], di_db)
            
            # Actualizar tarjetas de métricas finales
            self.update_metrics_cards(target_only=False, processed_metrics=metrics)
            
            self.progress_bar.setValue(100)
            QtWidgets.QApplication.processEvents()
            
            self.on_process_finished(True, "¡Proceso de Tone Matcher finalizado con éxito tras aplicar EQ quirúrgico y nivelación de volumen!")
        except Exception as e:
            self.on_process_error(str(e))

    def on_worker_progress(self, progress, text):
        self.progress_bar.setValue(progress)
        self.lbl_status.setText(text)

    def on_process_error(self, err_msg):
        self.on_process_finished(False, f"Error: {err_msg}")

    def on_process_finished(self, success, message):
        self.is_running = False
        self.set_working_state(False)
        self.lbl_status.setText(message)
        
        if self.audio_settings:
            self.lbl_status.setText("Reactivando monitor de audio...")
            QtWidgets.QApplication.processEvents()
            QtCore.QTimer.singleShot(1200, lambda: self.restart_main_audio(success, message))
        else:
            self.show_popup_message(success, message)

    def restart_main_audio(self, success, message):
        try:
            self.main_window.conn_mgr.start_audio(self.audio_settings)
        except Exception as e:
            print(f"Error restarting main audio: {e}")
        self.show_popup_message(success, message)

    def show_popup_message(self, success, message):
        if success:
            if self.goal_type == 'goal_1':
                self.tabs.setTabEnabled(1, True)
                self.tabs.setCurrentIndex(1)
                QtWidgets.QMessageBox.information(self, "Ajuste Manual Completado", message)
            elif self.goal_type == 'goal_2':
                self.tabs.setTabEnabled(2, True)
                self.tabs.setCurrentIndex(2)
                QtWidgets.QMessageBox.information(self, "Optimización de Amplificador Completada", message)
            elif self.goal_type == 'goal_3':
                QtWidgets.QMessageBox.information(self, "Tone Matcher Finalizado", "¡Tone Matcher completado con éxito!")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", message)

    def cancel_matching(self):
        self.is_running = False
        self.is_looping = False
        self.loop_timer.stop()
        try:
            sd.stop()
        except:
            pass
        if self.goal_type == 'goal_2' and hasattr(self, 'g2_worker') and self.g2_worker:
            self.g2_worker.cancel()
        
        self.on_process_finished(False, "Proceso cancelado por el usuario.")

    def set_working_state(self, is_working):
        self.btn_load_target.setEnabled(not is_working)
        self.btn_load_di.setEnabled(not is_working)
        
        # Ocultar botones de pestañas inactivas para no confundir al usuario durante un proceso activo
        if is_working:
            if self.goal_type == 'goal_1':
                self.btn_start_amp.setVisible(False)
                self.btn_start_eq.setVisible(False)
            elif self.goal_type == 'goal_2':
                self.btn_start_loop.setVisible(False)
                self.btn_fix_manual.setVisible(False)
                self.btn_start_eq.setVisible(False)
            elif self.goal_type == 'goal_3':
                self.btn_start_loop.setVisible(False)
                self.btn_fix_manual.setVisible(False)
                self.btn_start_amp.setVisible(False)
        else:
            self.btn_start_loop.setVisible(True)
            self.btn_fix_manual.setVisible(True)
            self.btn_start_amp.setVisible(True)
            self.btn_start_eq.setVisible(True)

        # Deshabilitar parámetros y selectores de CCs para que el usuario no los edite a mitad de optimización
        self.target_sel.setEnabled(not is_working)
        self.cc_bass.setEnabled(not is_working)
        self.cc_mid.setEnabled(not is_working)
        self.cc_treble.setEnabled(not is_working)
        self.cc_presence.setEnabled(not is_working)
        self.cc_eq_level.setEnabled(not is_working)
        for spin in self.cc_bands:
            spin.setEnabled(not is_working)

        # Permitir interactuar con el botón del loop manual incluso cuando se está procesando el loop
        if self.is_looping:
            self.btn_start_loop.setEnabled(True)
        else:
            self.btn_start_loop.setEnabled(not is_working and (self.target_data is not None) and (self.di_audio is not None))
            
        self.btn_start_amp.setEnabled(not is_working)
        self.btn_start_eq.setEnabled(not is_working)
        self.btn_cancel.setEnabled(is_working)
        
        # En vez de deshabilitar self.tabs por completo (lo cual deshabilita a todos sus widgets hijos),
        # deshabilitamos las pestañas individuales en la barra de pestañas para que no se pueda cambiar de una a otra.
        self.tabs.tabBar().setEnabled(not is_working)
