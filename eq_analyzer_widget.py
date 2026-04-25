import os
import numpy as np
import sounddevice as sd
from PySide6 import QtCore, QtWidgets, QtGui
import qtawesome as qta
from pathlib import Path
from ui_utils import FrequencyPlotWidget, apply_smoothing, sanitize_filename
from audio_comparator import AudioComparator

# --- CONFIGURACIÓN DE AUDIO Y DSP ---
SAMPLE_RATE = 48000
BLOCK_SIZE = 4096
CHANNELS = 2
SMOOTHING_FRACTION = 6

class AudioAnalyzer:
    """Motor de procesamiento de audio en tiempo real."""
    def __init__(self):
        self.fs = SAMPLE_RATE
        self.block_size = BLOCK_SIZE
        self.out_ch = 2 
        self.in_ch = 0  
        
        self.freqs = np.fft.rfftfreq(self.block_size, 1 / self.fs)[1:]
        
        # Ruido Periódico Perfecto
        N = self.block_size
        phases = np.random.uniform(0, 2*np.pi, N//2 + 1)
        mags = np.ones(N//2 + 1)
        mags[0] = 0 
        
        X = mags * np.exp(1j * phases)
        test_signal = np.fft.irfft(X, n=N)
        self.test_signal = (0.05 * (test_signal / np.max(np.abs(test_signal)))).astype(np.float32)
        self.ref_mag = np.abs(np.fft.rfft(self.test_signal))[1:] + 1e-12
        
        self.magnitude_db = np.zeros(len(self.freqs))
        self.meas_mag_avg = np.zeros(len(self.freqs))
        self.alpha = 0.5 
        self.analyzer_active = False # Desactivado por defecto

        # Buffers para manejar tamaños de bloque variables (ASIO)
        self.in_buffer = np.zeros(self.block_size, dtype=np.float32)
        self.out_ptr = 0

    def set_sample_rate(self, fs):
        if self.fs != fs:
            self.fs = fs
            self.freqs = np.fft.rfftfreq(self.block_size, 1 / self.fs)[1:]
            self.magnitude_db = np.zeros(len(self.freqs))
            self.meas_mag_avg = np.zeros(len(self.freqs))

    def audio_callback(self, indata, outdata, frames, time, status):
        outdata.fill(0)
        
        # Generar salida (ruido) usando un puntero circular
        if self.analyzer_active and outdata.shape[1] > self.out_ch:
            for i in range(frames):
                outdata[i, self.out_ch] = self.test_signal[self.out_ptr]
                self.out_ptr = (self.out_ptr + 1) % self.block_size
            
        # Procesar entrada usando un buffer circular
        if indata.shape[1] > self.in_ch:
            meas_data = indata[:, self.in_ch]
            # Desplazar buffer e insertar nuevos datos
            self.in_buffer = np.roll(self.in_buffer, -frames)
            self.in_buffer[-frames:] = meas_data
            
            # Realizar FFT sobre el bloque completo
            meas_mag = np.abs(np.fft.rfft(self.in_buffer))[1:] + 1e-12
            
            if np.all(self.meas_mag_avg == 0):
                self.meas_mag_avg = meas_mag
            else:
                self.meas_mag_avg = self.alpha * meas_mag + (1 - self.alpha) * self.meas_mag_avg
            
            # Asegurar que el tamaño coincida (por si acaso)
            if len(self.meas_mag_avg) == len(self.ref_mag):
                transfer_mag = self.meas_mag_avg / self.ref_mag
                self.magnitude_db = 20 * np.log10(transfer_mag)
            
    def get_smoothed_curve(self, fraction=SMOOTHING_FRACTION):
        return apply_smoothing(self.freqs, self.magnitude_db, fraction)

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
        
        self.plot_widget = FrequencyPlotWidget()
        self.curve = self.plot_widget.add_curve("Muestreo", color='#00ADB5')
        # Ya no usaremos self.ref_curve fija, sino dinámicas
        right_layout.addWidget(self.plot_widget)
        
        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Smoothing:"))
        self.smooth_sel = QtWidgets.QComboBox()
        self.smooth_sel.addItems(["None", "1/3 Octave", "1/6 Octave", "1/12 Octave"])
        
        # Cargar preferencia del usuario
        settings = self.main_window.load_settings()
        pref_smooth = settings.get("user_preferences", {}).get("smoothing", "1/6 Octave")
        self.smooth_sel.setCurrentText(pref_smooth)
        self.smooth_sel.currentTextChanged.connect(self.save_smoothing_preference)
        
        controls.addWidget(self.smooth_sel)
        controls.addStretch()
        right_layout.addLayout(controls)
        
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(30)

    def showEvent(self, event):
        """Activar el ruido y recargar preferencias cuando el widget se muestra."""
        self.load_smoothing_preference()
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

    def update_plot(self):
        smooth_txt = self.smooth_sel.currentText()
        fraction = 0
        if "1/3" in smooth_txt: fraction = 3
        elif "1/6" in smooth_txt: fraction = 6
        elif "1/12" in smooth_txt: fraction = 12
        
        smoothed = self.analyzer.get_smoothed_curve(fraction)
        if smoothed is not None:
            self.curve.setData(self.analyzer.freqs, smoothed)
            
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
