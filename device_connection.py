import os
import json
import sounddevice as sd
import time
from PySide6 import QtCore, QtWidgets, QtGui

class AudioDeviceDialog(QtWidgets.QDialog):
    """Diálogo para configurar el driver, dispositivo y canales de la Pedalboard."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Audio")
        self.setModal(True)
        self.resize(450, 250)
        
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        
        self.driver_combo = QtWidgets.QComboBox()
        self.device_combo = QtWidgets.QComboBox()
        self.in_combo = QtWidgets.QComboBox()
        self.out_combo = QtWidgets.QComboBox()
        self.di_in_combo = QtWidgets.QComboBox()
        
        form.addRow("Driver (Host API):", self.driver_combo)
        form.addRow("Dispositivo:", self.device_combo)
        form.addRow("Canal Salida (PedalBoard In):", self.out_combo)
        form.addRow("Canal Entrada (PedalBoard Out):", self.in_combo)
        form.addRow("Canal Entrada (DI Record):", self.di_in_combo)
        layout.addLayout(form)
        
        # Informativo
        self.info_lbl = QtWidgets.QLabel("Selecciona los canales correspondientes al loopback.")
        self.info_lbl.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(self.info_lbl)
        
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.btn_disconnect = btn_box.addButton("Desconectar", QtWidgets.QDialogButtonBox.DestructiveRole)
        self.btn_disconnect.clicked.connect(self.handle_disconnect)
        
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        
        self.requested_disconnect = False
        self.driver_combo.currentIndexChanged.connect(self.populate_devices)
        self.device_combo.currentIndexChanged.connect(self.populate_channels)
        
        self.populate_drivers()

    def handle_disconnect(self):
        self.requested_disconnect = True
        self.accept()

    def populate_drivers(self):
        self.driver_combo.blockSignals(True)
        self.driver_combo.clear()
        try:
            apis = sd.query_hostapis()
            for i, api in enumerate(apis):
                if len(api['devices']) > 0:
                    self.driver_combo.addItem(api['name'], i)
            idx = self.driver_combo.findText("ASIO")
            if idx >= 0: self.driver_combo.setCurrentIndex(idx)
        except Exception as e: print(f"Error al obtener drivers: {e}")
        self.driver_combo.blockSignals(False)
        self.populate_devices()

    def populate_devices(self, index=None):
        def get_base_name(name):
            words = name.replace("(", "").replace(")", "").split()
            return " ".join(words[:2]).title() if words else name

        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        api_index = self.driver_combo.currentData()
        if api_index is None:
            self.device_combo.blockSignals(False)
            return

        try:
            devices = sd.query_devices()
            api_info = sd.query_hostapis(api_index)
            api_devices = api_info['devices']
            
            in_only, out_only = [], []
            for i in api_devices:
                dev = devices[i]
                ins, outs = dev['max_input_channels'], dev['max_output_channels']
                if ins > 0 and outs > 0: 
                    self.device_combo.addItem(get_base_name(dev['name']), (i, i))
                elif ins > 0: in_only.append((i, dev))
                elif outs > 0: out_only.append((i, dev))
            
            grouped_in = {get_base_name(dev['name']): i for i, dev in in_only}
            grouped_out = {get_base_name(dev['name']): i for i, dev in out_only}
            
            for bname in set(list(grouped_in.keys()) + list(grouped_out.keys())):
                in_id, out_id = grouped_in.get(bname), grouped_out.get(bname)
                if in_id is not None and out_id is not None:
                    self.device_combo.addItem(bname, (in_id, out_id))
                elif in_id is not None:
                    self.device_combo.addItem(f"{bname} (Sólo Entrada)", (in_id, None))
                elif out_id is not None:
                    self.device_combo.addItem(f"{bname} (Sólo Salida)", (None, out_id))
        except Exception as e: print(f"Error al enumerar dispositivos: {e}")
        self.device_combo.blockSignals(False)
        self.populate_channels()

    def populate_channels(self, index=None):
        device_data = self.device_combo.currentData()
        if not device_data:
            self.out_combo.clear(); self.in_combo.clear()
            return
            
        in_id, out_id = device_data
        try:
            curr_in, curr_out, curr_di = self.in_combo.currentData(), self.out_combo.currentData(), self.di_in_combo.currentData()
            self.in_combo.clear(); self.out_combo.clear(); self.di_in_combo.clear()
            
            if in_id is not None:
                in_info = sd.query_devices(in_id)
                for i in range(1, in_info['max_input_channels'] + 1):
                    self.in_combo.addItem(f"Channel {i}", i)
                    self.di_in_combo.addItem(f"Channel {i}", i)

            if out_id is not None:
                out_info = sd.query_devices(out_id)
                for i in range(1, out_info['max_output_channels'] + 1):
                    self.out_combo.addItem(f"Channel {i}", i)
                    
            if curr_in:
                idx = self.in_combo.findData(curr_in)
                if idx >= 0: self.in_combo.setCurrentIndex(idx)
            if curr_out:
                idx = self.out_combo.findData(curr_out)
                if idx >= 0: self.out_combo.setCurrentIndex(idx)
            if curr_di:
                idx = self.di_in_combo.findData(curr_di)
                if idx >= 0: self.di_in_combo.setCurrentIndex(idx)
                
        except Exception as e: print(f"Error al obtener canales: {e}")

    def restore_settings(self, conn):
        try:
            driver_idx = self.driver_combo.findText(conn.get("driver_name", ""))
            if driver_idx >= 0:
                self.driver_combo.setCurrentIndex(driver_idx)
                dev_idx = self.device_combo.findText(conn.get("device_name", ""))
                if dev_idx >= 0:
                    self.device_combo.setCurrentIndex(dev_idx)
                    in_idx = self.in_combo.findData(conn.get("in_channel"))
                    out_idx = self.out_combo.findData(conn.get("out_channel"))
                    di_idx = self.di_in_combo.findData(conn.get("di_channel"))
                    if in_idx >= 0: self.in_combo.setCurrentIndex(in_idx)
                    if out_idx >= 0: self.out_combo.setCurrentIndex(out_idx)
                    if di_idx >= 0: self.di_in_combo.setCurrentIndex(di_idx)
                    return True
        except: pass
        return False

    def get_settings(self):
        device_data = self.device_combo.currentData()
        return {
            "driver_name": self.driver_combo.currentText(),
            "device_name": self.device_combo.currentText(),
            "in_channel": self.in_combo.currentData(),
            "out_channel": self.out_combo.currentData(),
            "di_channel": self.di_in_combo.currentData(),
            "device_id": device_data # (in_id, out_id)
        }

class ConnectionManager:
    """Gestiona el ciclo de vida del stream de audio."""
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.stream = None
        self.settings_file = "settings.json"

    def start_audio(self, settings):
        self.stop_audio()
        try:
            in_id, out_id = settings["device_id"]
            send_ch = settings["out_channel"] - 1
            receive_ch = settings["in_channel"] - 1
            
            # Configurar el analyzer
            self.analyzer.in_ch = receive_ch
            self.analyzer.out_ch = send_ch
            self.analyzer.meas_mag_avg.fill(0)

            # Obtener el número REAL de canales soportados para no pedir de más
            # Si in_id o out_id son None, usamos el ID del otro lado (duplex)
            actual_in_id = in_id if in_id is not None else out_id
            actual_out_id = out_id if out_id is not None else in_id
            
            in_info = sd.query_devices(actual_in_id)
            out_info = sd.query_devices(actual_out_id)
            
            needed_in = max(2, settings["in_channel"])
            needed_out = max(2, settings["out_channel"])
            
            num_in = min(needed_in, in_info['max_input_channels'])
            num_out = min(needed_out, out_info['max_output_channels'])

            # Usar la frecuencia de muestreo por defecto del dispositivo
            device_sr = int(in_info['default_samplerate'])
            self.analyzer.set_sample_rate(device_sr)

            # Pequeña pausa para permitir que el driver libere recursos
            time.sleep(0.1)

            try:
                self.stream = sd.Stream(
                    device=(actual_in_id, actual_out_id),
                    channels=(num_in, num_out),
                    samplerate=device_sr,
                    blocksize=4096,
                    callback=self.analyzer.audio_callback
                )
                self.stream.start()
            except Exception as e_inner:
                # Fallback: intentar sin especificar blocksize (usa el del driver)
                print(f"Reintentando sin blocksize fijo por error: {e_inner}")
                self.stream = sd.Stream(
                    device=(actual_in_id, actual_out_id),
                    channels=(num_in, num_out),
                    samplerate=device_sr,
                    callback=self.analyzer.audio_callback
                )
                self.stream.start()

            return True, "Conectado"
        except Exception as e:
            return False, str(e)

    def stop_audio(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except: pass
            self.stream = None

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as f:
                return json.load(f)
        return {}

    def save_settings(self, settings):
        with open(self.settings_file, "w") as f:
            json.dump(settings, f, indent=4)
