import sys
import numpy as np
import sounddevice as sd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

# --- CONFIGURACIÓN DE AUDIO Y DSP ---
SAMPLE_RATE = 48000
BLOCK_SIZE = 4096       # Tamaño del buffer (menor latencia = más pequeño, pero requiere más CPU)
CHANNELS = 2            # Canal 1: Referencia, Canal 2: Medición
SMOOTHING_FRACTION = 6  # 1/6 de octava para el suavizado (valores comunes: 3, 6, 12)

class AudioAnalyzer:
    def __init__(self):
        self.fs = SAMPLE_RATE
        self.block_size = BLOCK_SIZE
        
        # Buffers circulares o directos para la FFT
        self.ref_data = np.zeros(self.block_size)
        self.meas_data = np.zeros(self.block_size)
        
        # Eje de frecuencias (descartando la componente DC y llegando hasta Nyquist)
        self.freqs = np.fft.rfftfreq(self.block_size, 1 / self.fs)[1:]
        
        # Ventana para reducir leakage espectral
        self.window = np.hanning(self.block_size)
        
        # Array donde guardaremos el cálculo en dB
        self.magnitude_db = np.zeros(len(self.freqs))
        self.smoothed_db = np.zeros(len(self.freqs))

    def audio_callback(self, indata, frames, time, status):
        """Callback invocado por sounddevice. Debe ser rápido y no bloquear."""
        if status:
            print(f"Status: {status}", file=sys.stderr)
            
        # Asumimos indata[:, 0] = Referencia, indata[:, 1] = Helix/Amp
        self.ref_data = indata[:, 0]
        self.meas_data = indata[:, 1]
        
        self.compute_transfer_function()

    def compute_transfer_function(self):
        """Calcula la función de transferencia H(f) = Meas(f) / Ref(f)"""
        # 1. Aplicar ventana
        ref_windowed = self.ref_data * self.window
        meas_windowed = self.meas_data * self.window
        
        # 2. Calcular FFT real
        # rfft devuelve n/2 + 1 elementos. Descartamos el bin 0 (frecuencia 0)
        ref_fft = np.fft.rfft(ref_windowed)[1:]
        meas_fft = np.fft.rfft(meas_windowed)[1:]
        
        # 3. Calcular Magnitud (con protección para división por cero)
        epsilon = 1e-12
        ref_mag = np.abs(ref_fft) + epsilon
        meas_mag = np.abs(meas_fft) + epsilon
        
        # Función de transferencia (magnitud)
        transfer_mag = meas_mag / ref_mag
        
        # Convertir a dB
        self.magnitude_db = 20 * np.log10(transfer_mag)
        
        # 4. Aplicar Smoothing
        self.smoothed_db = self.fractional_octave_smoothing(self.magnitude_db, self.freqs, fraction=SMOOTHING_FRACTION)

    def fractional_octave_smoothing(self, data_db, freqs, fraction=6):
        """
        Aplica un suavizado de 1/N de octava.
        Para cada frecuencia f, promedia la energía en la banda [f * 2^(-1/2N), f * 2^(1/2N)].
        """
        smoothed = np.zeros_like(data_db)
        
        # El ancho de banda en octavas es 1/fraction. El multiplicador es 2^(1 / (2 * fraction))
        mult = 2 ** (1.0 / (2.0 * fraction))
        
        # Convertimos dB a potencia lineal para promediar correctamente
        data_linear = 10 ** (data_db / 20.0) 
        
        for i, f in enumerate(freqs):
            f_lower = f / mult
            f_upper = f * mult
            
            # Encontrar los índices en el array de frecuencias que caen en este rango
            # (En un código hiper optimizado en C esto se precalcula, pero en NumPy con boolean masks es razonablemente rápido)
            idx = np.where((freqs >= f_lower) & (freqs <= f_upper))[0]
            
            if len(idx) > 0:
                # Promediamos linealmente y volvemos a dB
                mean_linear = np.mean(data_linear[idx])
                smoothed[i] = 20 * np.log10(mean_linear)
            else:
                smoothed[i] = data_db[i]
                
        return smoothed

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, analyzer):
        super().__init__()
        self.analyzer = analyzer
        self.stream = None
        self.setWindowTitle("Mondo EQ Analyzer - Real-Time Match EQ")
        self.resize(1000, 600)
        
        # --- Layout Principal ---
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        
        # --- Panel de Control Superior ---
        control_layout = QtWidgets.QHBoxLayout()
        
        self.input_combo = QtWidgets.QComboBox()
        self.output_combo = QtWidgets.QComboBox()
        self.start_btn = QtWidgets.QPushButton("Conectar Audio")
        self.start_btn.clicked.connect(self.toggle_audio)
        
        control_layout.addWidget(QtWidgets.QLabel("Input (Helix):"))
        control_layout.addWidget(self.input_combo)
        control_layout.addWidget(QtWidgets.QLabel("Output (Futuro):"))
        control_layout.addWidget(self.output_combo)
        control_layout.addWidget(self.start_btn)
        control_layout.addStretch()
        
        main_layout.addLayout(control_layout)
        
        # --- Setup PyQtGraph ---
        self.graph_widget = pg.PlotWidget()
        main_layout.addWidget(self.graph_widget)
        self.graph_widget.setBackground('k')
        self.graph_widget.setTitle("Respuesta en Frecuencia (Helix vs Ref)", color="w", size="14pt")
        self.graph_widget.setLabel("left", "Magnitud (dB)", color="white", size="12pt")
        self.graph_widget.setLabel("bottom", "Frecuencia (Hz)", color="white", size="12pt")
        self.graph_widget.showGrid(x=True, y=True, alpha=0.3)
        self.graph_widget.setLogMode(x=True, y=False) # Eje X logarítmico (20Hz - 20kHz)
        self.graph_widget.setYRange(-30, 30, padding=0)
        self.graph_widget.setXRange(np.log10(20), np.log10(20000), padding=0)
        
        # Curvas
        self.raw_curve = self.graph_widget.plot(pen=pg.mkPen(color=(100, 100, 100, 150), width=1), name="Raw")
        self.smoothed_curve = self.graph_widget.plot(pen=pg.mkPen(color=(0, 255, 255), width=2), name="Smoothed")
        
        # Llenar listas de dispositivos de audio
        self.populate_devices()

        # Timer para actualizar GUI independientemente del audio
        self.timer = QtCore.QTimer()
        self.timer.setInterval(30) # ~33 FPS
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def populate_devices(self):
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        
        for i, dev in enumerate(devices):
            api_name = hostapis[dev['hostapi']]['name']
            name = f"{dev['name']} ({api_name})"
            if dev['max_input_channels'] > 0:
                self.input_combo.addItem(name, i)
            if dev['max_output_channels'] > 0:
                self.output_combo.addItem(name, i)

        # Seleccionar el dispositivo por defecto del sistema
        default_in = sd.default.device[0]
        default_out = sd.default.device[1]
        
        if default_in >= 0:
            idx = self.input_combo.findData(default_in)
            if idx >= 0: self.input_combo.setCurrentIndex(idx)
            
        if default_out >= 0:
            idx = self.output_combo.findData(default_out)
            if idx >= 0: self.output_combo.setCurrentIndex(idx)

    def toggle_audio(self):
        if self.stream is not None and self.stream.active:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self.start_btn.setText("Conectar Audio")
            self.input_combo.setEnabled(True)
            self.output_combo.setEnabled(True)
        else:
            in_device = self.input_combo.currentData()
            # out_device = self.output_combo.currentData() # Se usará cuando agreguemos salida
            
            try:
                # Actualmente solo iniciamos InputStream porque la app solo analiza.
                # Para usar la salida a futuro se cambia a sd.Stream()
                self.stream = sd.InputStream(
                    device=in_device,
                    channels=CHANNELS, 
                    samplerate=SAMPLE_RATE, 
                    blocksize=BLOCK_SIZE,
                    callback=self.analyzer.audio_callback
                )
                self.stream.start()
                self.start_btn.setText("Desconectar")
                self.input_combo.setEnabled(False)
                self.output_combo.setEnabled(False)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error de Audio", f"No se pudo iniciar el audio:\n{str(e)}")

    def update_plot(self):
        # Actualizar curvas (se le pasa np.log10(freqs) si setLogMode(x=False) pero 
        # setLogMode(x=True) en PyQtGraph asume que le pasas valores lineales en X
        # y él mismo los grafica logarítmicamente.
        self.raw_curve.setData(self.analyzer.freqs, self.analyzer.magnitude_db)
        self.smoothed_curve.setData(self.analyzer.freqs, self.analyzer.smoothed_db)

def main():
    app = QtWidgets.QApplication(sys.argv)
    
    analyzer = AudioAnalyzer()
    
    window = MainWindow(analyzer)
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
