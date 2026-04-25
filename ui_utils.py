import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets, QtGui
import numpy as np

class FreqAxisItem(pg.AxisItem):
    def logTickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            freq = 10 ** v
            if freq >= 1000:
                strings.append(f"{freq/1000:g}k")
            else:
                strings.append(f"{freq:g}")
        return strings

class FrequencyPlotWidget(pg.PlotWidget):
    """
    Widget especializado para mostrar espectros de audio (dB vs Frecuencia).
    Incluye rastreo de mouse, estética unificada y configuración logarítmica.
    """
    def __init__(self, parent=None, title="", y_range=(-30, 30), **kwargs):
        # Configurar el eje de frecuencia antes de inicializar el widget
        self.freq_axis = FreqAxisItem(orientation='bottom')
        
        # Inicializar atributo para evitar errores en resizeEvent prematuros
        self.cursor_label = None
        
        super().__init__(parent=parent, axisItems={'bottom': self.freq_axis}, **kwargs)
        
        self.setBackground('#121212')
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setLogMode(x=True, y=False)
        self.setYRange(y_range[0], y_range[1], padding=0)
        self.setXRange(np.log10(20), np.log10(20000), padding=0)
        
        self.setLabel("left", "dB", color="#BBBBBB", size="11pt")
        self.setLabel("bottom", "Hz", color="#BBBBBB", size="11pt")
        
        # Crosshair Lines
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color='#333333', width=1, style=QtCore.Qt.DashLine))
        self.hLine = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(color='#333333', width=1, style=QtCore.Qt.DashLine))
        self.addItem(self.vLine, ignoreBounds=True)
        self.addItem(self.hLine, ignoreBounds=True)
        
        # Cursor Label
        self.cursor_label = QtWidgets.QLabel("", self)
        self.cursor_label.setStyleSheet(
            "color: #00ADB5; font-family: 'Consolas', 'Monospace'; font-size: 10pt; "
            "background: transparent; padding: 2px 5px;"
        )
        self.cursor_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
        self.cursor_label.hide()
        
        # Signal Proxy para manejo de mouse
        self.proxy = pg.SignalProxy(self.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)
        self.scene().sigMouseClicked.connect(self.plotClicked)
        
        # Elementos de medición delta
        self.measure_state = 0 # 0: idle, 1: start set, 2: end set
        self.measure_line_a = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#FFAC41', width=1, style=QtCore.Qt.SolidLine))
        self.measure_line_b = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#FF4B2B', width=1, style=QtCore.Qt.SolidLine))
        
        # Usamos un QLabel dentro de un ProxyWidget para tener soporte total de CSS (bordes redondeados)
        self.measure_widget = QtWidgets.QLabel()
        self.measure_proxy = QtWidgets.QGraphicsProxyWidget()
        self.measure_proxy.setWidget(self.measure_widget)
        # IMPORTANTE: Hacer que ignore la transformación de los ejes para que no se agrande
        self.measure_proxy.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations)
        # Asegurar que esté en primer plano
        self.measure_proxy.setZValue(1000)
        
        self.measure_line_a.hide()
        self.measure_line_b.hide()
        self.measure_proxy.hide()
        
        self.addItem(self.measure_line_a)
        self.addItem(self.measure_line_b)
        self.addItem(self.measure_proxy)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_cursor_label()

    def _reposition_cursor_label(self):
        if self.cursor_label is not None:
            label_w = max(self.cursor_label.sizeHint().width(), 160)
            label_h = self.cursor_label.sizeHint().height()
            # Posicionar en la esquina inferior derecha, reduciendo el margen para que baje
            self.cursor_label.setGeometry(self.width() - label_w - 5, self.height() - label_h - 2, label_w, label_h)

    def mouseMoved(self, evt):
        pos = evt[0]
        # Usar el bounding rect del ViewBox (zona de dibujo real)
        if self.plotItem.vb.sceneBoundingRect().contains(pos):
            mousePoint = self.plotItem.vb.mapSceneToView(pos)
            x_log = mousePoint.x()
            y_db = mousePoint.y()
            freq = 10 ** x_log
            
            # Limitar a rangos audibles
            if freq < 10: freq = 10
            if freq > 22000: freq = 22000
            
            self.vLine.setPos(x_log)
            self.hLine.setPos(y_db)
            self.vLine.show()
            self.hLine.show()
            
            if freq >= 1000: freq_str = f"{freq/1000:.2f} kHz"
            else: freq_str = f"{freq:.1f} Hz"
            
            self.cursor_label.setText(f"{freq_str}  {y_db:+.1f} dB")
            self.cursor_label.show()
            self._reposition_cursor_label()
        else:
            self.cursor_label.hide()
            self.vLine.hide() # Opcional: Ocultar también las líneas de cruz
            self.hLine.hide()

    def plotClicked(self, evt):
        if evt.button() != QtCore.Qt.LeftButton:
            return
            
        pos = evt.scenePos()
        if self.plotItem.vb.sceneBoundingRect().contains(pos):
            mousePoint = self.plotItem.vb.mapSceneToView(pos)
            y_db = mousePoint.y()
            x_log = mousePoint.x()
            
            if self.measure_state == 0:
                # Primer click: Punto A
                self.measure_line_a.setPos(y_db)
                self.measure_line_a.show()
                self.val_a = y_db
                self.measure_state = 1
            elif self.measure_state == 1:
                # Segundo click: Punto B e informar delta
                self.measure_line_b.setPos(y_db)
                self.measure_line_b.show()
                delta = y_db - self.val_a
                
                # Estilo dinámico basado en el resultado
                color = "#00FFAB" if delta >= 0 else "#FF4B2B"
                self.measure_widget.setStyleSheet(f"""
                    background-color: #121212;
                    color: {color};
                    border: 1px solid {color};
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-family: 'Consolas';
                    font-size: 10pt;
                """)
                self.measure_widget.setText(f" Δ: {delta:+.1f} dB ")
                
                # Volver a usar coordenadas de datos (vista) directamente.
                # Al tener el flag ItemIgnoresTransformations, se posicionará bien pero no se escalará.
                self.measure_proxy.setPos(x_log, (y_db + self.val_a) / 2)
                self.measure_proxy.show()
                self.measure_state = 2
            else:
                # Tercer click: Limpiar
                self.measure_line_a.hide()
                self.measure_line_b.hide()
                self.measure_proxy.hide()
                self.measure_state = 0

    def auto_scale(self, padding=5):
        """Ajusta el rango Y para mostrar todas las curvas con un margen."""
        ymin, ymax = 0, -100
        has_data = False
        
        for item in self.plotItem.items:
            if isinstance(item, pg.PlotDataItem):
                _, y = item.getData()
                if y is not None and len(y) > 0:
                    # Filtrar posibles -inf o valores absurdos
                    valid_y = y[np.isfinite(y)]
                    if len(valid_y) > 0:
                        ymin = min(ymin, np.min(valid_y))
                        ymax = max(ymax, np.max(valid_y))
                        has_data = True
        
        if has_data:
            self.setYRange(ymin - padding, ymax + padding, padding=0)

    def add_curve(self, name, color='#00ADB5', width=2, style=QtCore.Qt.SolidLine):
        return self.plot(pen=pg.mkPen(color=color, width=width, style=style), name=name)

