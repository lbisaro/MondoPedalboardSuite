import sys
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtSvgWidgets import QSvgWidget
import qtawesome as qta
import json
import os

from helix_connection import HelixConnection
from utils.modules import get_module, save_module

# Icon mapping for different block categories (SVG paths and Colors)
CATEGORY_COLORS = {
    "Distortion": ('assets/icons_category/Distortion.svg', '#F57C00'), 
    "Dynamics": ('assets/icons_category/Dynamics.svg', '#FDD835'), 
    "EQ": ('assets/icons_category/EQ.svg', '#FDD835'), 
    "Modulation": ('assets/icons_category/Modulation.svg', '#29B6F6'), 
    "Delay": ('assets/icons_category/Delay.svg', '#8BC34A'), 
    "Reverb": ('assets/icons_category/Reverb.svg', '#FF7043'), 
    "Pitch/Synth": ('assets/icons_category/PitchSynth.svg', '#AB47BC'), 
    "Filter": ('assets/icons_category/Filter.svg', '#AB47BC'), 
    "Wah": ('assets/icons_category/Wah.svg', '#AB47BC'), 
    "Amp": ('assets/icons_category/Amp.svg', '#E53935'), 
    "Preamp": ('assets/icons_category/Preamp.svg', '#E53935'), 
    "Cab": ('assets/icons_category/Cab.svg', '#E53935'), 
    "IR": ('assets/icons_category/IR.svg', '#EC407A'), 
    "Volume/Pan": ('assets/icons_category/VolumePan.svg', '#26A69A'), 
    "Send/Return": ('assets/icons_category/SendReturn.svg', '#00ACC1'), 
    "Looper": ('assets/icons_category/Looper.svg', '#FFFFFF'), 
    "I/O": ('assets/icons_io/multi.svg', '#9E9E9E'), 
    "Unknown": ('assets/icons_io/none.svg', '#9E9E9E') 
}

def get_icon_for_category(category):
    cat = category if category else "Unknown"
    if cat not in CATEGORY_COLORS:
        for k, v in CATEGORY_COLORS.items():
            if k.lower() in cat.lower():
                return v
        return CATEGORY_COLORS["Unknown"]
    return CATEGORY_COLORS[cat]


