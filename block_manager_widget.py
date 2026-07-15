import sys
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtSvgWidgets import QSvgWidget
import qtawesome as qta
import json
import os

from helix_connection import HelixConnection
from utils.modules import get_module, save_module, get_categories

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

class ParameterEditorDialog(QtWidgets.QDialog):
    def __init__(self, param_data, raw_val, parent=None):
        super().__init__(parent)
        self.param_data = param_data.copy()
        self.raw_val = float(raw_val) if raw_val != "" else 0.0
        
        self.setWindowTitle(f"Editar Parámetro: {self.param_data.get('name', '')}")
        self.setMinimumWidth(450)
        self.setStyleSheet("background-color: #1a1a1a; color: white;")
        
        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()
        
        self.txt_name = QtWidgets.QLineEdit(self.param_data.get("name", ""))
        self.txt_name.setStyleSheet("background-color: #333; color: white; border: 1px solid #555; padding: 4px;")
        self.txt_name.textChanged.connect(self.update_preview)
        form_layout.addRow("Nombre:", self.txt_name)
        
        self.cmb_type = QtWidgets.QComboBox()
        self.cmb_type.addItems(["continuous", "bool", "enum"])
        self.cmb_type.setStyleSheet("background-color: #333; color: white; border: 1px solid #555; padding: 4px;")
        
        curr_type = self.param_data.get("type", "continuous")
        if curr_type == "switch": curr_type = "bool"
        if curr_type == "dropdown": curr_type = "enum"
        self.cmb_type.setCurrentText(curr_type)
        self.cmb_type.currentTextChanged.connect(self.on_type_changed)
        form_layout.addRow("Tipo:", self.cmb_type)
        
        self.dynamic_widget = QtWidgets.QWidget()
        self.dynamic_layout = QtWidgets.QFormLayout(self.dynamic_widget)
        self.dynamic_layout.setContentsMargins(0, 0, 0, 0)
        
        self.w_min = QtWidgets.QLineEdit(str(self.param_data.get("min", 0.0)))
        self.w_max = QtWidgets.QLineEdit(str(self.param_data.get("max", 10.0)))
        self.w_mult = QtWidgets.QLineEdit(str(self.param_data.get("multiplier", 1.0)))
        self.w_dec = QtWidgets.QLineEdit(str(self.param_data.get("decimals", 0)))
        self.w_unit = QtWidgets.QLineEdit(self.param_data.get("unit", ""))
        
        for w in [self.w_min, self.w_max, self.w_mult, self.w_dec, self.w_unit]:
            w.setStyleSheet("background-color: #333; color: white; border: 1px solid #555; padding: 4px;")
            w.textChanged.connect(self.update_preview)
            
        opts_str = ""
        opts_data = self.param_data.get("options", [])
        if isinstance(opts_data, list):
            opts_str = ", ".join(f"{o.get('value', i)}:{o.get('name', '')}" for i, o in enumerate(opts_data))
        self.w_options = QtWidgets.QLineEdit(opts_str)
        self.w_options.setPlaceholderText("Ej: 0:Off, 1:Rojo, 2:Verde")
        self.w_options.setStyleSheet("background-color: #333; color: white; border: 1px solid #555; padding: 4px;")
        self.w_options.textChanged.connect(self.update_preview)
        
        form_layout.addRow(self.dynamic_widget)
        layout.addLayout(form_layout)
        
        preview_group = QtWidgets.QGroupBox(" Vista Previa ")
        preview_group.setStyleSheet("QGroupBox { border: 1px solid #555; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; color: #888; }")
        p_layout = QtWidgets.QVBoxLayout(preview_group)
        self.lbl_preview = QtWidgets.QLabel("")
        self.lbl_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("font-size: 18px; font-weight: bold; color: #4CAF50; padding: 10px;")
        p_layout.addWidget(self.lbl_preview)
        layout.addWidget(preview_group)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QtWidgets.QPushButton("Guardar")
        btn_save.setObjectName("AccentButton")
        btn_save.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
        
        self.on_type_changed(self.cmb_type.currentText())
        
    def on_type_changed(self, p_type):
        while self.dynamic_layout.rowCount() > 0:
            self.dynamic_layout.removeRow(0)
            
        if p_type == "continuous":
            self.dynamic_layout.addRow("Mínimo:", self.w_min)
            self.dynamic_layout.addRow("Máximo:", self.w_max)
            self.dynamic_layout.addRow("Multiplicador:", self.w_mult)
            self.dynamic_layout.addRow("Decimales:", self.w_dec)
            self.dynamic_layout.addRow("Unidad:", self.w_unit)
        elif p_type == "enum":
            self.dynamic_layout.addRow("Opciones:", self.w_options)
            
        self.update_preview()
        
    def update_preview(self):
        p_type = self.cmb_type.currentText()
        fmt_val = str(self.raw_val)
        
        try:
            if p_type == "continuous":
                mult = float(self.w_mult.text() or 1.0)
                dec = int(self.w_dec.text() or 0)
                unit = self.w_unit.text()
                calc = self.raw_val * mult
                fmt_val = f"{calc:.{dec}f}{unit}"
            elif p_type == "bool":
                fmt_val = "On" if self.raw_val >= 0.5 else "Off"
            elif p_type == "enum":
                opts_str = self.w_options.text()
                match_txt = str(self.raw_val)
                for opt in opts_str.split(","):
                    if ":" in opt:
                        k, v = opt.split(":", 1)
                        if k.strip().isdigit() and int(k.strip()) == int(self.raw_val):
                            match_txt = v.strip()
                            break
                fmt_val = match_txt
        except Exception:
            fmt_val = "Error de formato"
            
        self.lbl_preview.setText(f"{fmt_val}   <span style='color:#888; font-size:12px;'>(RAW: {self.raw_val})</span>")
        
    def get_data(self):
        p_type = self.cmb_type.currentText()
        data = {
            "index": self.param_data.get("index", 0),
            "name": self.txt_name.text().strip(),
            "type": p_type
        }
        if p_type == "continuous":
            try:
                data["min"] = float(self.w_min.text() or 0.0)
                data["max"] = float(self.w_max.text() or 10.0)
                data["multiplier"] = float(self.w_mult.text() or 1.0)
                data["decimals"] = int(self.w_dec.text() or 0)
                data["unit"] = self.w_unit.text().strip()
            except ValueError:
                pass
        elif p_type == "enum":
            opts_parsed = []
            for opt in self.w_options.text().split(","):
                if ":" in opt:
                    k, v = opt.split(":", 1)
                    try:
                        opts_parsed.append({"value": int(k.strip()), "name": v.strip()})
                    except ValueError:
                        pass
            if opts_parsed:
                data["options"] = opts_parsed
                
        return data

