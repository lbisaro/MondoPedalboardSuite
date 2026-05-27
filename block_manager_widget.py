import sys
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtSvgWidgets import QSvgWidget
import qtawesome as qta
import json

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
        
        form_layout = QtWidgets.QFormLayout()
        
        self.txt_hex = QtWidgets.QLineEdit()
        self.txt_hex.setReadOnly(True)
        self.txt_hex.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
        form_layout.addRow("ID Hex:", self.txt_hex)
        
        self.cmb_category = QtWidgets.QComboBox()
        self.cmb_category.addItems(list(CATEGORY_COLORS.keys()))
        self.cmb_category.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
        self.cmb_category.currentTextChanged.connect(self.on_category_changed)
        form_layout.addRow("Categoría:", self.cmb_category)
        
        self.cmb_name = QtWidgets.QComboBox()
        self.cmb_name.setEditable(True)
        self.cmb_name.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
        form_layout.addRow("Nombre:", self.cmb_name)
        
        layout.addLayout(form_layout)
        
        # Parámetros (solo lectura)
        lbl_params = QtWidgets.QLabel("Parámetros disponibles (solo lectura):")
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
        models = self.catalog.get(category, [])
        if not models:
            # Try matching prefixes (e.g., Pitch/Synth -> Pitch)
            for k, v in self.catalog.items():
                if k.lower() in category.lower() or category.lower() in k.lower():
                    models = v
                    break
        names = sorted([m.get("name", "") for m in models if m.get("name")])
        self.cmb_name.addItems(names)

    def load_data(self):
        self.txt_hex.setText(self.hex_id or "Desconocido")
        
        if self.full_module:
            cat = self.full_module.get("category", "Unknown")
            idx = self.cmb_category.findText(cat)
            if idx >= 0:
                self.cmb_category.setCurrentIndex(idx)
            
            # This triggers on_category_changed and populates cmb_name
            name = self.full_module.get("name", "")
            self.cmb_name.setCurrentText(name)
        else:
            cat = self.block_data.get("category", "Unknown")
            idx = self.cmb_category.findText(cat)
            if idx >= 0:
                self.cmb_category.setCurrentIndex(idx)
                
            name = self.block_data.get("name", "")
            self.cmb_name.setCurrentText(name)
                
        # Draw parameter bars
        _, color = get_icon_for_category(cat)
        
        params = self.block_data.get("params_a", [])
        
        for i, p in enumerate(params):
            val_str = f"{p:.1f}" if isinstance(p, float) else str(p)
            name = f"Prm. {i}"
            bar = ParameterBar(name, val_str, color, self)
            self.params_layout.addWidget(bar)
            
        self.params_layout.addStretch()

    def save_data(self):
        if not self.hex_id:
            QtWidgets.QMessageBox.warning(self, "Error", "No se puede guardar un módulo sin ID hexadecimal.")
            return
            
        new_data = {
            "name": self.cmb_name.currentText().strip(),
            "category": self.cmb_category.currentText(),
            "variant": None
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
        
        self.setFixedSize(70, 75)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setObjectName("BlockCard")
        self.setStyleSheet("""
            QFrame#BlockCard {
                background-color: transparent;
                border: 2px solid #333;
                border-radius: 8px;
            }
            QFrame#BlockCard:hover {
                border: 2px solid #fff;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        cat = block_data.get("category", "Unknown")
        icon_path, color = get_icon_for_category(cat)
        
        self.svg_widget = QSvgWidget(icon_path)
        self.svg_widget.setFixedSize(40, 40)
        
        abbr = ABBREVIATIONS.get(cat, cat[:4])
        lbl_cat = QtWidgets.QLabel(abbr)
        lbl_cat.setAlignment(QtCore.Qt.AlignCenter)
        lbl_cat.setStyleSheet("color: white; font-size: 8pt; font-weight: bold; background: transparent;")
        
        layout.addWidget(self.svg_widget, alignment=QtCore.Qt.AlignCenter)
        layout.addWidget(lbl_cat, alignment=QtCore.Qt.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked_sig.emit(self.block_data)
        super().mousePressEvent(event)


class EmptyBlockCard(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(70, 75)
        self.setObjectName("EmptyBlock")
        self.setStyleSheet("""
            QFrame#EmptyBlock {
                background-color: transparent;
                border: 2px dashed #333;
                border-radius: 8px;
            }
        """)

class ConnectorCard(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(15, 75)
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw small circle in the vertical center
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#666"))
        
        cx = self.width() // 2
        cy = self.height() // 2
        radius = 4
        
        painter.drawEllipse(QtCore.QPoint(cx, cy), radius, radius)


class BlockManagerWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        lbl_title = QtWidgets.QLabel("BLOCK MANAGER")
        lbl_title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #00ADB5;")
        
        self.btn_sync = QtWidgets.QPushButton(qta.icon('fa5s.sync'), " Sincronizar con Helix")
        self.btn_sync.setObjectName("AccentButton")
        self.btn_sync.setFixedHeight(35)
        self.btn_sync.clicked.connect(self.sync_blocks)
        
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
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
            self.paths_layout.addWidget(group)
            
        self.paths_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # Draw empty slots initially
        self.render_blocks([])

    def sync_blocks(self):
        log.info("Sincronizando bloques...")
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
            if hasattr(main_window, 'set_usb_disconnected'):
                main_window.set_usb_disconnected()

    def render_blocks(self, blocks):
        # Clear existing blocks
        for layout in self.path_layouts.values():
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                    
        # Map blocks by slot_idx
        blocks_by_slot = {b["slot_idx"]: b for b in blocks if "slot_idx" in b}
        
        path_bases = [("1A", 0), ("1B", 10), ("2A", 20), ("2B", 30)]
        for path_name, base_idx in path_bases:
            layout = self.path_layouts[path_name]
            
            for i in range(10):
                slot_idx = base_idx + i
                block = blocks_by_slot.get(slot_idx)
                
                if block and block.get("type") == "effect":
                    card = BlockCard(block, self)
                    card.clicked_sig.connect(self.on_block_clicked)
                    layout.addWidget(card)
                else:
                    layout.addWidget(EmptyBlockCard(self))
                    
                if i < 9: # Add connector except after the last block
                    layout.addWidget(ConnectorCard(self))

    def on_block_clicked(self, block_data):
        dialog = BlockEditorDialog(block_data, self)
        if dialog.exec():
            # Refresh visualization to show updated name/category
            self.sync_blocks()

