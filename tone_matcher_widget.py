import os
import time
import numpy as np
import soundfile as sf
import sounddevice as sd
import mido
from PySide6 import QtCore, QtWidgets, QtGui
import qtawesome as qta
from audio_comparator import AudioComparator
from ui_utils import FrequencyPlotWidget

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
        self.goal_type = None
        self.midi_port = None
        
        # Goal 1 state variables
        self.g1_cc = None
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

        self.init_ui()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

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

        # --- SPLIT LAYOUT PANEL (Left: Controls, Right: FFT Plot) ---
        split_layout = QtWidgets.QHBoxLayout()
        split_layout.setSpacing(15)

        # LEFT SIDE: Controls Panel
        left_panel = QtWidgets.QWidget()
        left_panel.setFixedWidth(500)
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        # File loaders card
        files_frame = QtWidgets.QFrame()
        files_frame.setObjectName("MetricCard")
        files_layout = QtWidgets.QGridLayout(files_frame)
        files_layout.setContentsMargins(15, 15, 15, 15)
        files_layout.setSpacing(10)

        # Target file loader
        files_layout.addWidget(QtWidgets.QLabel("Target File (.wav):"), 0, 0)
        self.lbl_target_file = QtWidgets.QLabel("Ningún archivo cargado")
        self.lbl_target_file.setStyleSheet("color: #888;")
        files_layout.addWidget(self.lbl_target_file, 0, 1)
        self.btn_load_target = QtWidgets.QPushButton("Cargar Target...")
        self.btn_load_target.clicked.connect(self.load_target_file)
        files_layout.addWidget(self.btn_load_target, 0, 2)

        # DI file loader
        files_layout.addWidget(QtWidgets.QLabel("Guitar DI File (.wav):"), 1, 0)
        self.lbl_di_file = QtWidgets.QLabel("Ningún archivo cargado")
        self.lbl_di_file.setStyleSheet("color: #888;")
        files_layout.addWidget(self.lbl_di_file, 1, 1)
        self.btn_load_di = QtWidgets.QPushButton("Cargar Guitar DI...")
        self.btn_load_di.clicked.connect(self.load_di_file)
        files_layout.addWidget(self.btn_load_di, 1, 2)

        left_layout.addWidget(files_frame)

        # Tab Widget for Goals
        self.tabs = QtWidgets.QTabWidget()
        
        # Tab 1: Spectral Brightness
        self.tab_brightness = QtWidgets.QWidget()
        self.setup_brightness_tab()
        self.tabs.addTab(self.tab_brightness, "BRIGHTNESS (G1)")

        # Tab 2: Amp EQ (Initially disabled)
        self.tab_amp = QtWidgets.QWidget()
        self.setup_amp_tab()
        self.tabs.addTab(self.tab_amp, "AMP EQ (G2)")
        self.tabs.setTabEnabled(1, False)

        # Tab 3: EQ (Initially disabled)
        self.tab_eq = QtWidgets.QWidget()
        self.setup_eq_tab()
        self.tabs.addTab(self.tab_eq, "SURGICAL EQ (G3)")
        self.tabs.setTabEnabled(2, False)

        left_layout.addWidget(self.tabs)
        split_layout.addWidget(left_panel)

        # RIGHT SIDE: Plot Panel
        self.plot_widget = FrequencyPlotWidget(y_range=(-80, 0))
        self.target_curve = self.plot_widget.add_curve("Target FFT", color='#FFAC41', width=2)
        self.di_curve = self.plot_widget.add_curve("Processed DI FFT", color='#00ADB5', width=2)
        
        # Info overlays inside plot area
        self.lbl_target_info = QtWidgets.QLabel("Target: - | Brillo: -")
        self.lbl_target_info.setStyleSheet("color: #FFAC41; font-weight: bold; background: transparent;")
        self.lbl_di_info = QtWidgets.QLabel("DI Procesada: - | Brillo: -")
        self.lbl_di_info.setStyleSheet("color: #00ADB5; font-weight: bold; background: transparent;")
        
        plot_overlay_layout = QtWidgets.QVBoxLayout()
        plot_overlay_layout.addWidget(self.lbl_target_info)
        plot_overlay_layout.addWidget(self.lbl_di_info)
        plot_overlay_layout.addStretch()
        
        # Add overlay layouts safely
        self.plot_widget.setLayout(plot_overlay_layout)

        split_layout.addWidget(self.plot_widget)
        main_layout.addLayout(split_layout)

        # --- PROGRESS & STATUS BAR ---
        status_layout = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setValue(0)
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
                
                self.lbl_target_file.setText(os.path.basename(path))
                self.lbl_target_file.setStyleSheet("color: #00ADB5; font-weight: bold;")
                self.lbl_status.setText("Target cargado con éxito.")
                
                # Plot target FFT
                target_spec = self.target_data['avg_spectrum']
                target_db = 20 * np.log10(target_spec + 1e-12)
                self.target_curve.setData(self.target_data['freqs'], target_db)
                
                self.lbl_target_info.setText(f"Target: {self.target_data['lufs']:.1f} LUFS | Brillo: {self.target_data['centroid']:.1f} Hz")

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
        self.btn_start_brightness.setEnabled(ready)
        if ready:
            self.lbl_status.setText("Listo para iniciar Spectral Brightness (GOAL 1)")

    def setup_brightness_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_brightness)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        form = QtWidgets.QFormLayout()
        self.cc_mic_pos = QtWidgets.QSpinBox()
        self.cc_mic_pos.setRange(0, 127)
        self.cc_mic_pos.setValue(17)
        form.addRow("MIDI CC (Mic Position):", self.cc_mic_pos)
        layout.addLayout(form)

        info = QtWidgets.QLabel(
            "El sistema probará 11 posiciones del mic de 0% a 100% de a 10% en tu Helix,\n"
            "analizando el brillo espectral de la señal procesada para encontrar el mejor valor."
        )
        info.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(info)

        self.btn_start_brightness = QtWidgets.QPushButton("Iniciar Match de Mic Position (GOAL 1)")
        self.btn_start_brightness.setObjectName("AccentButton")
        self.btn_start_brightness.setEnabled(False)
        self.btn_start_brightness.clicked.connect(self.start_goal_1)
        layout.addWidget(self.btn_start_brightness)
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

        self.btn_start_amp = QtWidgets.QPushButton("Iniciar Match de Amp EQ (GOAL 2)")
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

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self.btn_start_eq = QtWidgets.QPushButton("Iniciar Match de 10-Band EQ (GOAL 3)")
        self.btn_start_eq.setObjectName("AccentButton")
        self.btn_start_eq.clicked.connect(self.start_goal_3)
        layout.addWidget(self.btn_start_eq)

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

    def start_goal_1(self):
        try:
            self.is_running = True
            self.goal_type = 'goal_1'
            self.midi_port = self.midi_port_combo.currentText()
            self.g1_cc = self.cc_mic_pos.value()
            self.g1_current_idx = 0
            self.g1_best_diff = float('inf')
            self.g1_best_cc_val = 0
            self.g1_best_centroid = 0

            self.set_working_state(True)
            self.lbl_status.setText("Liberando dispositivo de audio...")
            QtWidgets.QApplication.processEvents()
            
            self.main_window.conn_mgr.stop_audio()
            
            self.prepare_audio_routing()

            QtCore.QTimer.singleShot(1000, self.loop_step_goal_1)
        except Exception as e:
            self.on_process_error(str(e))

    def loop_step_goal_1(self):
        if not self.is_running:
            self.on_process_finished(False, "Cancelado por el usuario")
            return

        if self.g1_current_idx >= len(self.g1_steps):
            self.lbl_status.setText(f"Finalizado. Aplicando mejor CC {self.g1_best_cc_val}...")
            self.progress_bar.setValue(100)
            QtWidgets.QApplication.processEvents()
            self.send_midi(self.g1_cc, self.g1_best_cc_val)
            time.sleep(0.3)
            self.on_process_finished(True, f"Mejor Mic Position encontrado en CC val {self.g1_best_cc_val} (Centroid: {self.g1_best_centroid:.1f} Hz, Target: {self.target_data['centroid']:.1f} Hz)")
            return

        pct = self.g1_steps[self.g1_current_idx]
        cc_val = int((pct / 100.0) * 127)
        self.progress_bar.setValue(int((self.g1_current_idx / len(self.g1_steps)) * 100))
        self.lbl_status.setText(f"Paso {self.g1_current_idx+1}/{len(self.g1_steps)}: Mic al {pct}% (CC {cc_val})...")
        QtWidgets.QApplication.processEvents()

        self.send_midi(self.g1_cc, cc_val)
        QtCore.QTimer.singleShot(350, lambda: self.playrec_step_goal_1(cc_val))

    def playrec_step_goal_1(self, cc_val):
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
            QtCore.QTimer.singleShot(duration_ms + 250, lambda: self.process_recorded_step_goal_1(cc_val))
        except Exception as e:
            self.on_process_error(str(e))

    def process_recorded_step_goal_1(self, cc_val):
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
            current_centroid = metrics.get('centroid', 0.0)
            
            # Plot current processed DI FFT
            di_spec = metrics['avg_spectrum']
            di_db = 20 * np.log10(di_spec + 1e-12)
            self.di_curve.setData(metrics['freqs'], di_db)
            
            self.lbl_di_info.setText(f"DI Procesada (CC {cc_val}): {metrics['lufs']:.1f} LUFS | Brillo: {current_centroid:.1f} Hz")
            
            target_centroid = self.target_data['centroid']
            diff = abs(current_centroid - target_centroid)
            
            if diff < self.g1_best_diff:
                self.g1_best_diff = diff
                self.g1_best_cc_val = cc_val
                self.g1_best_centroid = current_centroid

            self.g1_current_idx += 1
            QtCore.QTimer.singleShot(150, self.loop_step_goal_1)
        except Exception as e:
            self.on_process_error(str(e))

    def start_goal_2(self):
        try:
            self.is_running = True
            self.goal_type = 'goal_2'
            self.midi_port = self.midi_port_combo.currentText()
            ccs = [self.cc_bass.value(), self.cc_mid.value(), self.cc_treble.value(), self.cc_presence.value()]

            self.set_working_state(True)
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
            
            # Calculate MSE in 80Hz - 8000Hz range
            freqs = metrics['freqs']
            mask = (freqs >= 80) & (freqs <= 8000)
            
            target_spec = self.target_data['avg_spectrum']
            target_db = 20 * np.log10(target_spec + 1e-12)
            
            mse = np.mean((target_db[mask] - di_db[mask]) ** 2)
            
            self.lbl_di_info.setText(f"DI B={cc_vals[0]} M={cc_vals[1]} T={cc_vals[2]} P={cc_vals[3]} | MSE: {mse:.2f}")
            
            # Return result to worker thread
            if self.g2_worker:
                self.g2_worker.set_evaluation_result(mse, metrics)
        except Exception as e:
            if self.g2_worker:
                self.g2_worker.set_evaluation_result(9999.0, {})

    def on_g2_finished(self, success, message, best_x):
        if success and best_x:
            ccs = [self.cc_bass.value(), self.cc_mid.value(), self.cc_treble.value(), self.cc_presence.value()]
            for cc, val in zip(ccs, best_x):
                self.send_midi(cc, val)
            time.sleep(0.2)
        
        self.on_process_finished(success, message)

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
            target_spec = self.target_data['avg_spectrum']
            target_db = 20 * np.log10(target_spec + 1e-12)
            
            current_spec = metrics['avg_spectrum']
            current_db = 20 * np.log10(current_spec + 1e-12)
            
            # Interpolate to find values at exact EQ frequencies
            target_interp = np.interp(eq_freqs, self.target_data['freqs'], target_db)
            current_interp = np.interp(eq_freqs, metrics['freqs'], current_db)
            
            # Calculate dB difference
            diff_db = target_interp - current_interp
            
            self.lbl_status.setText("Calculando y enviando valores de EQ de 10 bandas a la Helix...")
            self.progress_bar.setValue(50)
            QtWidgets.QApplication.processEvents()
            
            # Send CCs
            ccs = [spin.value() for spin in self.cc_bands]
            for i, diff in enumerate(diff_db):
                # Helix range is -15dB to +15dB. Linear mapping: -15dB -> CC 0, +15dB -> CC 127
                clipped_diff = np.clip(diff, -15.0, 15.0)
                cc_val = int(((clipped_diff + 15.0) / 30.0) * 127)
                self.send_midi(ccs[i], cc_val)
                print(f"Banda {eq_freqs[i]} Hz: Diff = {diff:+.2f} dB, Enviando MIDI CC {ccs[i]} = {cc_val}")
                
            time.sleep(0.3)  # Wait for MIDI buffer to clean and Helix to apply
            
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
            
            self.lbl_di_info.setText(f"DI Final (EQ Quirúrgico): {metrics['lufs']:.1f} LUFS | Brillo: {metrics['centroid']:.1f} Hz")
            
            self.progress_bar.setValue(100)
            QtWidgets.QApplication.processEvents()
            
            self.on_process_finished(True, "¡Proceso de Tone Matcher finalizado con éxito tras aplicar EQ quirúrgico!")
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
                QtWidgets.QMessageBox.information(self, "GOAL 1 Completado", message)
            elif self.goal_type == 'goal_2':
                self.tabs.setTabEnabled(2, True)
                self.tabs.setCurrentIndex(2)
                QtWidgets.QMessageBox.information(self, "GOAL 2 Completado", message)
            elif self.goal_type == 'goal_3':
                QtWidgets.QMessageBox.information(self, "GOAL 3 Completado", "Tone Matcher completado con éxito!")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", message)

    def cancel_matching(self):
        self.is_running = False
        if self.goal_type == 'goal_2' and hasattr(self, 'g2_worker') and self.g2_worker:
            self.g2_worker.cancel()
        self.lbl_status.setText("Cancelando...")
        self.btn_cancel.setEnabled(False)

    def set_working_state(self, is_working):
        self.btn_load_target.setEnabled(not is_working)
        self.btn_load_di.setEnabled(not is_working)
        self.btn_start_brightness.setEnabled(not is_working and (self.target_data is not None) and (self.di_audio is not None))
        self.btn_start_amp.setEnabled(not is_working)
        self.btn_start_eq.setEnabled(not is_working)
        self.btn_cancel.setEnabled(is_working)
        self.tabs.setEnabled(not is_working)