class ParameterBar(QtWidgets.QWidget):
    def __init__(self, name, value, color, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.name = name
        self.value = value
        self.color = color
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw text name
        painter.setPen(QtGui.QColor(self.color))
        painter.setFont(QtGui.QFont("Arial", 8, QtGui.QFont.Bold))
        painter.drawText(10, 15, self.name)
        
        val_str = str(self.value).lower()
        if val_str in ["true", "false"]:
            is_true = (val_str == "true")
            # Draw switch
            switch_w = 30
            switch_h = 14
            switch_x = 10
            switch_y = 18
            
            # background
            painter.setPen(QtCore.Qt.NoPen)
            bg_color = QtGui.QColor(self.color) if is_true else QtGui.QColor("#444")
            painter.setBrush(bg_color)
            painter.drawRoundedRect(switch_x, switch_y, switch_w, switch_h, switch_h//2, switch_h//2)
            
            # thumb
            thumb_color = QtGui.QColor("#fff") if is_true else QtGui.QColor("#aaa")
            painter.setBrush(thumb_color)
            thumb_x = switch_x + (switch_w - switch_h) + 1 if is_true else switch_x + 1
            painter.drawEllipse(thumb_x, switch_y + 1, switch_h - 2, switch_h - 2)
            
            return
        
        # Draw background track
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#333"))
        track_y = 20
        track_h = 6
        track_w = self.width() - 60
        painter.drawRect(10, track_y, track_w, track_h)
        
        # Calculate width
        val = 0.0
        try:
            val = float(self.value)
        except ValueError:
            pass
            
        # Assuming typical max is 10.0 for display purposes
        percentage = min(max(val / 10.0, 0.0), 1.0)
        
        # Draw filled track
        painter.setBrush(QtGui.QColor(self.color))
        fill_w = int(track_w * percentage)
        painter.drawRect(10, track_y, fill_w, track_h)
        
        # Draw value text
        painter.setPen(QtGui.QColor("#ccc"))
        painter.drawText(track_w + 20, 15, str(self.value))

class BlockEditorDialog(QtWidgets.QDialog):
    def __init__(self, block_data, parent=None):
        super().__init__(parent)
        self.block_data = block_data
        self.hex_id = block_data.get('hex_id')
        self.full_module = get_module(self.hex_id) if self.hex_id else None
        
        self.catalog = {}
        try:
            with open("utils/helix_catalog.json", encoding="utf-8") as f:
                data = json.load(f)
                self.catalog = data.get("catalog", {})
        except Exception as e:
            print("Error loading catalog:", e)
            
        self.setWindowTitle("Editar Módulo")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        self.setStyleSheet("background-color: #1a1a1a; color: white;")
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        top_layout = QtWidgets.QHBoxLayout()
        form_layout = QtWidgets.QFormLayout()
        
        self.lbl_hex = QtWidgets.QLabel()
        self.lbl_hex.setStyleSheet("font-weight: bold; font-size: 14px;")
        form_layout.addRow("ID Hex:", self.lbl_hex)
        
        self.cmb_category = QtWidgets.QComboBox()
        self.cmb_category.addItems(list(CATEGORY_COLORS.keys()))
        self.cmb_category.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
        self.cmb_category.currentTextChanged.connect(self.on_category_changed)
        form_layout.addRow("Categoría:", self.cmb_category)
        
        self.cmb_name = QtWidgets.QComboBox()
        self.cmb_name.setEditable(True)
        self.cmb_name.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
        
        completer = self.cmb_name.completer()
        if completer:
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            completer.setFilterMode(QtCore.Qt.MatchContains)
            
        self.cmb_name.currentTextChanged.connect(self.on_name_changed)
        form_layout.addRow("Nombre:", self.cmb_name)
        
        top_layout.addLayout(form_layout)
        
        self.lbl_image = QtWidgets.QLabel()
        self.lbl_image.setFixedSize(100, 100)
        self.lbl_image.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_image.setStyleSheet("background-color: transparent;")
        top_layout.addWidget(self.lbl_image)
        
        layout.addLayout(top_layout)
        
        # Parámetros (solo lectura)
        lbl_params = QtWidgets.QLabel("Parámetros:")
        layout.addWidget(lbl_params)
        
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        container = QtWidgets.QWidget()
        self.params_layout = QtWidgets.QVBoxLayout(container)
        self.params_layout.setSpacing(5)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Guardar")
        self.btn_save.setStyleSheet("background-color: #E53935; color: white; font-weight: bold; padding: 5px;")
        self.btn_save.clicked.connect(self.save_data)
        
        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet("background-color: #555; color: white; padding: 5px;")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)

    def on_category_changed(self, category):
        self.cmb_name.clear()
        models = self._get_models_for_category(category)
        names = sorted([m.get("name", "") for m in models if m.get("name")])
        self.cmb_name.addItems(names)
        
    def _get_models_for_category(self, category):
        models = self.catalog.get(category, [])
        if not models:
            for k, v in self.catalog.items():
                if k.lower() in category.lower() or category.lower() in k.lower():
                    return v
        return models

    def on_name_changed(self, name):
        cat = self.cmb_category.currentText()
        models = self._get_models_for_category(cat)
        model_data = next((m for m in models if m.get("name") == name), None)
        
        # Clear layout
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
                
        if model_data:
            img_path = model_data.get("image")
            if img_path and os.path.exists(img_path):
                pixmap = QtGui.QPixmap(img_path).scaled(100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.lbl_image.setPixmap(pixmap)
            else:
                self.lbl_image.clear()
                self.lbl_image.setText("Sin Icono")
                
            _, color = get_icon_for_category(cat)
            catalog_params = model_data.get("parameters", [])
            real_params = self.block_data.get("params_a", [])
            
            # Match parameters by index
            for i in range(max(len(catalog_params), len(real_params))):
                if i < len(catalog_params):
                    p_name = catalog_params[i].get("name", f"Prm. {i}")
                else:
                    p_name = f"Prm. {i}"
                    
                if i < len(real_params):
                    val = real_params[i]
                else:
                    val = 0.0
                    
                if isinstance(val, float):
                    val = val * 10.0
                    
                val_str = f"{val:.1f}" if isinstance(val, float) else str(val)
                bar = ParameterBar(p_name, val_str, color, self)
                self.params_layout.addWidget(bar)
                
            self.params_layout.addStretch()
        else:
            self.lbl_image.clear()
            self.lbl_image.setText("N/A")

    def load_data(self):
        self.lbl_hex.setText(self.hex_id or "Desconocido")
        
        if self.full_module:
            cat = self.full_module.get("category", "Unknown")
            idx = self.cmb_category.findText(cat)
            if idx >= 0:
                self.cmb_category.setCurrentIndex(idx)
            
            name = self.full_module.get("name", "")
            self.cmb_name.setCurrentText(name)
            
            is_verified = self.full_module.get("verified", False)
            if is_verified:
                self.lbl_hex.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 14px;")
            else:
                self.lbl_hex.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 14px;")
        else:
            cat = self.block_data.get("category", "Unknown")
            idx = self.cmb_category.findText(cat)
            if idx >= 0:
                self.cmb_category.setCurrentIndex(idx)
                
            name = self.block_data.get("name", "")
            self.cmb_name.setCurrentText(name)
            
            self.lbl_hex.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 14px;")
            
        self.on_name_changed(self.cmb_name.currentText())

    def save_data(self):
        if not self.hex_id:
            QtWidgets.QMessageBox.warning(self, "Error", "No se puede guardar un módulo sin ID hexadecimal.")
            return
            
        new_data = {
            "name": self.cmb_name.currentText().strip(),
            "category": self.cmb_category.currentText(),
            "variant": None,
            "verified": True
        }
        
        success = save_module(self.hex_id, new_data)
        if success:
            QtWidgets.QMessageBox.information(self, "Éxito", "Módulo actualizado correctamente en modules.json")
            self.accept()
        else:
            QtWidgets.QMessageBox.critical(self, "Error", "Hubo un error al guardar los datos.")


ABBREVIATIONS = {
    "Distortion": "Dist", "Dynamics": "Dyn", "EQ": "EQ", "Modulation": "Mod",
    "Delay": "Delay", "Reverb": "Verb", "Pitch/Synth": "Pitch", "Filter": "Filt",
    "Wah": "Wah", "Amp": "Amp", "Preamp": "Pre", "Cab": "Cab", "IR": "IR",
    "Volume/Pan": "Vol", "Send/Return": "Snd/Rtn", "Looper": "Loop", "I/O": "I/O", "Unknown": "?"
}

class BlockCard(QtWidgets.QFrame):
    clicked_sig = QtCore.Signal(dict)
    
    def __init__(self, block_data, parent=None):
        super().__init__(parent)
        self.block_data = block_data
        
        self.setFixedSize(70, 70)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        
        name = block_data.get("name", "")
        slot_idx = block_data.get("slot_idx", -1)
        
        is_io = False
        icon_path, color = get_icon_for_category(block_data.get("category", "Unknown"))
        
        if "input" in name.lower() or str(slot_idx).endswith('0'):
            icon_path = 'assets/icons_io/input.svg'
            is_io = True
        elif "output" in name.lower() or str(slot_idx).endswith('9'):
            icon_path = 'assets/icons_io/output.svg'
            is_io = True
            
        if is_io:
            self.setObjectName("BlockCardIO")
            self.setStyleSheet("""
                QFrame#BlockCardIO {
                    background-color: transparent;
                    border: 1px solid #555;
                    border-radius: 35px;
                }
                QFrame#BlockCardIO:hover {
                    border: 1px solid #fff;
                }
            """)
        else:
            self.setObjectName("BlockCard")
            self.setStyleSheet("""
                QFrame#BlockCard {
                    background-color: transparent;
                    border: 1px solid #555;
                    border-radius: 8px;
                }
                QFrame#BlockCard:hover {
                    border: 1px solid #fff;
                }
            """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.svg_widget = QSvgWidget(icon_path)
        self.svg_widget.setFixedSize(40, 40)
        
        layout.addWidget(self.svg_widget, alignment=QtCore.Qt.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked_sig.emit(self.block_data)
        super().mousePressEvent(event)


class EmptyBlockCard(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(70, 70)
        self.setObjectName("EmptyBlock")
        self.setStyleSheet("""
            QFrame#EmptyBlock {
                background-color: transparent;
                border: none;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(5, 5, 5, 5)
        
        svg_widget = QSvgWidget('assets/icons_category/none.svg')
        svg_widget.setFixedSize(40, 40)
        layout.addWidget(svg_widget, alignment=QtCore.Qt.AlignCenter)

class ConnectorCard(QtWidgets.QFrame):
    def __init__(self, has_split_merge=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(25, 70)
        self.has_split_merge = has_split_merge
        
    def paintEvent(self, event):
        if not self.has_split_merge:
            return
            
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw circle if split/merge
        painter.setPen(QtGui.QPen(QtGui.QColor("#888"), 1))
        painter.setBrush(QtCore.Qt.transparent)
        radius = 6
        cx = self.width() // 2
        cy = self.height() // 2
        painter.drawEllipse(QtCore.QPoint(cx, cy), radius, radius)


class IOCard(QtWidgets.QFrame):
    def __init__(self, icon_path, parent=None):
        super().__init__(parent)
        self.setFixedSize(70, 70)
        self.setStyleSheet("background: transparent; border: none;")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        svg_widget = QSvgWidget(icon_path)
        svg_widget.setFixedSize(50, 50)
        layout.addWidget(svg_widget, alignment=QtCore.Qt.AlignCenter)


class BlockManagerWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Preset Info Header
        info_layout = QtWidgets.QVBoxLayout()
        self.lbl_preset_name = QtWidgets.QLabel("")
        self.lbl_preset_name.setStyleSheet("font-size: 24pt; font-weight: normal; color: white;")
        
        self.lbl_preset_details = QtWidgets.QLabel("")
        self.lbl_preset_details.setStyleSheet("font-size: 12pt; color: #aaa;")
        
        info_layout.addWidget(self.lbl_preset_name)
        info_layout.addWidget(self.lbl_preset_details)
        
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        self.btn_sync = QtWidgets.QPushButton(qta.icon('fa5s.sync'), " Sincronizar con Helix")
        self.btn_sync.setObjectName("AccentButton")
        self.btn_sync.setFixedHeight(35)
        self.btn_sync.clicked.connect(self.sync_blocks)
        
        header_layout.addWidget(self.btn_sync)
        
        main_layout.addLayout(header_layout)
        
        # Paths
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        container = QtWidgets.QWidget()
        self.paths_layout = QtWidgets.QVBoxLayout(container)
        self.paths_layout.setSpacing(20)
        
        self.path_layouts = {}
        self.path_groups = []
        for path_name in ["1A", "1B", "2A", "2B"]:
            group = QtWidgets.QGroupBox(f" PATH {path_name} ")
            group.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #444;
                    border-radius: 5px;
                    margin-top: 10px;
                    font-weight: bold;
                    color: #888;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 3px 0 3px;
                }
            """)
            h_layout = QtWidgets.QHBoxLayout(group)
            h_layout.setAlignment(QtCore.Qt.AlignLeft)
            self.path_layouts[path_name] = h_layout
            self.paths_layout.addWidget(group, 0, QtCore.Qt.AlignLeft)
            self.path_groups.append(group)
            
        self.lbl_loading = QtWidgets.QLabel("Sincronizando información desde la pedalera...")
        self.lbl_loading.setStyleSheet("font-size: 16px; color: #888;")
        self.lbl_loading.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_loading.setVisible(False)
        self.paths_layout.addWidget(self.lbl_loading)
            
        self.paths_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # Draw empty slots initially
        self.render_blocks([])
        
        # Auto-sync when module is opened
        QtCore.QTimer.singleShot(100, self.sync_blocks)

    def sync_blocks(self):
        print("Sincronizando bloques...")
        
        for group in self.path_groups:
            group.setVisible(False)
        self.lbl_loading.setVisible(True)
        QtWidgets.QApplication.processEvents()
        
        main_window = self.window()
        
        if hasattr(main_window, 'set_usb_interacting'):
            main_window.set_usb_interacting()
            QtWidgets.QApplication.processEvents()
            
        try:
            conn = HelixConnection()
            conn_ok, conn_msg = conn.connect()
            if not conn_ok:
                QtWidgets.QMessageBox.warning(self, "Error", f"No se detectó la Helix por USB o fallo de conexión: {conn_msg}")
                if hasattr(main_window, 'set_usb_disconnected'):
                    main_window.set_usb_disconnected()
                return
                
            conn.perform_handshake()
            
            # Fetch info
            info = conn.fetch_active_preset_info()
            if info:
                bank_name = info.get("bank_name", "??")
                preset_name = info.get("preset_name", "Unknown Preset")
                setlist = info.get("setlist_name", "Unknown Setlist")
                self.lbl_preset_name.setText(f"{bank_name} <b>{preset_name}</b>")
                self.lbl_preset_details.setText(setlist)
            
            success, data = conn.fetch_active_preset_blocks()
            
            # Darle un respiro a la pedalera antes de cerrar de golpe 
            # (imita el comportamiento del time.sleep() en test_helix.py)
            import time
            time.sleep(3.0)
            
            conn.disconnect()
            
            if success:
                self.render_blocks(data)
            else:
                QtWidgets.QMessageBox.warning(self, "Aviso", f"No se pudieron leer los bloques: {data}")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Fallo en la sincronización: {e}")
            
        finally:
            for group in self.path_groups:
                group.setVisible(True)
            self.lbl_loading.setVisible(False)
            
            if hasattr(main_window, 'set_usb_disconnected'):
                main_window.set_usb_disconnected()

    def render_blocks(self, blocks):
        # Clear existing blocks
        for layout in self.path_layouts.values():
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
                    
        # Map blocks by slot_idx
        blocks_by_slot = {b["slot_idx"]: b for b in blocks if "slot_idx" in b}
        
        path_bases = [("1A", 0), ("1B", 10), ("2A", 20), ("2B", 30)]
        for path_name, base_idx in path_bases:
            layout = self.path_layouts[path_name]
            
            for i in range(10):
                slot_idx = base_idx + i
                block = blocks_by_slot.get(slot_idx)
                
                if block:
                    card = BlockCard(block, self)
                    card.clicked_sig.connect(self.on_block_clicked)
                    layout.addWidget(card)
                else:
                    layout.addWidget(EmptyBlockCard(self))
                    
                if i < 9:
                    layout.addWidget(ConnectorCard(has_split_merge=False, parent=self))

    def on_block_clicked(self, block_data):
        dialog = BlockEditorDialog(block_data, self)
        if dialog.exec():
            # Refresh visualization to show updated name/category
            self.sync_blocks()

