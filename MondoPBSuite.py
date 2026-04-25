import os
import sys

# Habilitar soporte ASIO (DEBE ESTAR ANTES DE IMPORTAR SOUNDDEVICE)
os.environ['SD_ENABLE_ASIO'] = '1'
# Forzar a pyqtgraph a usar PySide6
os.environ['QT_API'] = 'pyside6'

import json
import numpy as np
import sounddevice as sd
from PySide6 import QtCore, QtWidgets, QtGui
import qtawesome as qta

# Importar estilos y módulos locales
from styles import DARK_THEME
from eq_analyzer_widget import AudioAnalyzer, EQAnalyzerWidget, SAMPLE_RATE, BLOCK_SIZE
from preset_compare_widget import PresetCompareWidget
from device_connection import AudioDeviceDialog, ConnectionManager

class NavCard(QtWidgets.QFrame):
    """Tarjeta interactiva para la pantalla de inicio."""
    def __init__(self, title, icon_name, desc, target, main_window):
        super().__init__()
        self.target = target
        self.main_window = main_window
        self.setFixedSize(300, 250)
        self.setObjectName("HomeCard")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 30)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        
        icon_lbl = QtWidgets.QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color='#00ADB5').pixmap(64, 64))
        icon_lbl.setAlignment(QtCore.Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")
        
        title_lbl = QtWidgets.QLabel(title)
        title_lbl.setStyleSheet("font-size: 16pt; font-weight: bold; color: white; margin-top: 10px; background: transparent;")
        title_lbl.setAlignment(QtCore.Qt.AlignCenter)
        
        desc_lbl = QtWidgets.QLabel(desc)
        desc_lbl.setStyleSheet("color: #888; font-size: 10pt; background: transparent;")
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(QtCore.Qt.AlignCenter)
        
        layout.addWidget(icon_lbl)
        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)
        layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.main_window.navigate_to(self.target)
        super().mousePressEvent(event)

