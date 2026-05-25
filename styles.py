DARK_THEME = """
QMainWindow {
    background-color: #121212;
}

QWidget {
    background-color: #121212;
    color: #E0E0E0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 10pt;
}

/* Menu Bar */
QMenuBar {
    background-color: #1E1E1E;
    border-bottom: 1px solid #333;
    padding: 2px;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #333;
    border-radius: 4px;
}

QMenu {
    background-color: #1E1E1E;
    border: 1px solid #333;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #00ADB5;
    color: #FFFFFF;
}

/* Buttons */
QPushButton {
    background-color: #222831;
    border: 1px solid #393E46;
    border-radius: 6px;
    padding: 8px 16px;
    color: #EEEEEE;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #393E46;
    border-color: #00ADB5;
}

QPushButton:pressed {
    background-color: #00ADB5;
    border-color: #00ADB5;
}

QPushButton:disabled {
    color: #555;
    background-color: #1A1A1A;
    border-color: #222;
}

/* Cards (MetricCard) */
QFrame#MetricCard {
    background-color: #1E1E1E;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 10px;
}

QFrame#MetricCard:hover {
    border: 1px solid #00ADB5;
}

/* Labels */
QLabel#Title {
    color: #999;
    text-transform: uppercase;
    font-size: 9pt;
    font-weight: normal;
    letter-spacing: 1px;
    background: transparent;
}

QLabel#Value, QLabel#RefValue, QLabel#TargetValue {
    color: #FFFFFF;
    font-size: 14pt;
    font-weight: bold;
    background: transparent;
}

QLabel#Delta {
    font-size: 10pt;
    font-weight: bold;
    background: transparent;
}

/* Status Bar */
QStatusBar {
    background-color: #1E1E1E;
    border-top: 1px solid #333;
    color: #888;
}

/* Combo Boxes */
QComboBox {
    background-color: #222831;
    border: 1px solid #393E46;
    border-radius: 4px;
    padding: 4px 8px;
    color: #EEEEEE;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #1E1E1E;
    border: 1px solid #333;
    selection-background-color: #00ADB5;
}

/* Tables */
QTableWidget {
    background-color: #1E1E1E;
    border: 1px solid #333;
    gridline-color: #333;
    border-radius: 4px;
}

QHeaderView::section {
    background-color: #252525;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #333;
    color: #AAA;
    font-weight: bold;
}

/* Progress Bar */
QProgressBar {
    background-color: #1A1A1A;
    border: 1px solid #333;
    border-radius: 8px;
    text-align: center;
    height: 16px;
}

QProgressBar::chunk {
    background-color: #00ADB5;
    border-radius: 7px;
}

/* List Widget (Library) */
QListWidget#LoopList {
    background-color: #1E1E1E;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 5px;
    outline: none;
}

QListWidget#LoopList::item {
    padding: 2px;
    border-radius: 4px;
    margin-bottom: 2px;
    background-color: transparent;
}

QListWidget#LoopList::item:hover, QListWidget#LoopList::item:selected {
    background-color: transparent;
    border: none;
    outline: none;
}

/* Accent Button (Target B) */
QPushButton#AccentButton {
    background-color: #FFAC41;
    color: #121212;
    font-size: 11pt;
}

QPushButton#AccentButton:hover {
    background-color: #008f95;
}

/* Home Screen Cards */
#HomeCard {
    background-color: #1E1E1E;
    border: 1px solid #333333;
    border-radius: 15px;
}
#HomeCard:hover {
    border-color: #00ADB5;
    background-color: #252525;
}

/* Toolbar Superior */
#TopToolbar {
    background-color: #121212;
    border-bottom: 1px solid #222222;
}

#HomeNavButton {
    background: transparent;
    border: none;
    color: #00ADB5;
    font-weight: bold;
    font-size: 14pt;
    letter-spacing: 1px;
    padding: 5px 15px;
}
#HomeNavButton:hover {
    color: white;
}

#AccentButton {
    background-color: #00ADB5;
    color: #EEEEEE;
    border-radius: 5px;
    font-weight: bold;
    padding: 8px 15px;
    border: none;
}
#AccentButton:hover {
    background-color: #008f95;
}
#AccentButton:pressed {
    background-color: #00767a;
}
"""
