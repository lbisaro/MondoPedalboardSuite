import os
import json
import time
import pickle
import sqlite3
import numpy as np
from pathlib import Path
from PySide6 import QtCore, QtWidgets, QtGui
import qtawesome as qta
import utils.modules

DB_PATH = "user_data/MondoPBSuite.db"

class CheckableListWidget(QtWidgets.QListWidget):
    def __init__(self, ignore_custom=False):
        super().__init__()
        self.ignore_custom = ignore_custom
        self.itemClicked.connect(self.on_item_clicked)
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.custom_has_value = False
        self.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 2px;
            }
        """)

    def on_item_clicked(self, item):
        state = QtCore.Qt.CheckState.Checked if item.checkState() == QtCore.Qt.CheckState.Unchecked else QtCore.Qt.CheckState.Unchecked
        item.setCheckState(state)

    def on_item_double_clicked(self, item):
        if self.count() == 0: return
        
        target_state = QtCore.Qt.CheckState.Checked if self.item(0).checkState() == QtCore.Qt.CheckState.Unchecked else QtCore.Qt.CheckState.Unchecked
        
        for i in range(self.count()):
            list_item = self.item(i)
            if self.ignore_custom and list_item.text() == "Custom":
                if not self.custom_has_value and target_state == QtCore.Qt.CheckState.Checked:
                    continue
            list_item.setCheckState(target_state)
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, '_desired_columns', None):
            cols = self._desired_columns
            width = event.size().width() - self.verticalScrollBar().width() - 10
            item_width = max(50, int(width / cols))
            self.setGridSize(QtCore.QSize(item_width, 24))

class HelixCabsWidget(QtWidgets.QWidget):
    def __init__(self, analyzer, main_window):
        super().__init__()
        self.analyzer = analyzer
        self.main_window = main_window
        self.helix_conn = main_window.conn_mgr.helix_conn
        
        # Estado del Batch
        self.is_analyzing = False
        self.is_aborting = False
        self.combinations_to_analyze = []
        self.current_comb_index = 0
        self.batch_connection = None
        self.cab_slot_idx = None
        self.cab_slot_bus = 0x01
        
        self.total_mics_db = 12 # Default
        
        self.init_ui()
        self.load_db_data()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QtWidgets.QHBoxLayout()
        self.lbl_title = QtWidgets.QLabel("Batch Analysis Filter")
        self.lbl_title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #FFAC41;")
        header.addWidget(self.lbl_title)
        header.addStretch()
        layout.addLayout(header)
        
        # Estilo para los QGroupBox
        group_style = """
            QGroupBox {
                font-size: 11pt;
                font-weight: bold;
                color: #00ADB5;
                border: 1px solid #333;
                border-radius: 6px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: #FFAC41;
            }
        """
        
        # Main Lists Layout (Horizontal)
        lists_layout = QtWidgets.QHBoxLayout()
        
        # LEFT SIDE: Cabs
        cabs_group = QtWidgets.QGroupBox("Cabs")
        cabs_group.setStyleSheet(group_style)
        cabs_layout = QtWidgets.QVBoxLayout(cabs_group)
        cabs_layout.setContentsMargins(10, 15, 10, 10)
        self.list_cabs = CheckableListWidget()
        self.list_cabs.setViewMode(QtWidgets.QListView.ViewMode.ListMode)
        self.list_cabs.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        self.list_cabs.setWrapping(True)
        self.list_cabs.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.list_cabs._desired_columns = 4  # Custom property for resizeEvent
        cabs_layout.addWidget(self.list_cabs)
        lists_layout.addWidget(cabs_group, stretch=3)
        
        # RIGHT SIDE: Vertical layout containing (Mics) and (Pos + Dist)
        right_layout = QtWidgets.QVBoxLayout()
        
        # TOP RIGHT: Mics
        mics_group = QtWidgets.QGroupBox("Mics")
        mics_group.setStyleSheet(group_style)
        mics_layout = QtWidgets.QVBoxLayout(mics_group)
        mics_layout.setContentsMargins(10, 15, 10, 10)
        self.list_mics = CheckableListWidget()
        self.list_mics.setViewMode(QtWidgets.QListView.ViewMode.ListMode)
        self.list_mics.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        self.list_mics.setWrapping(True)
        self.list_mics.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.list_mics._desired_columns = 2
        mics_layout.addWidget(self.list_mics)
        right_layout.addWidget(mics_group, stretch=1)
        
        # BOTTOM RIGHT: Pos and Dist
        bottom_right_layout = QtWidgets.QHBoxLayout()
        
        # Positions
        pos_group = QtWidgets.QGroupBox("Position")
        pos_group.setStyleSheet(group_style)
        pos_layout = QtWidgets.QVBoxLayout(pos_group)
        pos_layout.setContentsMargins(10, 15, 10, 10)
        self.list_pos = CheckableListWidget()
        for p in ["Center", "Cap Edge", "Mid-Cone"]:
            item = QtWidgets.QListWidgetItem(p)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.list_pos.addItem(item)
        pos_layout.addWidget(self.list_pos)
        bottom_right_layout.addWidget(pos_group)
        
        # Distances
        dist_group = QtWidgets.QGroupBox("Distance")
        dist_group.setStyleSheet(group_style)
        dist_layout = QtWidgets.QVBoxLayout(dist_group)
        dist_layout.setContentsMargins(10, 15, 10, 10)
        self.list_dist = CheckableListWidget(ignore_custom=True)
        for d in ["1.0", "3.5", "8.0", "Custom"]:
            item = QtWidgets.QListWidgetItem(d)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.list_dist.addItem(item)
        dist_layout.addWidget(self.list_dist)
        
        self.spin_custom_dist = QtWidgets.QDoubleSpinBox()
        self.spin_custom_dist.setRange(1.0, 12.0)
        self.spin_custom_dist.setSingleStep(0.1)
        self.spin_custom_dist.setPrefix("Custom: ")
        self.spin_custom_dist.setSuffix(" in")
        self.spin_custom_dist.setValue(1.0)
        self.spin_custom_dist.valueChanged.connect(self.on_custom_dist_changed)
        dist_layout.addWidget(self.spin_custom_dist)
        
        bottom_right_layout.addWidget(dist_group)
        
        right_layout.addLayout(bottom_right_layout, stretch=1)
        lists_layout.addLayout(right_layout, stretch=2)
        
        layout.addLayout(lists_layout, stretch=1)
        
        # Controles superiores
        controls_layout = QtWidgets.QHBoxLayout()
        self.btn_analyze = QtWidgets.QPushButton(qta.icon('fa5s.play', color='white'), " Iniciar Análisis")
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
        
        controls_layout.addWidget(self.btn_analyze)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Log Box
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120) 
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #A9B7C6;
                font-family: Consolas, monospace;
                font-size: 9pt;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.log_text)
        
        self.log("HELIX CABS Batch Analysis inicializado. Listo para configurar combinaciones.")

    def log(self, message):
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_custom_dist_changed(self, value):
        self.list_dist.custom_has_value = True

    def load_db_data(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            c.execute('SELECT id, hex_id, name, cap_edge_position FROM cabs ORDER BY id')
            for row in c.fetchall():
                item = QtWidgets.QListWidgetItem(f"{row[2]}")
                item.setData(QtCore.Qt.ItemDataRole.UserRole, {
                    "cab_id": row[0],
                    "hex_id": row[1],
                    "name": row[2],
                    "cap_edge": row[3] if row[3] is not None else 3.0
                })
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                self.list_cabs.addItem(item)
                
            c.execute('SELECT id, model FROM cabs_mics ORDER BY id')
            mics = c.fetchall()
            self.total_mics_db = len(mics)
            for row in mics:
                item = QtWidgets.QListWidgetItem(f"{row[1]}")
                item.setData(QtCore.Qt.ItemDataRole.UserRole, row[0])
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                self.list_mics.addItem(item)
                
            conn.close()
        except Exception as e:
            print(f"Error loading DB data: {e}")

    def generate_combinations(self):
        sel_cabs = []
        for i in range(self.list_cabs.count()):
            if self.list_cabs.item(i).checkState() == QtCore.Qt.CheckState.Checked:
                sel_cabs.append(self.list_cabs.item(i).data(QtCore.Qt.ItemDataRole.UserRole))
                
        sel_mics = []
        for i in range(self.list_mics.count()):
            if self.list_mics.item(i).checkState() == QtCore.Qt.CheckState.Checked:
                sel_mics.append(self.list_mics.item(i).data(QtCore.Qt.ItemDataRole.UserRole))
                
        sel_pos_types = []
        for i in range(self.list_pos.count()):
            if self.list_pos.item(i).checkState() == QtCore.Qt.CheckState.Checked:
                sel_pos_types.append(self.list_pos.item(i).text())
                
        sel_dists = []
        for i in range(self.list_dist.count()):
            if self.list_dist.item(i).checkState() == QtCore.Qt.CheckState.Checked:
                txt = self.list_dist.item(i).text()
                if txt == "Custom":
                    sel_dists.append(self.spin_custom_dist.value())
                else:
                    sel_dists.append(float(txt))
                    
        self.combinations_to_analyze = []
        for cab in sel_cabs:
            for mic_id in sel_mics:
                for pos_type in sel_pos_types:
                    if pos_type == "Center":
                        pos_val = 0.0
                    elif pos_type == "Cap Edge":
                        pos_val = cab["cap_edge"]
                    elif pos_type == "Mid-Cone":
                        pos_val = cab["cap_edge"] + ((10.0 - cab["cap_edge"]) / 2.0)
                        
                    for dist_val in sel_dists:
                        self.combinations_to_analyze.append({
                            "cab_id": cab["cab_id"],
                            "hex_id": cab["hex_id"],
                            "cab_name": cab["name"],
                            "mic_id": mic_id,
                            "pos_val": round(pos_val, 1),
                            "dist_val": round(dist_val, 1)
                        })

    def start_analysis(self):
        if self.is_analyzing:
            self.is_aborting = True
            self.log("Cancelando el análisis...")
            self.btn_analyze.setText(" Cancelando...")
            self.btn_analyze.setEnabled(False)
            return
            
        self.generate_combinations()
        if not self.combinations_to_analyze:
            self._abort("No se seleccionaron combinaciones.")
            return

        self.log_text.clear()
        self.log(f"Iniciando lote de {len(self.combinations_to_analyze)} combinaciones...")

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
        self.current_comb_index = 0
        
        self.log("Conectando y leyendo bloques de Helix...")
        
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
        
        self._analyze_next_combination()

    def _analyze_next_combination(self):
        if self.is_aborting:
            self._abort("Análisis cancelado por el usuario.")
            return
            
        if self.current_comb_index >= len(self.combinations_to_analyze):
            self._abort(f"¡Análisis completado! ({len(self.combinations_to_analyze)} combinaciones).")
            return
            
        comb = self.combinations_to_analyze[self.current_comb_index]
        cab_id = comb["cab_id"]
        mic_id = comb["mic_id"]
        pos_val = comb["pos_val"]
        dist_val = comb["dist_val"]
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT response_data FROM cabs_frequency_response 
            WHERE cab_id=? AND mic_id=? AND position=? AND distance=?
        ''', (cab_id, mic_id, pos_val, dist_val))
        row = c.fetchone()
        conn.close()
        
        if row and row[0]:
            msg = f"[{self.current_comb_index+1}/{len(self.combinations_to_analyze)}] OMITIDO (Caché DB): {comb['cab_name']} | Mic: {mic_id} | Pos: {pos_val} | Dist: {dist_val}"
            self.log(msg)
                
            self.current_comb_index += 1
            QtCore.QTimer.singleShot(10, self._analyze_next_combination)
            return

        msg = f"[{self.current_comb_index+1}/{len(self.combinations_to_analyze)}] ANALIZANDO: {comb['cab_name']} | Mic: {mic_id} | Pos: {pos_val} | Dist: {dist_val}"
        self.log(msg)
        
        ok, msg_err = self.batch_connection.write_block_model(self.cab_slot_idx, comb["hex_id"], self.cab_slot_bus)
        if not ok:
            self._abort(f"Error al cambiar de modelo: {msg_err}")
            return
            
        QtCore.QTimer.singleShot(500, self._inject_custom_params)
            
    def _inject_custom_params(self):
        if self.is_aborting:
            self._abort("Análisis cancelado por el usuario.")
            return

        comb = self.combinations_to_analyze[self.current_comb_index]
        
        mic_norm = comb["mic_id"] / max(1, self.total_mics_db - 1)
        pos_norm = comb["pos_val"] / 10.0
        dist_norm = max(0.0, min(1.0, (comb["dist_val"] - 1.0) / 11.0))
        
        targets = [
            {"raw": comb["mic_id"], "norm": mic_norm, "is_int": True},
            {"raw": comb["pos_val"], "norm": pos_norm, "is_int": False},
            {"raw": comb["dist_val"], "norm": dist_norm, "is_int": False},
            {"raw": 0.0, "norm": 0.0, "is_int": False},
            {"raw": 0.0, "norm": 0.0, "is_int": False},
            {"raw": 20100.0, "norm": 1.0, "is_int": False},
            {"raw": 0.0, "norm": 0.0, "is_int": False}
        ]
        
        for idx, target in enumerate(targets):
            self.batch_connection.write_block_parameter(
                self.cab_slot_idx, idx, target_db=target["raw"], norm_val=target["norm"], is_int=target["is_int"]
            )
            time.sleep(0.1)
            
        QtCore.QTimer.singleShot(200, self._start_sweep)
        
    def _start_sweep(self):
        if self.is_aborting:
            self._abort("Análisis cancelado por el usuario.")
            return
            
        self.analyzer.mode = "Exponential Sine Sweep"
        self.analyzer.analyzer_active = True
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
        
        comb = self.combinations_to_analyze[self.current_comb_index]
        
        try:
            data = pickle.dumps((freqs, db_mag))
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            c.execute('''
                INSERT OR REPLACE INTO cabs_frequency_response 
                (cab_id, mic_id, position, distance, response_data)
                VALUES (?, ?, ?, ?, ?)
            ''', (comb['cab_id'], comb['mic_id'], comb['pos_val'], comb['dist_val'], data))
            
            conn.commit()
            conn.close()
            self.log(f"  -> Guardado exitoso en DB.")
        except Exception as e:
            self.log(f"  -> Error guardando en DB: {e}")
        
        self.current_comb_index += 1
        QtCore.QTimer.singleShot(500, self._analyze_next_combination)

    def _abort(self, message):
        self.is_analyzing = False
        self.is_aborting = False
        self.btn_analyze.setText(" Iniciar Análisis")
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
        self.log(f"STATUS: {message}")
        self.analyzer.analyzer_active = False
        
        if self.batch_connection:
            try:
                self.batch_connection.disconnect()
            except:
                pass
            self.batch_connection = None