def apply_smoothing(freqs, magnitude_db, fraction):
    """
    Aplica suavizado por octavas a una curva de magnitud (dB).
    fraction: denominador de la octava (ej: 3 para 1/3, 6 para 1/6).
    """
    if fraction <= 0:
        return magnitude_db
        
    data_linear = 10 ** (magnitude_db / 20.0)
    smoothed_linear = np.zeros_like(data_linear)
    mult = 2 ** (1.0 / (2.0 * fraction))
    
    left_idx = 0
    right_idx = 0
    n = len(freqs)
    
    for i in range(n):
        f_lower = freqs[i] / mult
        f_upper = freqs[i] * mult
        
        while left_idx < n and freqs[left_idx] < f_lower:
            left_idx += 1
        while right_idx < n and freqs[right_idx] <= f_upper:
            right_idx += 1
            
        if right_idx > left_idx:
            smoothed_linear[i] = np.mean(data_linear[left_idx:right_idx])
        else:
            smoothed_linear[i] = data_linear[i]
            
    return 20 * np.log10(smoothed_linear + 1e-12)

def sanitize_filename(name):
    """
    Limpia un nombre de archivo para evitar caracteres inválidos en Windows y Linux.
    """
    import re
    # Caracteres prohibidos en Windows: < > : " / \ | ? * 
    # y caracteres de control (0-31)
    # También evitamos espacios al final o puntos al final (problemas en Windows)
    s = str(name).strip().replace(' ', '_')
    s = re.sub(r'(?u)[^-\w.]', '', s)
    if not s:
        s = "unnamed"
    return s
