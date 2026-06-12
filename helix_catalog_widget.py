import os
import sys
import json
from PySide6 import QtCore, QtWidgets, QtGui
import qtawesome as qta

def resource_path(relative):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)

class FlowLayout(QtWidgets.QLayout):
    """Layout personalizado para hacer wrap de widgets (como píldoras de tags)."""
    def __init__(self, parent=None, margin=-1, hSpacing=-1, vSpacing=-1):
        super().__init__(parent)
        self._itemList = []
        self.m_hSpace = hSpacing
        self.m_vSpace = vSpacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._itemList.append(item)

    def horizontalSpacing(self):
        if self.m_hSpace >= 0:
            return self.m_hSpace
        else:
            return self.smartSpacing(QtWidgets.QStyle.PixelMetric.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self.m_vSpace >= 0:
            return self.m_vSpace
        else:
            return self.smartSpacing(QtWidgets.QStyle.PixelMetric.PM_LayoutVerticalSpacing)

    def count(self):
        return len(self._itemList)

    def itemAt(self, index):
        if 0 <= index < len(self._itemList):
            return self._itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._itemList):
            return self._itemList.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QtCore.QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._itemList:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QtCore.QSize(left + right, top + bottom)
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0

        for item in self._itemList:
            wid = item.widget()
            spaceX = self.horizontalSpacing()
            if spaceX == -1: spaceX = wid.style().layoutSpacing(QtWidgets.QSizePolicy.ControlType.PushButton, QtWidgets.QSizePolicy.ControlType.PushButton, QtCore.Qt.Orientation.Horizontal)
            spaceY = self.verticalSpacing()
            if spaceY == -1: spaceY = wid.style().layoutSpacing(QtWidgets.QSizePolicy.ControlType.PushButton, QtWidgets.QSizePolicy.ControlType.PushButton, QtCore.Qt.Orientation.Vertical)

            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()

    def smartSpacing(self, pm):
        parent = self.parent()
        if not parent: return -1
        elif parent.isWidgetType(): return parent.style().pixelMetric(pm, None, parent)
        else: return parent.spacing()

