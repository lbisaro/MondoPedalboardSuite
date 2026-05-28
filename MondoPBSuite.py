import os
import sys
import atexit
import traceback

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
from tone_matcher_widget import ToneMatcherWidget
from block_manager_widget import BlockManagerWidget

def resource_path(relative):
    """Resuelve rutas de recursos tanto en desarrollo como dentro del exe de PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)

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
        self.card_preset = NavCard("PRESET COMPARE", "fa6s.code-compare", 
                                 "Gestión de reamping y comparación A/B.", "preset", self.main_window)
        self.card_tone_matcher = NavCard("TONE MATCHER", "fa5s.music",
                                        "Ajuste automático de parámetros de Helix para igualar tonos.", "tone_matcher", self.main_window)
        self.card_block_mgr = NavCard("BLOCK MANAGER", "fa5s.cubes",
                                        "Visualiza y administra bloques de la Helix via USB.", "block_mgr", self.main_window)
        
        cards_layout.addStretch()
        cards_layout.addWidget(self.card_eq)
        cards_layout.addWidget(self.card_preset)
        cards_layout.addWidget(self.card_tone_matcher)
        cards_layout.addWidget(self.card_block_mgr)
        cards_layout.addStretch()
        
        layout.addLayout(cards_layout)
        layout.addStretch()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, analyzer):
        print("[INIT-UI] Constructor de MainWindow iniciado...")
        super().__init__()
        self.analyzer = analyzer
        self.conn_mgr = ConnectionManager(self.analyzer)
        
        self.setWindowTitle("Mondo PedalBoard Suite")
        self.resize(1280, 800)
        print("[INIT-UI] Cargando iconos de QtAwesome...")
        self.setWindowIcon(qta.icon('fa5s.wave-square', color='#00ADB5'))
        
        # --- UI Setup ---
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        print("[INIT-UI] Configurando barra de herramientas...")
        self.setup_toolbar()
        
        self.stack = QtWidgets.QStackedWidget()
        self.main_layout.addWidget(self.stack)
        
        print("[INIT-UI] Creando HomeWidget...")
        self.page_home = HomeWidget(self)
        print("[INIT-UI] Creando EQAnalyzerWidget...")
        self.page_eq = EQAnalyzerWidget(self.analyzer, self)
        print("[INIT-UI] Creando PresetCompareWidget...")
        self.page_preset = PresetCompareWidget(self.analyzer)
        print("[INIT-UI] Creando ToneMatcherWidget...")
        self.page_tone_matcher = ToneMatcherWidget(self.analyzer, self)
        print("[INIT-UI] Creando BlockManagerWidget...")
        self.page_block_mgr = BlockManagerWidget(self)
        
        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_eq)
        self.stack.addWidget(self.page_preset)
        self.stack.addWidget(self.page_tone_matcher)
        self.stack.addWidget(self.page_block_mgr)
        
        self.stack.setCurrentWidget(self.page_home)
        self.btn_home.setVisible(False) # Ocultar en el home al inicio
        self.setup_statusbar()
        self.auto_connect()

    def setup_toolbar(self):
        self.toolbar = QtWidgets.QWidget()
        self.toolbar.setFixedHeight(70)
        self.toolbar.setObjectName("TopToolbar")
        layout = QtWidgets.QHBoxLayout(self.toolbar)
        layout.setContentsMargins(15, 5, 15, 5)
        
        # Left side: Nav and Titles
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setSpacing(2)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(5)
        
        self.btn_home = QtWidgets.QPushButton(qta.icon('fa5s.home', color='#00ADB5'), "")
        self.btn_home.setObjectName("HomeNavButton")
        self.btn_home.setFixedSize(24, 24)
        self.btn_home.setStyleSheet("border: none; background: transparent;")
        self.btn_home.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_home.clicked.connect(self.go_home)
        
        self.lbl_app_title = QtWidgets.QLabel("MONDO PEDALBOARD")
        self.lbl_app_title.setStyleSheet("color: #00ADB5; font-weight: bold; font-size: 11pt;")
        
        top_row.addWidget(self.btn_home)
        top_row.addWidget(self.lbl_app_title)
        top_row.addStretch()
        
        self.lbl_module_title = QtWidgets.QLabel("")
        self.lbl_module_title.setStyleSheet("color: #00ADB5; font-weight: bold; font-size: 14pt; padding-left: 2px;")
        
        left_layout.addLayout(top_row)
        left_layout.addWidget(self.lbl_module_title)
        
        layout.addLayout(left_layout)
        
        layout.addStretch()
        
        # Botón de estado USB Helix
        self.usb_btn = QtWidgets.QPushButton(" USB ")
        self.usb_btn.setObjectName("UsbStatusButton")
        self.set_usb_disconnected()
        # Puedes conectarlo a una acción si quieres reconectar manualmente
        layout.addWidget(self.usb_btn)
        
        # Botón de conexión de Audio
        self.conn_btn = QtWidgets.QPushButton("")
        self.set_btn_disconnected()
        self.conn_btn.setObjectName("ConnectionButton")
        self.conn_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.conn_btn)
        self.main_layout.addWidget(self.toolbar)

    def set_usb_disconnected(self):
        self.usb_btn.setIcon(qta.icon('fa5b.usb', color='#888888'))
        self.usb_btn.setStyleSheet("""
            QPushButton#UsbStatusButton {
                background-color: #222;
                border: 1px solid #444;
                border-radius: 15px;
                color: #888888;
                font-size: 8pt;
                font-weight: bold;
                padding: 4px 12px;
            }
        """)

    def set_usb_connected(self):
        self.usb_btn.setIcon(qta.icon('fa5b.usb', color='#00ADB5'))
        self.usb_btn.setStyleSheet("""
            QPushButton#UsbStatusButton {
                background-color: rgba(0, 173, 181, 0.1);
                border: 1px solid #00ADB5;
                border-radius: 15px;
                color: #00ADB5;
                font-size: 8pt;
                font-weight: bold;
                padding: 4px 12px;
            }
        """)

    def set_usb_interacting(self):
        self.usb_btn.setIcon(qta.icon('fa5s.sync-alt', color='#4CAF50', animation=qta.Spin(self.usb_btn)))
        self.usb_btn.setStyleSheet("""
            QPushButton#UsbStatusButton {
                background-color: rgba(76, 175, 80, 0.1);
                border: 1px solid #4CAF50;
                border-radius: 15px;
                color: #4CAF50;
                font-size: 8pt;
                font-weight: bold;
                padding: 4px 12px;
            }
        """)

    def go_home(self):
        self.stop_audio()
        self.stack.setCurrentWidget(self.page_home)
        self.btn_home.setVisible(False)
        self.lbl_module_title.setText("")

    def navigate_to(self, page_name):
        if page_name == "eq": 
            self.stack.setCurrentWidget(self.page_eq)
            self.lbl_module_title.setText("EQ ANALIZER")
        elif page_name == "preset": 
            self.stack.setCurrentWidget(self.page_preset)
            self.lbl_module_title.setText("PRESET COMPARER")
        elif page_name == "tone_matcher": 
            self.stack.setCurrentWidget(self.page_tone_matcher)
            self.lbl_module_title.setText("TONE MATCHER")
        elif page_name == "block_mgr": 
            self.stack.setCurrentWidget(self.page_block_mgr)
            self.lbl_module_title.setText("BLOCK MANAGER")
            
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
        print(f"[AUDIO] Iniciando conexión con dispositivo desde MainWindow...")
        success, message = self.conn_mgr.start_audio(settings)
        if success:
            print("[AUDIO] Conexión establecida y stream de audio iniciado.")
            self.set_btn_connected(settings)
            self.statusBar().showMessage(f"Audio activo: {settings['device_name']}")
        else:
            print(f"[AUDIO] Error al iniciar stream de audio: {message}")
            self.set_btn_disconnected()
            QtWidgets.QMessageBox.critical(self, "Error de Audio", f"No se pudo iniciar el audio:\n{message}")

    def stop_audio(self):
        self.conn_mgr.stop_audio()
        self.set_btn_disconnected()
        self.statusBar().showMessage("Audio detenido")

    def auto_connect(self):
        print("[INIT] Comprobando conexión guardada para auto-connect...")
        settings = self.conn_mgr.load_settings()
        if "connection" in settings:
            print(f"[INIT] Conexión guardada detectada: {settings['connection'].get('device_name')}. Conectando...")
            self.start_audio(settings["connection"])
        else:
            print("[INIT] No hay conexión guardada para auto-connect.")

    def load_settings(self):
        return self.conn_mgr.load_settings()

    def save_settings(self, settings):
        self.conn_mgr.save_settings(settings)

def _emergency_stop(conn_mgr):
    """Cierre de emergencia del stream de audio. Se llama en crash o salida inesperada."""
    try:
        conn_mgr.stop_audio()
    except Exception:
        pass

class LoggerRedirector:
    def __init__(self, filepath, terminal):
        self.terminal = terminal
        self.log = open(filepath, "w", encoding="utf-8")

    def write(self, message):
        if self.terminal:
            self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        if self.terminal:
            self.terminal.flush()
        self.log.flush()

def main():
    log_path = "app_terminal.log"
    sys.stdout = LoggerRedirector(log_path, sys.stdout)
    sys.stderr = LoggerRedirector(log_path, sys.stderr)

    print("[INIT] Iniciando QApplication...")
    app = QtWidgets.QApplication(sys.argv)
    print("[INIT] Aplicando hoja de estilo DARK_THEME...")
    app.setStyleSheet(DARK_THEME)

    # --- Splash screen -------------------------------------------------------
    splash = None
    logo_path = resource_path(os.path.join('docs', 'MondoPBSuite_Logo.png'))
    if os.path.exists(logo_path):
        print("[INIT] Mostrando Splash Screen...")
        splash_pix = QtGui.QPixmap(logo_path)
        splash = QtWidgets.QSplashScreen(splash_pix, QtCore.Qt.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()
    # -------------------------------------------------------------------------
    print("[INIT] Creando instancia de AudioAnalyzer...")
    analyzer = AudioAnalyzer()
    print("[INIT] Creando MainWindow...")
    window = MainWindow(analyzer)

    # --- Capa 1: cierre limpio al salir normalmente ---
    app.aboutToQuit.connect(window.conn_mgr.stop_audio)

    # --- Capa 2: atexit garantiza el cierre aunque el event loop explote ---
    atexit.register(_emergency_stop, window.conn_mgr)

    # --- Capa 3: capturar excepciones no manejadas para cerrar el stream ---
    _original_excepthook = sys.excepthook
    def _excepthook(exc_type, exc_value, exc_tb):
        _emergency_stop(window.conn_mgr)
        # Mostrar el error al usuario antes de salir
        try:
            msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            QtWidgets.QMessageBox.critical(
                None,
                "Error inesperado",
                f"Ocurrio un error. El audio fue cerrado para proteger el dispositivo.\n\n{msg[:800]}"
            )
        except Exception:
            pass
        _original_excepthook(exc_type, exc_value, exc_tb)
    sys.excepthook = _excepthook

    print("[INIT] Mostrando ventana principal y cerrando Splash...")
    window.show()
    if splash:
        splash.finish(window)   # Cierra el splash cuando la ventana principal está lista
    print("[INIT] Iniciando event loop de Qt. Listo.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
