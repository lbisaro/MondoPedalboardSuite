import os
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets, QtGui
import shutil
from pathlib import Path
import qtawesome as qta
from audio_comparator import AudioComparator
from ui_utils import FrequencyPlotWidget, apply_smoothing, sanitize_filename

class PresetCompareWidget(QtWidgets.QWidget):
    def __init__(self, analyzer_core, parent=None):
        super().__init__(parent)
        self.analyzer_core = analyzer_core
        self.comparator = AudioComparator(sample_rate=48000)
        
        self.di_audio = None
        self.preset_a_audio = None
        self.preset_b_audio = None
        
        self.presets_path = Path("./user_data/di")
        old_path = Path("./user_data/guitar_di")
        if old_path.exists() and old_path.is_dir():
            if not self.presets_path.exists():
                self.presets_path.mkdir(parents=True, exist_ok=True)
            for item in old_path.iterdir():
                if item.is_file():
                    try: shutil.move(str(item), str(self.presets_path / item.name))
                    except: pass
            try: old_path.rmdir()
            except: pass
        else:
            self.presets_path.mkdir(parents=True, exist_ok=True)
        
        self.preset_a_metrics = None
        self.preset_b_metrics = None
        self.di_metrics = None 
        self.capture_running = False
        
        self.init_ui()
        self.refresh_preset_list()

    def init_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # --- PANEL IZQUIERDO: LIBRERIA ---
        self.left_panel = QtWidgets.QWidget()
        self.left_panel.setFixedWidth(240)
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        # Header
        header_lib = QtWidgets.QHBoxLayout()
        lbl_lib = QtWidgets.QLabel("GUITAR DI FILES")
        lbl_lib.setStyleSheet("font-weight: bold; color: #00ADB5; font-size: 10pt; letter-spacing: 1px;")
        
        self.btn_record_di = QtWidgets.QPushButton(qta.icon('fa5s.microphone', color='#FF4B2B'), "")
        self.btn_record_di.setFixedSize(24, 24)
        self.btn_record_di.setToolTip("Grabar DI desde la Pedalboard")
        self.btn_record_di.clicked.connect(self.record_di)
        self.btn_record_di.setStyleSheet("background: transparent; border: 1px solid #333; border-radius: 4px;")
        
        header_lib.addWidget(lbl_lib)
        header_lib.addStretch()
        header_lib.addWidget(self.btn_record_di)
        left_layout.addLayout(header_lib)
        
        self.list_presets = QtWidgets.QListWidget()
        self.list_presets.setObjectName("PresetList")
        self.list_presets.itemDoubleClicked.connect(self.on_preset_selected)
        left_layout.addWidget(self.list_presets)
        
        main_layout.addWidget(self.left_panel)
        
        # --- PANEL DERECHO ---
        self.right_panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.right_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.right_panel)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_back_to_lib = QtWidgets.QPushButton(qta.icon('fa5s.arrow-left', color='#00ADB5'), "")
        self.btn_back_to_lib.setVisible(False)
        self.btn_back_to_lib.clicked.connect(self.show_library)
        toolbar.addWidget(self.btn_back_to_lib)
        
        self.lbl_di_info = QtWidgets.QLabel("Selecciona un archivo DI para comenzar")
        self.lbl_di_info.setStyleSheet("color: #00ADB5; font-weight: bold; font-size: 10pt;")
        
        self.btn_capture_b = QtWidgets.QPushButton("Capturar PRESET B")
        self.btn_capture_b.setObjectName("AccentButton")
        self.btn_capture_b.setFixedHeight(35)
        self.btn_capture_b.setVisible(False)
        self.btn_capture_b.clicked.connect(lambda: self.capture_process("preset_b"))
        
        toolbar.addWidget(self.lbl_di_info)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_capture_b)
        layout.addLayout(toolbar)
        
        # Metrics
        self.dash_layout = QtWidgets.QHBoxLayout()
        self.card_lufs = MetricCard("Loudness (LUFS)", "---")
        self.card_lufs.setToolTip(
            "<b>LOUDNESS (LUFS):</b> Mide la sonoridad promedio percibida.<br><br>"
            "<b>Delta:</b> Indica la diferencia de volumen real. Si es (+), el Preset B suena más fuerte.<br>"
            "<b>Recomendación:</b> Ajusta el 'Level' o 'Channel Volume' en el bloque de salida de la PedalBoard para igualar los niveles."
        )
        self.card_plr = MetricCard("Dynamics (PLR)", "---")
        self.card_plr.setToolTip(
            "<b>DYNAMICS (PLR):</b> Peak-to-Loudness Ratio.<br><br>"
            "Indica qué tan comprimida está la señal respecto al original.<br>"
            "Un Delta (-) significa que el preset está comprimiendo la dinámica."
        )
        self.card_peak = MetricCard("Max Peak", "---")
        
        self.dash_layout.addWidget(self.card_lufs)
        self.dash_layout.addWidget(self.card_plr)
        self.dash_layout.addWidget(self.card_peak)
        layout.addLayout(self.dash_layout)
        
        # Plot
        self.plot_widget = FrequencyPlotWidget(y_range=(-60, 10))
        self.curve_di = self.plot_widget.add_curve("DI Original", color='#555555', width=1, style=QtCore.Qt.DashLine)
        self.curve_a = self.plot_widget.add_curve("Preset A", color='#00ADB5', width=2)
        self.curve_b = self.plot_widget.add_curve("Preset B", color='#FFAC41', width=2)
        self.diff_fill = pg.FillBetweenItem(self.curve_a, self.curve_b, brush=pg.mkBrush(0, 173, 181, 40))
        layout.addWidget(self.plot_widget)
        
        self.lbl_status = QtWidgets.QLabel("")
        self.lbl_status.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: #00ADB5; font-weight: bold; font-size: 10pt;")
        layout.addWidget(self.lbl_status)
        
        prog_layout = QtWidgets.QHBoxLayout()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setFixedHeight(10)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        
        self.btn_stop = QtWidgets.QPushButton("DETENER")
        self.btn_stop.setFixedSize(80, 24)
        self.btn_stop.setStyleSheet("background-color: #FF4B2B; color: white; font-size: 10pt; padding: 3px; font-weight: bold; border: none;")
        self.btn_stop.setVisible(False)
        self.btn_stop.clicked.connect(self.stop_capture)
        
        self.btn_cancel_record = QtWidgets.QPushButton("CANCELAR")
        self.btn_cancel_record.setFixedSize(80, 24)
        self.btn_cancel_record.setStyleSheet("background-color: #555; color: white; font-size: 10pt; padding: 3px; font-weight: bold; border: none;")
        self.btn_cancel_record.setVisible(False)
        self.btn_cancel_record.clicked.connect(self.stop_capture)
        
        prog_layout.addWidget(self.progress)
        prog_layout.addWidget(self.btn_stop)
        prog_layout.addWidget(self.btn_cancel_record)
        layout.addLayout(prog_layout)
        
        smooth_layout = QtWidgets.QHBoxLayout()
        smooth_layout.addWidget(QtWidgets.QLabel("Smoothing:"))
        self.smooth_sel = QtWidgets.QComboBox()
        self.smooth_sel.addItems(["None", "1/3 Octave", "1/6 Octave", "1/12 Octave"])
        
        parent_win = self.window()
        settings = parent_win.load_settings() if hasattr(parent_win, 'load_settings') else {}
        pref_smooth = settings.get("user_preferences", {}).get("smoothing", "1/6 Octave")
        self.smooth_sel.setCurrentText(pref_smooth)
        self.smooth_sel.currentTextChanged.connect(self.save_smoothing_preference)
        self.smooth_sel.currentTextChanged.connect(self.refresh_plots)
        
        smooth_layout.addWidget(self.smooth_sel)
        smooth_layout.addStretch()
        layout.addLayout(smooth_layout)

    def showEvent(self, event):
        self.load_smoothing_preference()
        self.refresh_plots()
        super().showEvent(event)

    def load_smoothing_preference(self):
        parent_win = self.window()
        if not hasattr(parent_win, 'load_settings'): return
        settings = parent_win.load_settings()
        pref_smooth = settings.get("user_preferences", {}).get("smoothing", "1/6 Octave")
        self.smooth_sel.blockSignals(True)
        self.smooth_sel.setCurrentText(pref_smooth)
        self.smooth_sel.blockSignals(False)

    def save_smoothing_preference(self, text):
        parent_win = self.window()
        if not hasattr(parent_win, 'load_settings'): return
        settings = parent_win.load_settings()
        if "user_preferences" not in settings: settings["user_preferences"] = {}
        settings["user_preferences"]["smoothing"] = text
        parent_win.save_settings(settings)

    def refresh_plots(self):
        if self.di_metrics: self.draw_metrics_curve("di", self.di_metrics)
        if self.preset_a_metrics: self.draw_metrics_curve("preset_a", self.preset_a_metrics)
        if self.preset_b_metrics: self.draw_metrics_curve("preset_b", self.preset_b_metrics)
        self.plot_widget.auto_scale()

    def draw_metrics_curve(self, mode, metrics):
        smooth_txt = self.smooth_sel.currentText()
        fraction = 0
        if "1/3" in smooth_txt: fraction = 3
        elif "1/6" in smooth_txt: fraction = 6
        elif "1/12" in smooth_txt: fraction = 12
        mag_db = 20 * np.log10(metrics["avg_spectrum"] + 1e-12)
        smoothed = apply_smoothing(metrics["freqs"], mag_db, fraction)
        if mode == "di": self.curve_di.setData(metrics["freqs"], smoothed)
        elif mode == "preset_a": self.curve_a.setData(metrics["freqs"], smoothed)
        else: self.curve_b.setData(metrics["freqs"], smoothed)

    def refresh_preset_list(self):
        self.list_presets.clear()
        # Primero migrar archivos antiguos si existen
        self.migrate_old_files()
        
        for f in self.presets_path.glob("*.mndDI"):
            item = QtWidgets.QListWidgetItem(self.list_presets)
            widget = PresetItemWidget(f.name, self)
            item.setSizeHint(widget.sizeHint())
            self.list_presets.addItem(item)
            self.list_presets.setItemWidget(item, widget)

    def migrate_old_files(self):
        """Migra archivos antiguos (.wav, .mondodi) al nuevo formato .mndDI"""
        parent_win = self.window()
        if not hasattr(parent_win, 'load_settings'): return
        settings = parent_win.load_settings()
        di_analysis = settings.get("di_analysis", {})
        
        # 1. Migrar .mondodi a .mndDI (solo renombrar)
        for mondo_file in self.presets_path.glob("*.mondodi"):
            new_file = mondo_file.with_suffix(".mndDI")
            if not new_file.exists():
                try: os.rename(mondo_file, new_file)
                except: pass
            else:
                try: os.remove(mondo_file)
                except: pass

        # 2. Migrar .wav a .mndDI (convertir)
        migrated = False
        for wav_file in self.presets_path.glob("*.wav"):
            safe_name = sanitize_filename(wav_file.stem)
            dest_file = self.presets_path / f"{safe_name}.mndDI"
            if dest_file.exists():
                try: os.remove(wav_file)
                except: pass
                continue
                
            try:
                data, fs = sf.read(str(wav_file))
                metrics = None
                if wav_file.name in di_analysis:
                    cached = di_analysis[wav_file.name]
                    metrics = {
                        "lufs": cached["lufs"], "max_peak_db": cached["max_peak_db"], "plr": cached["plr"],
                        "avg_spectrum": np.array(cached["avg_spectrum"]), "freqs": np.array(cached["freqs"])
                    }
                else:
                    metrics = self.comparator.calculate_metrics(data)
                
                if metrics:
                    self.comparator.save_guitar_di(str(dest_file), data, fs, metrics)
                    os.remove(wav_file)
                    migrated = True
            except Exception as e:
                print(f"Error migrando {wav_file.name}: {e}")
        
        if migrated:
            # Si migramos todo, podríamos limpiar di_analysis pero mejor lo dejamos 
            # para cuando estemos seguros de que todo funciona.
            # settings.pop("di_analysis", None) 
            # parent_win.save_settings(settings)
            pass



    def record_di(self):
        parent_win = self.window()
        settings = parent_win.load_settings() if hasattr(parent_win, 'load_settings') else {}
        if "connection" not in settings or "di_channel" not in settings["connection"] or settings["connection"]["di_channel"] is None:
            QtWidgets.QMessageBox.warning(self, "Audio", "Configura el dispositivo de audio y el 'Canal Entrada (DI Record)' primero.")
            return
            
        name, ok = QtWidgets.QInputDialog.getText(self, "Grabar DI", "Nombre del archivo:")
        if not ok or not name.strip(): return
        
        safe_name = sanitize_filename(name.strip())
        filename = f"{safe_name}.mndDI"
        dest_path = self.presets_path / filename
        
        if dest_path.exists():
            reply = QtWidgets.QMessageBox.question(self, "Archivo existente", 
                                                 f"El archivo '{filename}' ya existe. ¿Deseas sobrescribirlo?",
                                                 QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.No:
                return

        conn = settings["connection"]
        device_id = conn["device_id"]
        di_channel = conn["di_channel"] - 1 # 0-indexed
        
        if isinstance(device_id, (list, tuple)):
            in_id = device_id[0] if device_id[0] is not None else device_id[1]
        else:
            in_id = device_id
            
        try:
            dev_info_in = sd.query_devices(in_id)
            device_sr = int(dev_info_in['default_samplerate'])
            num_in = min(conn["di_channel"], dev_info_in['max_input_channels'])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo consultar el dispositivo: {e}")
            return

        self.capture_running = True
        self.capture_state = "waiting" # waiting -> countdown -> recording -> stopped
        self.recorded_di_data = []
        self.current_vol = 0
        self.countdown_start_time = 0
        self.signal_detected = False
        
        # Preparar gráficas para mostrar la entrada en tiempo real
        self.curve_a.setData([], [])
        self.curve_b.setData([], [])
        if self.diff_fill in self.plot_widget.items():
            self.plot_widget.removeItem(self.diff_fill)
        self.curve_di.setData([], [])
        
        fft_size = 4096
        self.fft_buffer = np.zeros(fft_size)
        self.fft_freqs = np.fft.rfftfreq(fft_size, 1 / device_sr)[1:]
        self.current_spectrum = None
        
        was_analyzing = False
        if hasattr(parent_win, 'conn_mgr') and parent_win.conn_mgr.stream is not None:
            parent_win.stop_audio()
            was_analyzing = True
        if hasattr(parent_win, 'set_btn_capturing'):
            parent_win.set_btn_capturing(conn)
            
        def record_callback(indata, frames, time_info, status):
            if indata.shape[1] > di_channel:
                channel_data = indata[:, di_channel]
                if self.capture_state == "recording":
                    self.recorded_di_data.append(channel_data.copy())
                # Calc volume
                rms = np.sqrt(np.mean(channel_data**2))
                db = 20 * np.log10(rms + 1e-12)
                self.current_vol = max(0, min(100, int((db + 60) * (100/60))))
                
                # Actualizar buffer para FFT
                L = len(channel_data)
                if L > 0:
                    if L >= fft_size:
                        self.fft_buffer = channel_data[-fft_size:]
                    else:
                        self.fft_buffer = np.roll(self.fft_buffer, -L)
                        self.fft_buffer[-L:] = channel_data
                    
                    window = np.hanning(fft_size)
                    mag = np.abs(np.fft.rfft(self.fft_buffer * window))[1:] + 1e-12
                    self.current_spectrum = 20 * np.log10(mag)
            else:
                if self.capture_state == "recording":
                    self.recorded_di_data.append(np.zeros((frames,)))

        def on_action_clicked():
            if self.capture_state == "waiting":
                self.capture_state = "countdown"
                self.countdown_start_time = time.time()
                self.btn_stop.setEnabled(False)
            elif self.capture_state == "recording":
                self.capture_state = "stopped"
                self.capture_running = False

        try: self.btn_stop.clicked.disconnect()
        except: pass
        self.btn_stop.clicked.connect(on_action_clicked)

        self.btn_stop.setText("INICIAR GRABACIÓN")
        self.btn_stop.setFixedSize(140, 28)
        self.btn_stop.setStyleSheet("background-color: #00ADB5; color: white; font-size: 10pt; font-weight: bold; border: none; padding: 5px;")
        self.btn_stop.setVisible(True)
        self.btn_cancel_record.setVisible(True)

        self.left_panel.setVisible(False)
        self.lbl_status.setText(f"Listo para grabar: {filename} (Toca la guitarra para probar el volumen)")
        self.progress.setVisible(True)
        self.progress.setMaximum(100)
        self.progress.setValue(0)

        try:
            with sd.InputStream(device=in_id, channels=num_in, samplerate=device_sr, callback=record_callback):
                while self.capture_running:
                    sd.sleep(50)
                    
                    if self.capture_state == "countdown":
                        elapsed = time.time() - self.countdown_start_time
                        remaining = 5 - int(elapsed)
                        if remaining <= 0:
                            self.capture_state = "recording"
                            self.btn_stop.setEnabled(True)
                            self.btn_stop.setText("DETENER")
                            self.btn_stop.setStyleSheet("background-color: #FF4B2B; color: white; font-size: 10pt; font-weight: bold; border: none; padding: 5px;")
                        else:
                            self.lbl_status.setText(f"Comenzando en {remaining} segundos... ¡Prepárate!")
                    
                    if self.capture_state == "recording":
                        if self.current_vol >= 5:
                            self.signal_detected = True
                            
                        if self.current_vol < 5 and not self.signal_detected:
                            self.lbl_status.setText(f"Grabando {filename}... <span style='color: #FF4B2B; font-weight: bold;'>¡SIN SEÑAL!</span>")
                        else:
                            self.lbl_status.setText(f"Grabando {filename}... (Recibiendo audio)")
                    
                    if self.capture_state in ["waiting", "recording", "countdown"]:
                        self.progress.setValue(self.current_vol)
                        if self.current_spectrum is not None:
                            smooth_txt = self.smooth_sel.currentText()
                            fraction = 6
                            if "1/3" in smooth_txt: fraction = 3
                            elif "1/6" in smooth_txt: fraction = 6
                            elif "1/12" in smooth_txt: fraction = 12
                            elif "None" in smooth_txt: fraction = 0
                            
                            smoothed = apply_smoothing(self.fft_freqs, self.current_spectrum, fraction)
                            self.curve_di.setData(self.fft_freqs, smoothed)
                            
                    QtWidgets.QApplication.processEvents()
                    
            if self.recorded_di_data:
                final_data = np.concatenate(self.recorded_di_data)
                
                # Verificar si se grabó silencio o señal muy baja
                max_val = np.max(np.abs(final_data))
                if max_val < 0.001: # Menos de -60dB
                    QtWidgets.QMessageBox.warning(self, "Señal no detectada", 
                        "La grabación parece estar en silencio o tiene un nivel extremadamente bajo.\n\n"
                        "Por favor, verifica:\n"
                        "1. Que el 'Canal Entrada (DI Record)' sea el correcto.\n"
                        "2. Que la Pedalboard esté enviando señal por ese canal.\n"
                        "3. Los niveles de entrada en tu interfaz.")
                
                # sf.write(str(dest_path), final_data, device_sr)
                # Ahora calculamos métricas y guardamos en el nuevo formato
                self.lbl_status.setText(f"Analizando y guardando {filename}...")
                QtWidgets.QApplication.processEvents()
                metrics = self.comparator.calculate_metrics(final_data)
                self.comparator.save_guitar_di(str(dest_path), final_data, device_sr, metrics)
                
                self.refresh_preset_list()
                QtWidgets.QMessageBox.information(self, "Grabación completada", f"Se guardó exitosamente: {filename}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error de Grabación", f"Fallo al grabar: {e}")
        finally:
            self.capture_running = False
            self.capture_state = "stopped"
            self.btn_stop.setEnabled(True)
            self.btn_stop.setVisible(False)
            self.btn_cancel_record.setVisible(False)
            self.left_panel.setVisible(True)
            self.lbl_status.setText("")
            self.progress.setVisible(False)
            
            try: self.btn_stop.clicked.disconnect()
            except: pass
            self.btn_stop.clicked.connect(self.stop_capture)
            self.btn_stop.setText("DETENER")
            self.btn_stop.setFixedSize(80, 24)
            self.btn_stop.setStyleSheet("background-color: #FF4B2B; color: white; font-size: 10pt; padding: 3px; font-weight: bold; border: none;")
            
            if was_analyzing and hasattr(parent_win, 'start_audio'):
                parent_win.start_audio(conn)
            elif hasattr(parent_win, 'set_btn_connected'):
                parent_win.set_btn_connected(conn)

    def delete_preset_file(self, filename):
        reply = QtWidgets.QMessageBox.question(self, "Eliminar", f"¿Eliminar '{filename}'?",
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            os.remove(self.presets_path / filename)
            self.refresh_preset_list()

    def show_library(self):
        self.left_panel.setVisible(True)
        self.btn_back_to_lib.setVisible(False)

    def stop_capture(self):
        self.capture_running = False

    def on_preset_selected(self, item):
        widget = self.list_presets.itemWidget(item)
        if not widget: return
        filename = widget.filename
        path = str(self.presets_path / filename)
        try:
            self.lbl_status.setText("Cargando archivo DI...")
            QtWidgets.QApplication.processEvents()
            
            data, fs, metrics = self.comparator.load_guitar_di(path)
            self.di_audio = data
            self.di_metrics = metrics
            
            # Asegurar que el comparator tenga el SR correcto del archivo cargado
            self.comparator.set_sample_rate(fs)
            
            self.lbl_di_info.setText(f"GUITAR DI FILE: {filename}")
            self.draw_metrics_curve("di", self.di_metrics)
            self.capture_process("preset_a")
            self.lbl_status.setText("")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo cargar: {e}")

    def capture_process(self, mode):
        if self.di_audio is None: return
        if mode == "preset_a":
            self.preset_a_metrics = None
            self.preset_b_metrics = None
            self.curve_a.setData([], [])
            self.curve_b.setData([], [])
            for card in [self.card_lufs, self.card_plr, self.card_peak]: card.set_values("---", "---", "")
        else:
            self.preset_b_metrics = None
            self.curve_b.setData([], [])
            self.card_lufs.set_values(f"{self.preset_a_metrics['lufs']:.1f}" if self.preset_a_metrics else "---", "---", "")
            self.card_plr.set_values(f"{self.preset_a_metrics['plr']:.1f}" if self.preset_a_metrics else "---", "---", "")
            self.card_peak.set_values(f"{self.preset_a_metrics['max_peak_db']:.1f}" if self.preset_a_metrics else "---", "---", "")
        if self.diff_fill in self.plot_widget.items(): self.plot_widget.removeItem(self.diff_fill)
        QtWidgets.QApplication.processEvents()
        try:
            parent_win = self.window()
            settings = parent_win.load_settings()
            if "connection" not in settings:
                QtWidgets.QMessageBox.warning(self, "Audio", "Configura el dispositivo de audio primero.")
                return
            was_analyzing = False
            if hasattr(parent_win, 'conn_mgr') and parent_win.conn_mgr.stream is not None:
                parent_win.stop_audio()
                was_analyzing = True
            parent_win.set_btn_capturing(settings.get("connection", {}))
            conn = settings["connection"]
            device_id = conn["device_id"]
            # Ruteo estándar:
            # - Enviar WAV al canal de SALIDA (Out) -> Entrada PedalBoard
            # - Leer respuesta del canal de ENTRADA (In) <- Salida PedalBoard
            send_ch, receive_ch = conn["out_channel"] - 1, conn["in_channel"] - 1
            if isinstance(device_id, (list, tuple)):
                in_id, out_id = device_id[0] or device_id[1], device_id[1] or device_id[0]
            else: in_id = out_id = device_id
            dev_info_in, dev_info_out = sd.query_devices(in_id), sd.query_devices(out_id)
            
            # OPTIMIZACIÓN: Solo abrir los canales necesarios
            num_in = min(conn["in_channel"], dev_info_in['max_input_channels'])
            num_out = min(conn["out_channel"], dev_info_out['max_output_channels'])
            
            # Ajustar la frecuencia de muestreo dinámicamente
            device_sr = int(dev_info_in['default_samplerate'])
            self.comparator.set_sample_rate(device_sr)

            play_data = self.di_audio
            if play_data.ndim == 1:
                tmp = np.zeros((len(play_data), num_out))
                if send_ch < num_out: tmp[:, send_ch] = play_data
                play_data = tmp
            self.recorded_data, self.current_frame = [], 0
            def callback(indata, outdata, frames, time, status):
                nonlocal play_data
                chunk = play_data[self.current_frame : self.current_frame + frames]
                outdata[:len(chunk)] = chunk
                if len(chunk) < frames: outdata[len(chunk):].fill(0)
                if indata.shape[1] > receive_ch: self.recorded_data.append(indata[:, receive_ch].copy())
                else: self.recorded_data.append(np.zeros((frames,)))
                self.current_frame += frames
                if self.current_frame >= len(play_data): raise sd.CallbackStop
            self.btn_capture_b.setEnabled(False)
            self.btn_stop.setVisible(True)
            self.left_panel.setVisible(False)
            self.btn_back_to_lib.setVisible(False)
            self.capture_running = True
            self.lbl_status.setText(f"Capturando {mode.upper()}... Reproduciendo DI")
            self.progress.setMaximum(len(play_data))
            self.progress.setValue(0); self.progress.setVisible(True)
            self.prog_timer = QtCore.QTimer()
            self.prog_timer.timeout.connect(lambda: self.progress.setValue(self.current_frame))
            self.prog_timer.start(100)
            
            try:
                with sd.Stream(device=device_id, channels=(num_in, num_out), samplerate=device_sr, callback=callback):
                    while self.current_frame < len(play_data) and self.capture_running:
                        sd.sleep(50)
                        QtWidgets.QApplication.processEvents()
                        pct = int((self.current_frame / len(play_data)) * 100)
                        self.lbl_status.setText(f"Capturando {mode.upper()}... {pct}%")
            except Exception as e_stream:
                QtWidgets.QMessageBox.warning(self, "Audio", f"Error con la frecuencia de muestreo ({device_sr}Hz). Reintentando sin especificar SR...")
                with sd.Stream(device=device_id, channels=(num_in, num_out), callback=callback):
                    while self.current_frame < len(play_data) and self.capture_running:
                        sd.sleep(50)
                        QtWidgets.QApplication.processEvents()
                        pct = int((self.current_frame / len(play_data)) * 100)
                        self.lbl_status.setText(f"Capturando {mode.upper()}... {pct}%")

            self.btn_stop.setVisible(False); self.btn_back_to_lib.setVisible(True)
            if not self.capture_running:
                self.lbl_status.setText("Captura cancelada."); self.progress.setVisible(False)
                self.btn_capture_b.setEnabled(True); return
            self.prog_timer.stop(); self.progress.setVisible(False)
            self.lbl_status.setText(f"Procesando {mode.upper()}...")
            QtWidgets.QApplication.processEvents()
            captured = np.concatenate(self.recorded_data)
            metrics = self.comparator.calculate_metrics(captured)
            if mode == "preset_a":
                self.preset_a_metrics = metrics
                self.draw_metrics_curve("preset_a", metrics)
                self.btn_capture_b.setVisible(True)
            else:
                self.preset_b_metrics = metrics
                self.draw_metrics_curve("preset_b", metrics)
            self.update_dashboard(); self.plot_widget.auto_scale()
            self.lbl_status.setText(f"Estado {mode.replace('_', ' ').upper()} actualizado.")
            self.btn_capture_b.setEnabled(True)
            if was_analyzing: parent_win.start_audio(settings["connection"])
            else: parent_win.set_btn_connected(settings["connection"])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Fallo: {e}")
            self.btn_capture_b.setEnabled(True)

    def update_dashboard(self):
        if not self.preset_a_metrics or not self.preset_b_metrics or not self.di_metrics:
            if self.preset_a_metrics and self.di_metrics:
                d_lufs, d_plr, d_peak = self.preset_a_metrics['lufs'] - self.di_metrics['lufs'], self.preset_a_metrics['plr'] - self.di_metrics['plr'], self.preset_a_metrics['max_peak_db'] - self.di_metrics['max_peak_db']
                self.card_lufs.set_values(f"{self.preset_a_metrics['lufs']:.1f}", "---", f"{d_lufs:+.1f} vs DI")
                self.card_plr.set_values(f"{self.preset_a_metrics['plr']:.1f}", "---", f"{d_plr:+.1f} vs DI")
                self.card_peak.set_values(f"{self.preset_a_metrics['max_peak_db']:.1f}", "---", f"{d_peak:+.1f} vs DI")
            return
        gain_a, plr_a, peak_a = self.preset_a_metrics['lufs'] - self.di_metrics['lufs'], self.preset_a_metrics['plr'] - self.di_metrics['plr'], self.preset_a_metrics['max_peak_db'] - self.di_metrics['max_peak_db']
        gain_b, plr_b, peak_b = self.preset_b_metrics['lufs'] - self.di_metrics['lufs'], self.preset_b_metrics['plr'] - self.di_metrics['plr'], self.preset_b_metrics['max_peak_db'] - self.di_metrics['max_peak_db']
        d_gain, d_plr, d_peak = gain_b - gain_a, plr_b - plr_a, peak_b - peak_a
        self.card_lufs.set_values(f"{self.preset_a_metrics['lufs']:.1f}", f"{self.preset_b_metrics['lufs']:.1f}", f"{d_gain:+.1f}")
        self.card_plr.set_values(f"{self.preset_a_metrics['plr']:.1f}", f"{self.preset_b_metrics['plr']:.1f}", f"{d_plr:+.1f}")
        self.card_peak.set_values(f"{self.preset_a_metrics['max_peak_db']:.1f}", f"{self.preset_b_metrics['max_peak_db']:.1f}", f"{d_peak:+.1f}")
        self.highlight_differences()

    def highlight_differences(self):
        if not self.preset_a_metrics or not self.preset_b_metrics: return
        if self.diff_fill in self.plot_widget.items(): self.plot_widget.removeItem(self.diff_fill)
        self.diff_fill = pg.FillBetweenItem(self.curve_a, self.curve_b, brush=pg.mkBrush(0, 173, 181, 40))
        self.plot_widget.addItem(self.diff_fill)

class MetricCard(QtWidgets.QFrame):
    def __init__(self, title, value, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(2)
        self.lbl_title = QtWidgets.QLabel(title); self.lbl_title.setObjectName("Title")
        val_layout = QtWidgets.QHBoxLayout(); val_layout.setSpacing(8)
        self.lbl_preset_a = QtWidgets.QLabel("---"); self.lbl_preset_a.setObjectName("RefValue")
        self.lbl_preset_a.setStyleSheet("color: #00ADB5; background: transparent;")
        self.lbl_sep = QtWidgets.QLabel("|"); self.lbl_sep.setStyleSheet("color: #333; background: transparent;")
        self.lbl_preset_b = QtWidgets.QLabel("---"); self.lbl_preset_b.setObjectName("TargetValue")
        self.lbl_preset_b.setStyleSheet("color: #FFAC41; background: transparent;")
        val_layout.addWidget(self.lbl_preset_a); val_layout.addWidget(self.lbl_sep); val_layout.addWidget(self.lbl_preset_b); val_layout.addStretch()
        self.lbl_delta = QtWidgets.QLabel(""); self.lbl_delta.setObjectName("Delta")
        layout.addWidget(self.lbl_title); layout.addLayout(val_layout); layout.addWidget(self.lbl_delta)
    def set_values(self, a_val, b_val, delta=None):
        self.lbl_preset_a.setText(a_val); self.lbl_preset_b.setText(b_val)
        if delta:
            self.lbl_delta.setText(f"Δ: {delta}")
            if "+" in delta: self.lbl_delta.setStyleSheet("color: #FF4B2B; background: transparent;")
            elif "-" in delta: self.lbl_delta.setStyleSheet("color: #00FFAB; background: transparent;")
            else: self.lbl_delta.setStyleSheet("color: #E0E0E0; background: transparent;")
        else: self.lbl_delta.setText("")

class PresetItemWidget(QtWidgets.QWidget):
    def __init__(self, filename, parent_module):
        super().__init__()
        self.filename, self.parent_module = filename, parent_module
        self.setStyleSheet("background: transparent;")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2); self.setMinimumHeight(35)
        self.side_bar = QtWidgets.QFrame(); self.side_bar.setFixedWidth(3)
        self.side_bar.setStyleSheet("background-color: transparent; border-radius: 1px;")
        display_name = filename.replace(".mndDI", "").replace(".mondodi", "")
        self.lbl_name = QtWidgets.QLabel(display_name)
        self.lbl_name.setStyleSheet("color: #E0E0E0; background: transparent; font-weight: 500; margin-left: 5px;")
        self.btn_delete = QtWidgets.QPushButton(qta.icon('fa5s.times', color='#444'), "")
        self.btn_delete.setFixedSize(24, 24); self.btn_delete.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_delete.setStyleSheet("background: transparent; border: none;")
        self.btn_delete.clicked.connect(lambda: self.parent_module.delete_preset_file(self.filename))
        layout.addWidget(self.side_bar); layout.addWidget(self.lbl_name); layout.addStretch(); layout.addWidget(self.btn_delete)
    def enterEvent(self, event):
        self.lbl_name.setStyleSheet("color: #00ADB5; background: transparent; font-weight: bold; margin-left: 5px;")
        self.side_bar.setStyleSheet("background-color: #00ADB5; border-radius: 1px;")
        self.btn_delete.setIcon(qta.icon('fa5s.times', color='#FF4B2B'))
        super().enterEvent(event)
    def leaveEvent(self, event):
        self.lbl_name.setStyleSheet("color: #E0E0E0; background: transparent; font-weight: 500; margin-left: 5px;")
        self.side_bar.setStyleSheet("background-color: transparent; border-radius: 1px;")
        self.btn_delete.setIcon(qta.icon('fa5s.times', color='#444'))
        super().leaveEvent(event)