class TagPill(QtWidgets.QLabel):
    def __init__(self, text, color="#393E46", text_color="#EEEEEE"):
        super().__init__(text)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: {text_color};
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 8pt;
                font-weight: bold;
            }}
        """)
        self.setAlignment(QtCore.Qt.AlignCenter)

class CatalogItemWidget(QtWidgets.QFrame):
    def __init__(self, data, category):
        super().__init__()
        self.data = data
        self.category = category
        
        self.setObjectName("CatalogItem")
        self.setStyleSheet("""
            #CatalogItem {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 8px;
            }
            #CatalogItem:hover {
                border: 1px solid #00ADB5;
                background-color: #252525;
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Image
        self.img_label = QtWidgets.QLabel()
        self.img_label.setFixedSize(100, 100)
        self.img_label.setAlignment(QtCore.Qt.AlignCenter)
        self.img_label.setStyleSheet("background: transparent;")
        
        img_path = data.get("image", "")
        if img_path:
            full_path = resource_path(img_path)
            if os.path.exists(full_path):
                pixmap = QtGui.QPixmap(full_path).scaled(100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.img_label.setPixmap(pixmap)
            else:
                self.img_label.setPixmap(qta.icon("fa5s.image", color="#555").pixmap(64, 64))
        else:
            self.img_label.setPixmap(qta.icon("fa5s.image", color="#555").pixmap(64, 64))
            
        layout.addWidget(self.img_label)
        
        # Details
        details_layout = QtWidgets.QVBoxLayout()
        details_layout.setSpacing(4)
        
        # --- Top Row ---
        top_row_layout = QtWidgets.QHBoxLayout()
        
        # Name
        name_lbl = QtWidgets.QLabel(data.get("name", "Unknown"))
        name_lbl.setStyleSheet("font-size: 14pt; font-weight: bold; color: #FFFFFF; background: transparent; border: none;")
        top_row_layout.addWidget(name_lbl)
        
        # Based On
        based_on_txt = data.get('based_on', 'Line 6 Original')
        based_lbl = QtWidgets.QLabel(based_on_txt)
        based_lbl.setStyleSheet("font-size: 11pt; color: #00ADB5; font-style: italic; background: transparent; border: none;")
        top_row_layout.addWidget(based_lbl)
        
        top_row_layout.addStretch()
        
        # Category & Instrument Tags (top right)
        cat_color = "#E84545" if category == "Distortion" else "#2B2E4A" if category == "Amp" else "#903749" if category == "Cab" else "#53354A"
        top_row_layout.addWidget(TagPill(category.upper(), color=cat_color))
        
        for inst in data.get("instruments", []):
            inst_color = "#00ADB5" if inst == "Bass" else "#393E46"
            top_row_layout.addWidget(TagPill(inst, color=inst_color))
            
        details_layout.addLayout(top_row_layout)
        
        # --- Custom Tags ---
        self.custom_tags_widget = QtWidgets.QWidget()
        self.custom_tags_widget.setStyleSheet("background: transparent; border: none;")
        custom_tags_layout = FlowLayout(self.custom_tags_widget, margin=0, hSpacing=8, vSpacing=4)
        
        has_custom_tags = False
        for tag in data.get("tags", []):
            custom_tags_layout.addWidget(TagPill(tag))
            has_custom_tags = True
            
        if has_custom_tags:
            details_layout.addWidget(self.custom_tags_widget)
            
        # --- Description ---
        desc_lbl = QtWidgets.QLabel(data.get("description", "No description available."))
        desc_lbl.setStyleSheet("font-size: 10pt; color: #AAAAAA; background: transparent; border: none;")
        desc_lbl.setWordWrap(True)
        details_layout.addWidget(desc_lbl)
        
        details_layout.addStretch()
        
        layout.addLayout(details_layout)
        layout.setStretchFactor(details_layout, 1)

class HelixCatalogWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog_data = {}
        self.all_items = [] # (category, data)
        self.load_data()
        
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Sidebar (Filters)
        sidebar = QtWidgets.QFrame()
        sidebar.setFixedWidth(250)
        sidebar.setObjectName("Sidebar")
        sidebar.setStyleSheet("#Sidebar { background-color: #1A1A1A; border: 1px solid #333; border-radius: 8px; }")
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(15)
        
        # Search
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search models...")
        self.search_input.setStyleSheet("background-color: #222831; border: 1px solid #393E46; border-radius: 4px; padding: 6px; color: white;")
        self.search_input.textChanged.connect(self.filter_items)
        lbl_search = QtWidgets.QLabel("Search:")
        lbl_search.setStyleSheet("color: #00ADB5; background: transparent; border: none;")
        sidebar_layout.addWidget(lbl_search)
        sidebar_layout.addWidget(self.search_input)
        
        # Category Filter
        self.cat_combo = QtWidgets.QComboBox()
        self.cat_combo.addItem("All Categories")
        for cat in sorted(self.catalog_data.keys()):
            if cat == "Preamp": continue
            self.cat_combo.addItem(cat)
        self.cat_combo.currentTextChanged.connect(self.update_dynamic_filters)
        lbl_cat = QtWidgets.QLabel("Category:")
        lbl_cat.setStyleSheet("color: #00ADB5; background: transparent; border: none;")
        sidebar_layout.addWidget(lbl_cat)
        sidebar_layout.addWidget(self.cat_combo)
        
        # Dynamic Filters container
        self.dynamic_filters_widget = QtWidgets.QWidget()
        self.dynamic_filters_widget.setStyleSheet("background: transparent; border: none;")
        self.dynamic_filters_layout = QtWidgets.QVBoxLayout(self.dynamic_filters_widget)
        self.dynamic_filters_layout.setContentsMargins(0, 0, 0, 0)
        self.dynamic_filters_layout.setSpacing(15)
        sidebar_layout.addWidget(self.dynamic_filters_widget)
        
        # Instrument Filter
        self.inst_combo = QtWidgets.QComboBox()
        self.inst_combo.addItems(["All Instruments", "Guitar", "Bass", "Universal"])
        self.inst_combo.currentTextChanged.connect(self.filter_items)
        lbl_inst = QtWidgets.QLabel("Instrument:")
        lbl_inst.setStyleSheet("color: #00ADB5; background: transparent; border: none;")
        sidebar_layout.addWidget(lbl_inst)
        sidebar_layout.addWidget(self.inst_combo)
        
        # Stats
        self.lbl_stats = QtWidgets.QLabel("")
        self.lbl_stats.setStyleSheet("color: #888; border: none;")
        sidebar_layout.addWidget(self.lbl_stats)
        
        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)
        
        # Main Area (Scroll Area for Items)
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.scroll_content = QtWidgets.QWidget()
        self.scroll_content.setStyleSheet("background-color: transparent;")
        self.items_layout = QtWidgets.QVBoxLayout(self.scroll_content)
        self.items_layout.setContentsMargins(10, 0, 10, 0)
        self.items_layout.setSpacing(10)
        self.items_layout.setAlignment(QtCore.Qt.AlignTop)
        
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)
        
        # Initial Render
        self.render_items(self.all_items)
        
    def load_data(self):
        try:
            tags_path = resource_path('utils/tags.json')
            if os.path.exists(tags_path):
                with open(tags_path, 'r', encoding='utf-8') as f:
                    self.tags_data = json.load(f)
            else:
                self.tags_data = {}
                
            path = resource_path('utils/helix_catalog.json')
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.catalog_data = data.get("catalog", {})
                    for cat, items in self.catalog_data.items():
                        if cat == "Preamp": continue
                        for item in items:
                            self.all_items.append((cat, item))
        except Exception as e:
            print(f"Error loading catalog: {e}")
            
    def update_dynamic_filters(self, category):
        # Clear existing dynamic filters
        while self.dynamic_filters_layout.count():
            child = self.dynamic_filters_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        self.dynamic_combos = {} # dict to keep track of combos
        
        if category == "All Categories" or category not in getattr(self, 'tags_data', {}):
            self.filter_items()
            return
            
        # Extract tag types for this category
        cat_tags = self.tags_data[category]
        groups = {} # type -> list of tags
        for tag, info in cat_tags.items():
            t_type = info.get("type", "Tags")
            if t_type not in groups:
                groups[t_type] = []
            groups[t_type].append(tag)
            
        for g_type in sorted(groups.keys()):
            tags_list = groups[g_type]
            lbl = QtWidgets.QLabel(f"{g_type}:")
            lbl.setStyleSheet("color: #00ADB5; background: transparent; border: none;")
            combo = QtWidgets.QComboBox()
            combo.addItem("All")
            for t in sorted(tags_list):
                combo.addItem(t)
            combo.currentTextChanged.connect(self.filter_items)
            
            self.dynamic_filters_layout.addWidget(lbl)
            self.dynamic_filters_layout.addWidget(combo)
            self.dynamic_combos[g_type] = combo
            
        self.filter_items()

    def filter_items(self):
        search_txt = self.search_input.text().lower()
        sel_cat = self.cat_combo.currentText()
        sel_inst = self.inst_combo.currentText()
        
        active_tags = []
        if hasattr(self, 'dynamic_combos'):
            for c in self.dynamic_combos.values():
                t = c.currentText()
                if t != "All":
                    active_tags.append(t)
        
        filtered = []
        for cat, item in self.all_items:
            # Filter by Category
            if sel_cat != "All Categories" and cat != sel_cat:
                continue
                
            # Filter by Instrument
            if sel_inst != "All Instruments":
                insts = item.get("instruments", [])
                if sel_inst not in insts:
                    if sel_inst == "Guitar" and not insts:
                        pass
                    else:
                        continue
                        
            # Filter by Dynamic Tags
            if active_tags:
                item_tags = item.get("tags", [])
                match_all = True
                for req_tag in active_tags:
                    if req_tag not in item_tags:
                        match_all = False
                        break
                if not match_all:
                    continue
                        
            # Filter by Search Text
            if search_txt:
                name = item.get("name", "").lower()
                based = item.get("based_on", "").lower()
                desc = item.get("description", "").lower()
                if search_txt not in name and search_txt not in based and search_txt not in desc:
                    continue
                    
            filtered.append((cat, item))
            
        self.render_items(filtered)
        
    def clear_layout(self):
        while self.items_layout.count():
            child = self.items_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def render_items(self, items_to_render):
        self.clear_layout()
        
        self.lbl_stats.setText(f"Showing {len(items_to_render)} models")
        self.lbl_stats.setStyleSheet("background: none;")
        
        # Sort alphabetically by name
        items_to_render.sort(key=lambda x: x[1].get("name", ""))
        
        # Render max 150 items to avoid UI freeze. 
        # In a real app we'd use pagination or dynamic loading, but for a local desktop app 150 is fine.
        max_render = 150
        for cat, item in items_to_render[:max_render]:
            widget = CatalogItemWidget(item, cat)
            self.items_layout.addWidget(widget)
            
        if len(items_to_render) > max_render:
            warning_lbl = QtWidgets.QLabel(f"... and {len(items_to_render) - max_render} more. Refine search to see them.")
            warning_lbl.setStyleSheet("color: #E84545; font-weight: bold;")
            warning_lbl.setAlignment(QtCore.Qt.AlignCenter)
            self.items_layout.addWidget(warning_lbl)