class HomeWidget(QtWidgets.QWidget):
    """Pantalla principal de bienvenida con acceso a los módulos."""
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setSpacing(40)
        
        # Título
        title = QtWidgets.QLabel("MONDO PEDALBOARD SUITE")
        title.setStyleSheet("font-size: 28pt; font-weight: bold; color: #00ADB5; letter-spacing: 4px; background: transparent;")
        layout.addWidget(title, 0, QtCore.Qt.AlignCenter)
        
        subtitle = QtWidgets.QLabel("Selecciona una herramienta para comenzar")
        subtitle.setStyleSheet("font-size: 12pt; color: #888; background: transparent;")
        layout.addWidget(subtitle, 0, QtCore.Qt.AlignCenter)
        
        # Grid de Tarjetas
        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(30)
        
        self.card_eq = NavCard("EQ ANALYZER", "fa5s.wave-square", 
                                "Análisis en tiempo real y Match EQ.", "eq", self.main_window)
        self.card_preset = NavCard("PRESET COMPARE", "fa5s.redo-alt", 
                                 "Gestión de reamping y comparación A/B.", "preset", self.main_window)
        
        cards_layout.addStretch()
        cards_layout.addWidget(self.card_eq)
        cards_layout.addWidget(self.card_preset)
        cards_layout.addStretch()
        
        layout.addLayout(cards_layout)
        layout.addStretch()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, analyzer):
        super().__init__()
        self.analyzer = analyzer
        self.conn_mgr = ConnectionManager(self.analyzer)
        
        self.setWindowTitle("Mondo PedalBoard Suite v1.0")
        self.resize(1280, 800)
        self.setWindowIcon(qta.icon('fa5s.wave-square', color='#00ADB5'))
        
        # --- UI Setup ---
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.setup_toolbar()
        
        self.stack = QtWidgets.QStackedWidget()
        self.main_layout.addWidget(self.stack)
        
        self.page_home = HomeWidget(self)
        self.page_eq = EQAnalyzerWidget(self.analyzer, self)
        self.page_preset = PresetCompareWidget(self.analyzer)
        
        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_eq)
        self.stack.addWidget(self.page_preset)
        
        self.stack.setCurrentWidget(self.page_home)
        self.btn_home.setVisible(False) # Ocultar en el home al inicio
        self.setup_statusbar()
        self.auto_connect()

    def setup_toolbar(self):
        self.toolbar = QtWidgets.QWidget()
        self.toolbar.setFixedHeight(50)
        self.toolbar.setObjectName("TopToolbar")
        layout = QtWidgets.QHBoxLayout(self.toolbar)
        layout.setContentsMargins(15, 0, 15, 0)
        
        self.btn_home = QtWidgets.QPushButton(qta.icon('fa5s.home', color='#00ADB5'), " MONDO PEDALBOARD")
        self.btn_home.setObjectName("HomeNavButton")
        self.btn_home.clicked.connect(self.go_home)
        layout.addWidget(self.btn_home)
        
        layout.addStretch()
        self.conn_btn = QtWidgets.QPushButton("")
        self.set_btn_disconnected()
        self.conn_btn.setObjectName("ConnectionButton")
        self.conn_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.conn_btn)
        self.main_layout.addWidget(self.toolbar)

    def go_home(self):
        self.stop_audio()
        self.stack.setCurrentWidget(self.page_home)
        self.btn_home.setVisible(False)

    def navigate_to(self, page_name):
        if page_name == "eq": self.stack.setCurrentWidget(self.page_eq)
        elif page_name == "preset": self.stack.setCurrentWidget(self.page_preset)
        self.btn_home.setVisible(True)

    def setup_statusbar(self):
        self.statusBar().showMessage("Listo")

    def set_btn_disconnected(self):
        self.conn_btn.setText(" Desconectado ")
        self.conn_btn.setIcon(qta.icon('fa5s.volume-mute', color='#ff4444'))
        self.conn_btn.setStyleSheet("""
            QPushButton#ConnectionButton {
                background-color: #222;
                border: 1px solid #444;
                border-radius: 15px;
                color: #888;
                font-size: 8pt;
                padding: 4px 12px;
            }
            QPushButton#ConnectionButton:hover {
                border-color: #ff4444;
                background-color: #2a2a2a;
            }
        """)

    def set_btn_connected(self, settings):
        driver = settings.get('driver_name', 'ASIO')
        device = settings.get('device_name', 'Device')
        ch_in = settings.get('in_channel', '?')
        ch_out = settings.get('out_channel', '?')
        
        text = f" {driver} | {device} | IN: {ch_in} OUT: {ch_out} "
        self.conn_btn.setText(text)
        self.conn_btn.setIcon(qta.icon('fa5s.volume-up', color='#00ADB5'))
        self.conn_btn.setStyleSheet("""
            QPushButton#ConnectionButton {
                background-color: rgba(0, 173, 181, 0.1);
                border: 1px solid #00ADB5;
                border-radius: 15px;
                color: #00ADB5;
                font-size: 8pt;
                font-weight: bold;
                padding: 4px 12px;
            }
            QPushButton#ConnectionButton:hover {
                background-color: rgba(0, 173, 181, 0.2);
            }
        """)

    def set_btn_capturing(self, settings):
        driver = settings.get('driver_name', 'ASIO')
        device = settings.get('device_name', 'Device')
        ch_in = settings.get('in_channel', '?')
        ch_out = settings.get('out_channel', '?')
        
        text = f" REPRODUCIENDO: {driver} | {device} | IN: {ch_in} OUT: {ch_out} "
        self.conn_btn.setText(text)
        self.conn_btn.setIcon(qta.icon('fa5s.sync-alt', color='#FFAC41', animation=qta.Spin(self.conn_btn)))
        self.conn_btn.setStyleSheet("""
            QPushButton#ConnectionButton {
                background-color: rgba(255, 172, 65, 0.1);
                border: 1px solid #FFAC41;
                border-radius: 15px;
                color: #FFAC41;
                font-size: 8pt;
                font-weight: bold;
                padding: 4px 12px;
            }
        """)

    def toggle_connection(self):
        self.open_audio_dialog()

    def open_audio_dialog(self):
        dialog = AudioDeviceDialog(self)
        
        # Restaurar ajustes actuales en el diálogo si existen
        settings = self.conn_mgr.load_settings()
        if "connection" in settings:
            dialog.restore_settings(settings["connection"])
            
        if dialog.exec():
            if dialog.requested_disconnect:
                self.stop_audio()
                s = self.conn_mgr.load_settings()
                if "connection" in s:
                    del s["connection"]
                    self.conn_mgr.save_settings(s)
            else:
                new_settings = dialog.get_settings()
                s = self.conn_mgr.load_settings()
                s["connection"] = new_settings
                self.conn_mgr.save_settings(s)
                self.start_audio(new_settings)

    def start_audio(self, settings):
        success, message = self.conn_mgr.start_audio(settings)
        if success:
            self.set_btn_connected(settings)
            self.statusBar().showMessage(f"Audio activo: {settings['device_name']}")
        else:
            self.set_btn_disconnected()
            QtWidgets.QMessageBox.critical(self, "Error de Audio", f"No se pudo iniciar el audio:\n{message}")

    def stop_audio(self):
        self.conn_mgr.stop_audio()
        self.set_btn_disconnected()
        self.statusBar().showMessage("Audio detenido")

    def auto_connect(self):
        settings = self.conn_mgr.load_settings()
        if "connection" in settings:
            self.start_audio(settings["connection"])

    def load_settings(self):
        return self.conn_mgr.load_settings()

    def save_settings(self, settings):
        self.conn_mgr.save_settings(settings)

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME)
    
    analyzer = AudioAnalyzer()
    window = MainWindow(analyzer)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
