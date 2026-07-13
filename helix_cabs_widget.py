import os
import json
import time
import numpy as np
from pathlib import Path
from PySide6 import QtCore, QtWidgets, QtGui
import qtawesome as qta
from ui_utils import FrequencyPlotWidget
import utils.modules

class HelixCabsWidget(QtWidgets.QWidget):
    def __init__(self, analyzer, main_window):
        super().__init__()
        self.analyzer = analyzer
        self.main_window = main_window
        self.helix_conn = main_window.conn_mgr.helix_conn
        
        self.json_path = Path("user_data/cab_frequency_responses.json")
        self.custom_json_path = Path("user_data/cab_frequency_responses_57_dynamic.json")
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Estado del Batch
        self.is_analyzing = False
        self.is_aborting = False
        self.cabs_to_analyze = []
        self.current_cab_index = 0
        self.batch_connection = None
        self.cab_slot_idx = None
        self.cab_slot_bus = 0x01
        
        self.current_cab_id = None
        self.current_cab_name = None
        self.current_cab_category = "Cab"
        
        utils.modules._load_db()
        self._load_cabs_list()
        
        self.init_ui()

    def _load_cabs_list(self):
        parent_dir = Path(__file__).parent
        with open(parent_dir / "utils" / "modules.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        usb_mapping = data.get("usb_mapping", {})
        
        self.cabs_to_analyze = []
        for model_id, model_data in utils.modules._models_db.items():
            if model_data.get('category') == 'Cab' and model_id != 'cab_custom_ir':
                real_hex_id = None
                variant_val = None
                for hid, mapping in usb_mapping.items():
                    if mapping.get("model_id") == model_id:
                        real_hex_id = hid
                        variant_val = mapping.get("variant")
                        break
                
                if real_hex_id:
                    self.cabs_to_analyze.append({
                        "model_id": model_id,
                        "name": model_data.get("name"),
                        "hex_id": real_hex_id,
                        "variant": variant_val
                    })

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QtWidgets.QHBoxLayout()
        self.lbl_title = QtWidgets.QLabel("HELIX CABS  |  Batch Analysis")
        self.lbl_title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #FFAC41;")
        
        header.addWidget(self.lbl_title)
        header.addStretch()
        layout.addLayout(header)
        
        # Controles superiores
        controls_layout = QtWidgets.QHBoxLayout()
        
        self.btn_analyze = QtWidgets.QPushButton(qta.icon('fa5s.play', color='white'), " Analizar todos los Cabs")
        self.btn_analyze.setMinimumHeight(40)
        self.btn_analyze.setStyleSheet("""
            QPushButton {
                background-color: #00ADB5;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #00939A; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_analyze.clicked.connect(self.start_analysis)
        
        self.chk_custom_params = QtWidgets.QCheckBox("Usar Parámetros Fijos (Mic 57, Normal Cabs)")
        self.chk_custom_params.setStyleSheet("color: white;")
        self.chk_custom_params.setChecked(False)
        
        self.lbl_status = QtWidgets.QLabel(f"Listo. {len(self.cabs_to_analyze)} Cabs disponibles.")
        self.lbl_status.setStyleSheet("color: #888; font-size: 10pt;")
        
        controls_layout.addWidget(self.btn_analyze)
        controls_layout.addWidget(self.chk_custom_params)
        controls_layout.addWidget(self.lbl_status)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Gráfico
        self.plot_widget = FrequencyPlotWidget(y_range=(-40, 20))
        layout.addWidget(self.plot_widget)
        
        self.curves = []
        self.colors = [
            '#00ADB5', '#FFAC41', '#FF4B2B', '#2ECC71', '#9B59B6',
            '#F1C40F', '#E74C3C', '#3498DB', '#1ABC9C', '#E67E22'
        ]

    def start_analysis(self):
        if self.is_analyzing:
            self.is_aborting = True
            self.lbl_status.setText("Cancelando el análisis por lotes...")
            self.btn_analyze.setText(" Cancelando...")
            self.btn_analyze.setEnabled(False)
            return
            
        if not self.cabs_to_analyze:
            self._abort("No se encontraron Cabs en la base de datos.")
            return

        # Limpiar curvas anteriores
        for curve in self.curves:
            self.plot_widget.removeItem(curve)
        self.curves = []

        self.btn_analyze.setText(" Cancelar Análisis")
        self.btn_analyze.setIcon(qta.icon('fa5s.stop', color='white'))
        self.btn_analyze.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #C0392B; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.is_analyzing = True
        self.is_aborting = False
        self.lbl_status.setText("Conectando y leyendo bloques de Helix...")
        
        from helix_connection import HelixConnection
        self.batch_connection = HelixConnection()
        conn_success, conn_msg = self.batch_connection.connect()
        if not conn_success:
            self._abort(f"Error de conexión: {conn_msg}")
            return
            
        self.batch_connection.perform_handshake()
        
        success, blocks_or_msg = self.batch_connection.fetch_active_preset_blocks()
        if not success:
            self._abort(f"Error al leer bloques: {blocks_or_msg}")
            return
            
        cab_block = next((b for b in blocks_or_msg if b.get('category') in ['Cab', 'Impulse Response', 'IR']), None)
        if not cab_block:
            self._abort("No se encontró ningún bloque Cab o IR en el preset actual de la Helix.")
            return
            
        self.cab_slot_idx = cab_block.get('slot_idx')
        self.cab_slot_bus = 0x01
        
        self.current_cab_index = 0
        self._analyze_next_cab()

    def _analyze_next_cab(self):
        if self.is_aborting:
            self._abort("Análisis cancelado por el usuario.")
            return
            
        if self.current_cab_index >= len(self.cabs_to_analyze):
            self._abort(f"¡Análisis completado con éxito! ({len(self.cabs_to_analyze)} Cabs grabados).")
            return
            
        cab_info = self.cabs_to_analyze[self.current_cab_index]
        
        # Skip legacy cabs if custom params are checked
        if self.chk_custom_params.isChecked() and cab_info.get("variant") == "Legacy":
            self.current_cab_index += 1
            self._analyze_next_cab()
            return
        self.current_cab_id = cab_info["model_id"]
        self.current_cab_name = cab_info["name"]
        
        self.lbl_status.setText(f"({self.current_cab_index+1}/{len(self.cabs_to_analyze)}) Cambiando a: {self.current_cab_name}...")
        
        ok, msg = self.batch_connection.write_block_model(self.cab_slot_idx, cab_info["hex_id"], self.cab_slot_bus)
        if not ok:
            self._abort(f"Error al cambiar de modelo: {msg}")
            return
            
        if self.chk_custom_params.isChecked():
            self.lbl_status.setText(f"({self.current_cab_index+1}/{len(self.cabs_to_analyze)}) Esperando estabilización del Cab...")
            # Esperar usando QTimer para no bloquear la interfaz (mili segundos)
            QtCore.QTimer.singleShot(1000, self._inject_custom_params)
        else:
            QtCore.QTimer.singleShot(1000, self._start_sweep)
            
    def _inject_custom_params(self):
        if self.is_aborting:
            self._abort("Análisis cancelado por el usuario.")
            return

        self.lbl_status.setText(f"({self.current_cab_index+1}/{len(self.cabs_to_analyze)}) Forzando Mic 57 Dynamic y demás parámetros...")
        QtWidgets.QApplication.processEvents()
        
        # Targets for Normal Cab
        targets = [
            {"raw": 0.0, "norm": 0.0},
            {"raw": 0.24, "norm": 0.024},
            {"raw": 1.0, "norm": 0.0},
            {"raw": 0.0, "norm": 0.0},
            {"raw": 70.0, "norm": 0.14},
            {"raw": 11000.0, "norm": 0.535714},
            {"raw": 0.0, "norm": 0.0}
        ]
        for idx, target in enumerate(targets):
            is_int = (idx == 0)
            ok, msg = self.batch_connection.write_block_parameter(
                self.cab_slot_idx, idx, target_db=target["raw"], norm_val=target["norm"], is_int=is_int
            )
            # Pausa completa entre parámetros (segundo)
            time.sleep(0.25)
            
        self.lbl_status.setText(f"({self.current_cab_index+1}/{len(self.cabs_to_analyze)}) Parámetros inyectados. Esperando DSP...")
        QtCore.QTimer.singleShot(500, self._start_sweep)
        
    def _start_sweep(self):
        if self.is_aborting:
            self._abort("Análisis cancelado por el usuario.")
            return
            
        self.lbl_status.setText(f"({self.current_cab_index+1}/{len(self.cabs_to_analyze)}) Analizando: {self.current_cab_name}...")
        
        self.analyzer.mode = "Exponential Sine Sweep"
        self.analyzer.analyzer_active = True
        
        # 2.5 segundos de barrido
        QtCore.QTimer.singleShot(2500, self._finish_sweep_and_save)

    def _finish_sweep_and_save(self):
        if self.is_aborting:
            self._abort("Análisis cancelado por el usuario.")
            return
            
        self.analyzer.analyzer_active = False
        
        if not self.analyzer.result_ready:
            self._abort("Fallo al capturar el audio. Verifique dispositivo y volumen.")
            return
            
        freqs = self.analyzer.freqs.copy()
        db_mag = self.analyzer.calibrated_mag.copy()
        
        # Elegir un color de nuestra paleta según el índice
        color = self.colors[self.current_cab_index % len(self.colors)]
        
        # Crear y añadir una nueva curva para el Cab actual
        new_curve = self.plot_widget.add_curve(self.current_cab_name, color=color)
        new_curve.setData(freqs, db_mag)
        self.curves.append(new_curve)
        
        # --- NUEVO: Leer parámetros del bloque actual ---
        self.lbl_status.setText(f"({self.current_cab_index+1}/{len(self.cabs_to_analyze)}) Procesando curva de: {self.current_cab_name}...")
        
        params_dict = {}
        raw_params = []
        
        # TEMPORALMENTE DESHABILITADO: 
        # La lectura masiva del preset completo (5KB) en cada ciclo agota el número de sesiones
        # disponibles en el buffer USB de la Helix (por eso crashea en el 4to Cab).
        # Además, como modules.json está desactualizado (faltan Position y Angle), 
        # la decodificación sería errónea de todos modos.
        # Solo guardaremos la respuesta de frecuencia.
        
        # success, blocks_or_msg = self.batch_connection.fetch_active_preset_blocks()
        # if success:
        #     cab_block = next((b for b in blocks_or_msg if b.get('slot_idx') == self.cab_slot_idx), None)
        #     if cab_block and 'params_a' in cab_block:
        #         norm_vals = cab_block['params_a']
        #         raw_params = [round(float(v), 4) for v in norm_vals]
        #         print(f"[CABS] Parámetros extraídos para {self.current_cab_name}: RAW: {raw_params}")
        
        current_cab_info = self.cabs_to_analyze[self.current_cab_index]
        current_hex_id = current_cab_info["hex_id"]
        current_variant = current_cab_info.get("variant")
        self._save_to_json(freqs, db_mag, params_dict, raw_params, current_hex_id, current_variant)
        
        self.current_cab_index += 1
        
        # Dar respiro al USB y DSP antes de bombardear con el siguiente comando
        QtCore.QTimer.singleShot(1000, self._analyze_next_cab)

    def _save_to_json(self, freqs, db_mag, params_dict, raw_params, hex_id, variant):
        data = {}
        target_path = self.custom_json_path if self.chk_custom_params.isChecked() else self.json_path
        if target_path.exists():
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Error cargando JSON previo: {e}")
                
        # Asegurarse de que raw_params sea una lista vacía si no hay valores
        if raw_params is None:
            raw_params = []
                
        cab_entry = {
            "name": self.current_cab_name,
            "hex_id": hex_id,
            "variant": variant,
            "category": self.current_cab_category,
            "parameters": params_dict,
            "raw_parameters": raw_params,
            "frequencies": [round(float(f), 1) for f in freqs],
            "db_response": [round(float(d), 1) for d in db_mag]
        }
        
        data[self.current_cab_id] = cab_entry
        
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Guardado exitoso para {self.current_cab_name} en {target_path.name}")
        except Exception as e:
            print(f"Error guardando JSON: {e}")

    def _abort(self, message):
        self.is_analyzing = False
        self.is_aborting = False
        self.btn_analyze.setText(" Analizar todos los Cabs")
        self.btn_analyze.setIcon(qta.icon('fa5s.play', color='white'))
        self.btn_analyze.setStyleSheet("""
            QPushButton {
                background-color: #00ADB5;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #00939A; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_analyze.setEnabled(True)
        self.lbl_status.setText(message)
        self.analyzer.analyzer_active = False
        
        if self.batch_connection:
            try:
                self.batch_connection.disconnect()
            except:
                pass
            self.batch_connection = None