class BlockEditorDialog(QtWidgets.QDialog):
    def __init__(self, block_data, parent=None):
        super().__init__(parent)
        self.block_data = block_data
        self.hex_id = block_data.get('hex_id')
        self.full_module = get_module(self.hex_id) if self.hex_id else None
        self.categories_db = get_categories()
        
        self.catalog = {}
        try:
            with open("utils/helix_catalog.json", encoding="utf-8") as f:
                data = json.load(f)
                self.catalog = data.get("catalog", {})
        except Exception as e:
            print("Error loading catalog:", e)
            
        self.cabs_mics = []
        try:
            with open("utils/cabs_mics.json", encoding="utf-8") as f:
                self.cabs_mics = json.load(f)
        except Exception as e:
            print("Error loading cabs_mics:", e)
            
        self.setWindowTitle("Editar Módulo")
        self.setMinimumWidth(1000)
        self.setMinimumHeight(600)
        self.setStyleSheet("background-color: #1a1a1a; color: white;")
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        top_layout = QtWidgets.QHBoxLayout()
        form_layout = QtWidgets.QFormLayout()
        
        # Hex ID
        self.lbl_hex = QtWidgets.QLabel()
        self.lbl_hex.setStyleSheet("font-weight: bold; font-size: 14px;")
        form_layout.addRow("ID Hex:", self.lbl_hex)
        
        # Category
        self.cmb_category = QtWidgets.QComboBox()
        self.cmb_category.addItems(list(self.categories_db.keys()))
        self.cmb_category.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
        self.cmb_category.currentTextChanged.connect(self.on_category_changed)
        form_layout.addRow("Categoría:", self.cmb_category)
        
        # Subcategory
        self.cmb_subcategory = QtWidgets.QComboBox()
        self.cmb_subcategory.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
        self.cmb_subcategory.currentTextChanged.connect(self.update_name_suggestions)
        form_layout.addRow("Subcategoría:", self.cmb_subcategory)
        
        # Name
        self.cmb_name = QtWidgets.QComboBox()
        self.cmb_name.setEditable(True)
        self.cmb_name.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
        
        completer = self.cmb_name.completer()
        if completer:
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            completer.setFilterMode(QtCore.Qt.MatchContains)
            
        self.cmb_name.currentTextChanged.connect(self.on_name_changed)
        form_layout.addRow("Nombre:", self.cmb_name)
        
        # Model ID
        self.lbl_model_id = QtWidgets.QLabel()
        self.lbl_model_id.setStyleSheet("color: #888; font-style: italic;")
        form_layout.addRow("Model ID:", self.lbl_model_id)
        
        # Based On
        self.lbl_based_on = QtWidgets.QLabel("")
        self.lbl_based_on.setStyleSheet("color: #aaa; font-style: italic; font-size: 14px;")
        form_layout.addRow("Basado en:", self.lbl_based_on)
        
        # Link existing
        self.chk_link = QtWidgets.QCheckBox()
        self.chk_link.setToolTip("Enlazar a modelo existente (ignorar parámetros)")
        self.chk_link.toggled.connect(self.on_link_toggled)
        form_layout.addRow("", self.chk_link)
        
        top_layout.addLayout(form_layout)
        
        self.lbl_image = QtWidgets.QLabel("Sin Icono")
        self.lbl_image.setFixedSize(200, 160)
        self.lbl_image.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_image.setStyleSheet("background-color: transparent; border: none;")
        top_layout.addWidget(self.lbl_image)
        
        layout.addLayout(top_layout)
        
        # Parameters Section
        self.params_container = QtWidgets.QWidget()
        params_layout = QtWidgets.QVBoxLayout(self.params_container)
        params_layout.setContentsMargins(0, 10, 0, 0)
        
        self.table_params = QtWidgets.QTableWidget()
        self.table_params.setColumnCount(3)
        self.table_params.setHorizontalHeaderLabels(["Parámetro", "Valor", "RAW"])
        self.table_params.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.table_params.setColumnWidth(0, 200)
        self.table_params.setColumnWidth(1, 150)
        self.table_params.horizontalHeader().setStretchLastSection(True)
        self.table_params.verticalHeader().setVisible(False)
        self.table_params.setShowGrid(False)
        self.table_params.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_params.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_params.itemDoubleClicked.connect(self.on_param_double_clicked)
        self.table_params.setStyleSheet("""
            QTableWidget { background-color: #222; color: white; border: none; }
            QHeaderView::section { background-color: #333; color: white; border: none; padding: 4px; font-weight: bold; text-align: left; }
        """)
        params_layout.addWidget(self.table_params)
        
        layout.addWidget(self.params_container)
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Guardar")
        self.btn_save.setStyleSheet("background-color: #E53935; color: white; font-weight: bold; padding: 5px; min-width: 100px;")
        self.btn_save.clicked.connect(self.save_data)
        
        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet("background-color: #555; color: white; padding: 5px; min-width: 100px;")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)
        
        self.on_category_changed(self.cmb_category.currentText())

    def _get_models_for_category(self, category):
        models = self.catalog.get(category, [])
        if not models:
            for k, v in self.catalog.items():
                if k.lower() in category.lower() or category.lower() in k.lower():
                    return v
        return models

    def on_category_changed(self, category):
        self.cmb_subcategory.blockSignals(True)
        self.cmb_subcategory.clear()
        subcats = self.categories_db.get(category, [])
        self.cmb_subcategory.addItems(subcats)
        self.cmb_subcategory.blockSignals(False)
        
        self.update_name_suggestions()
        
    def update_name_suggestions(self, *args):
        current_text = self.cmb_name.currentText()
        
        self.cmb_name.blockSignals(True)
        self.cmb_name.clear()
        
        category = self.cmb_category.currentText()
        selected_subcat = self.cmb_subcategory.currentText()
        
        models = self._get_models_for_category(category)
        
        names = []
        for m in models:
            name = m.get("name", "")
            if not name:
                continue
                
            subcats_list = m.get("subcategories", [])
            if selected_subcat and subcats_list:
                if selected_subcat.lower() not in [s.lower() for s in subcats_list]:
                    continue
                    
            if subcats_list:
                names.append(f"{name} [{', '.join(subcats_list)}]")
            else:
                names.append(name)
                
        self.cmb_name.addItems(sorted(names))
        self.cmb_name.setCurrentText(current_text)
        self.cmb_name.blockSignals(False)
        
        self.update_model_id()
        
    def on_name_changed(self, text):
        self.update_model_id()
        
        # Pull data from catalog
        cat = self.cmb_category.currentText()
        models = self._get_models_for_category(cat)
        
        model_data = None
        for m in models:
            m_name = m.get("name", "")
            subcats_list = m.get("subcategories", [])
            m_str = f"{m_name} [{', '.join(subcats_list)}]" if subcats_list else m_name
            if m_str == text:
                model_data = m
                break
        
        if model_data:
            self.lbl_based_on.setText(model_data.get("based_on", ""))
            self.current_image_path = model_data.get("image", "")
            
            # If it's a new module, auto-populate the table automatically
            if not self.full_module:
                self.create_params_profile()
            else:
                self.current_parameters = self.full_module.get("parameters", [])
                self.populate_table()
        if hasattr(self, 'current_image_path') and self.current_image_path and os.path.exists(self.current_image_path):
            pixmap = QtGui.QPixmap(self.current_image_path).scaled(200, 160, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.lbl_image.setPixmap(pixmap)
        else:
            self.lbl_image.clear()
            self.lbl_image.setText("Sin Icono")
            
    def on_param_double_clicked(self, item):
        row = item.row()
        if not hasattr(self, 'current_parameters') or row < 0 or row >= len(self.current_parameters): 
            return
            
        p_data = self.current_parameters[row]
        idx = p_data.get("index", row)
        real_params = self.block_data.get("params_a", [])
        raw_val = real_params[idx] if idx < len(real_params) else 0.0
        
        dialog = ParameterEditorDialog(p_data, raw_val, self)
        if dialog.exec_():
            self.current_parameters[row] = dialog.get_data()
            self.populate_table()
        
    def update_model_id(self):
        cat = self.cmb_category.currentText().lower().strip().replace(" ", "_").replace("/", "_")
        subcat = self.cmb_subcategory.currentText().lower().strip().replace(" ", "_").replace("/", "_")
        
        text = self.cmb_name.currentText()
        name = text.split(" [")[0].strip() if " [" in text and text.endswith("]") else text.strip()
        name = name.lower().replace(" ", "_")
        
        prefix = f"{cat}_{subcat}" if subcat else cat
        
        if name:
            self.lbl_model_id.setText(f"{prefix}_{name}")
        else:
            self.lbl_model_id.setText("")
            
    def on_link_toggled(self, checked):
        self.params_container.setVisible(not checked)

    def load_data(self):
        self.lbl_hex.setText(self.hex_id or "Desconocido")
        
        if self.full_module:
            # Es un módulo ya mapeado
            self.lbl_hex.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 14px;") # Verde
            
            cat = self.full_module.get("category", "Unknown")
            self.cmb_category.setCurrentText(cat)
            
            self.cmb_subcategory.setCurrentText(self.full_module.get("variant", ""))
            
            name = self.full_module.get("name", "")
            variant = self.full_module.get("variant", "")
            formatted_name = name
            models = self._get_models_for_category(cat)
            for m in models:
                if m.get("name") == name:
                    subcats_list = m.get("subcategories", [])
                    if variant and subcats_list:
                        if variant.lower() in [s.lower() for s in subcats_list]:
                            formatted_name = f"{name} [{', '.join(subcats_list)}]"
                            break
                    elif subcats_list:
                        formatted_name = f"{name} [{', '.join(subcats_list)}]"
                        break
            self.cmb_name.setCurrentText(formatted_name)
            self.lbl_based_on.setText(self.full_module.get("based_on", ""))
            img_path = self.full_module.get("image", "")
            
            if img_path and os.path.exists(img_path):
                pixmap = QtGui.QPixmap(img_path).scaled(200, 160, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.lbl_image.setPixmap(pixmap)
                
            self.current_parameters = self.full_module.get("parameters", [])
            self.populate_table()
            
        else:
            # Nuevo módulo
            self.lbl_hex.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 14px;") # Naranja
            cat = self.block_data.get("category", "Unknown")
            if cat in self.categories_db:
                self.cmb_category.setCurrentText(cat)
                
            self.cmb_name.setCurrentText(self.block_data.get("name", ""))
            
            self.table_params.setRowCount(0)
            
            # Si el bloque ya tenía un nombre (ej. detectado de params_a), cargar perfil automáticamente
            if self.block_data.get("name", ""):
                self.create_params_profile()

    def create_params_profile(self):
        real_params = self.block_data.get("params_a", [])
        
        cat = self.cmb_category.currentText()
        models = self._get_models_for_category(cat)
        text = self.cmb_name.currentText()
        
        model_data = None
        for m in models:
            m_name = m.get("name", "")
            subcats_list = m.get("subcategories", [])
            m_str = f"{m_name} [{', '.join(subcats_list)}]" if subcats_list else m_name
            if m_str == text:
                model_data = m
                break
                
        catalog_params = model_data.get("parameters", []) if model_data else []
        
        params = []
        for i, val in enumerate(real_params):
            p_name = f"Prm. {i}"
            if i < len(catalog_params) and "name" in catalog_params[i]:
                p_name = catalog_params[i]["name"]
                
            params.append({
                "index": i,
                "name": p_name,
                "type": "continuous",
                "min": 0.0,
                "max": 10.0,
                "multiplier": 10.0 if isinstance(val, float) else 1.0,
                "decimals": 1 if isinstance(val, float) else 0,
                "unit": ""
            })
        self.current_parameters = params
        self.populate_table()

    def populate_table(self):
        if not hasattr(self, 'current_parameters'):
            return
            
        parameters = self.current_parameters
        self.table_params.setRowCount(len(parameters))
        
        real_params = self.block_data.get("params_a", [])
        
        # Print raw parameters to console for debugging
        print(f"DEBUG - RAW params_a for {self.block_data.get('hex_id')}:", real_params)
        print(f"DEBUG - current_parameters list from JSON:", [(p.get('index'), p.get('name')) for p in parameters])
        
        cat = self.cmb_category.currentText()
        _, cat_color = get_icon_for_category(cat)
        
        for row, p in enumerate(parameters):
            idx = p.get("index", row)
            
            raw_val = real_params[idx] if idx < len(real_params) else 0.0
            
            p_type = p.get("type", "continuous")
            if p_type == "switch": p_type = "bool"
            if p_type == "dropdown": p_type = "enum"
            
            fmt_val = str(raw_val)
            if p_type == "continuous":
                mult = p.get("multiplier", 1.0)
                dec = p.get("decimals", 0)
                unit = p.get("unit", "")
                calc = float(raw_val) * mult
                fmt_val = f"{calc:.{dec}f}{unit}"
            elif p_type == "bool":
                fmt_val = "On" if float(raw_val) >= 0.5 else "Off"
            elif p_type == "enum":
                opts = p.get("options", [])
                match_txt = str(raw_val)
                for opt in opts:
                    if opt.get("value") == int(float(raw_val)):
                        match_txt = opt.get("name")
                        break
                fmt_val = match_txt
            elif p_type == "mic":
                match_txt = f"Mic {int(float(raw_val))}"
                for mic in getattr(self, 'cabs_mics', []):
                    if mic.get("id") == int(float(raw_val)):
                        match_txt = mic.get("model", match_txt)
                        break
                fmt_val = match_txt
                
            item_param = QtWidgets.QTableWidgetItem(p.get("name", f"Prm. {idx}"))
            item_param.setForeground(QtGui.QBrush(QtGui.QColor(cat_color)))
            item_param.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.table_params.setItem(row, 0, item_param)
            
            item_val = QtWidgets.QTableWidgetItem(str(fmt_val))
            item_val.setForeground(QtGui.QBrush(QtGui.QColor(cat_color)))
            item_val.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.table_params.setItem(row, 1, item_val)
            
            item_raw = QtWidgets.QTableWidgetItem(str(raw_val))
            item_raw.setForeground(QtGui.QBrush(QtGui.QColor("#888888")))
            item_raw.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.table_params.setItem(row, 2, item_raw)

    def save_data(self):
        if not self.hex_id:
            QtWidgets.QMessageBox.warning(self, "Error", "No se puede guardar un módulo sin ID hexadecimal.")
            return
            
        model_id = self.lbl_model_id.text()
        if not model_id:
            QtWidgets.QMessageBox.warning(self, "Error", "El nombre está vacío.")
            return
            
        # Validación: El nombre debe existir en helix_catalog.json
        cat = self.cmb_category.currentText()
        models = self._get_models_for_category(cat)
        valid_names = [m.get("name") for m in models]
        
        text = self.cmb_name.currentText()
        name = text.split(" [")[0].strip() if " [" in text and text.endswith("]") else text.strip()
        
        if name not in valid_names:
            QtWidgets.QMessageBox.warning(self, "Error", "El módulo no existe en el catálogo maestro.\nPor favor, añade la información en 'helix_catalog.json' primero.")
            return
            
        model_data = {
            "name": name,
            "category": self.cmb_category.currentText(),
            "based_on": self.lbl_based_on.text().strip(),
            "image": getattr(self, 'current_image_path', ''),
            "parameters": []
        }

        if not self.chk_link.isChecked():
            model_data["parameters"] = getattr(self, 'current_parameters', [])
        else:
            # Si estamos enlazando, en realidad no sobreescribimos los parámetros, 
            # confiamos en que el save_module simplemente actualizará el mapping si no pasamos parameters.
            # En la implementación de save_module sobreescribe model_data, así que necesitamos leer el existente.
            
            # Hay que buscar el modelo crudo real en _models_db de utils.modules
            from utils.modules import _models_db
            existing = _models_db.get(model_id)
            if existing:
                model_data["parameters"] = existing.get("parameters", [])
            else:
                # Si no existía, pero quiere enlazar...
                QtWidgets.QMessageBox.information(self, "Info", "Si enlazas a un modelo existente, asegúrate de que el modelo base (Mismo Categoría y Nombre) haya sido grabado primero.")
        
        success = save_module(self.hex_id, self.cmb_subcategory.currentText(), model_id, model_data)
        if success:
            QtWidgets.QMessageBox.information(self, "Éxito", "Módulo guardado correctamente en modules.json")
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
        
        hex_id = block_data.get("hex_id")
        db_module = get_module(hex_id) if hex_id else None
        
        cat = block_data.get("category", "Unknown")
        name = block_data.get("name", "")
        
        if db_module:
            cat = db_module.get("category", cat)
            name = db_module.get("name", name)
            
        slot_idx = block_data.get("slot_idx", -1)
        
        is_io = False
        icon_path, color = get_icon_for_category(cat)
        
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
        
        self.btn_sync = QtWidgets.QPushButton(qta.icon('fa5s.sync'), " Sincronizar (F5)")
        self.btn_sync.setObjectName("AccentButton")
        self.btn_sync.setFixedHeight(35)
        self.btn_sync.clicked.connect(self.sync_blocks)
        
        shortcut_f5 = QtGui.QShortcut(QtGui.QKeySequence("F5"), self)
        shortcut_f5.activated.connect(self.sync_blocks)
        
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

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_has_synced'):
            self._has_synced = True
            QtCore.QTimer.singleShot(100, self.sync_blocks)

    def sync_blocks(self):
        print("Sincronizando bloques...")
        self.btn_sync.setEnabled(False)
        self.btn_sync.setText(" Sincronizando...")
        
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
            
            if success:
                self.last_fetched_blocks = data
                self.render_blocks(data)
            else:
                QtWidgets.QMessageBox.warning(self, "Aviso", f"No se pudieron leer los bloques: {data}")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Fallo al cargar información: {str(e)}")
            if hasattr(main_window, 'set_usb_disconnected'):
                main_window.set_usb_disconnected()
        finally:
            for group in self.path_groups:
                group.setVisible(True)
            self.lbl_loading.setVisible(False)
            self.btn_sync.setEnabled(True)
            self.btn_sync.setText(" Sincronizar (F5)")
            
            if hasattr(main_window, 'set_usb_disconnected'):
                main_window.set_usb_disconnected()
            if 'conn' in locals() and conn:
                conn.disconnect()

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
            # Evitamos reconectar al USB; los datos se guardaron en modules.json localmente.
            # Re-renderizamos para actualizar la UI del bloque (imagen, nombre, color)
            if hasattr(self, 'last_fetched_blocks'):
                self.render_blocks(self.last_fetched_blocks)
