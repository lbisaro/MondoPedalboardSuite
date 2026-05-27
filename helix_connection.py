import logging
import queue
import threading
import time
import random
import usb.core
import usb.util
import urllib.request
import json
import os

# Configuración del logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("HelixConnection")

DEVICE_MAP = {
    0x4241: "Helix Floor",
    0x4242: "Helix Rack",
    0x4244: "Helix LT (Early Firmware)",
    0x424a: "Helix LT",
    0x4246: "HX Stomp",
    0x4253: "HX Stomp XL",
    0x424b: "POD Go",
    0x5055: "POD Go / Helix Effects (Alt)"
}

class HelixConnection:
    def __init__(self, custom_config_url="https://helix.bisaro.ar/helix_api.php", cache_file="helix_config_cache.json"):
        self.dev = None
        self.product_id = 0
        self.interface = 0
        self.endpoint_out = 0x01
        self.endpoint_in = 0x81
        
        self.event_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.reader_thread = None
        
        self.x1_counter = 0x02
        self.x2_counter = 0x02
        self.x80_counter = 0x02
        self.preset_data_double_cnt = [0x1e, 0x00]
        self.request_preset_session_id = 0xf4
        self.write_lock = threading.RLock()
        self.handshake_done = False
        self.keep_alive_thread = None
        self.last_ed03_echo_model = None
        self.capture_model_echoes = True
        
        # Contadores para escritura en vivo (Live Write)
        self.editor_ed03_double = 0x64e7
        self.preset_dump_ack_ctr = 0x119d
        self.ed03_cmd_type = 0x01
        self.preset_last_ack_double = [0, 0]
        self.live_write_ctr = 0x6cbd
        self.live_write_yy = 0x17
        
        self.last_x1_counter = 0x04
        self.session_no = 0x1a
        self.active_setlist_idx = -1
        self.active_preset_idx_in_setlist = -1
        self.active_preset_idx = -1
        self.preset_name = ""
        self.setlist_names = [
            "FACTORY 1",
            "FACTORY 2",
            "USER 1",
            "USER 2",
            "USER 3",
            "USER 4",
            "USER 5",
            "TEMPLATES"
        ]
        
        self.custom_config_url = custom_config_url
        self.cache_file = cache_file
        
        # Buffer para acumular datos del nombre del preset
        self.preset_name_buffer = bytearray()
        self.name_completed_event = threading.Event()

        # Intentar cargar nombres de setlists personalizados
        self.load_custom_setlists()

    def load_custom_setlists(self):
        """Intenta cargar las setlists personalizadas desde la nube o el caché local."""
        loaded = False
        data = None
        
        # 1. Intentar cargar desde la nube
        try:
            log.info(f"Intentando descargar nombres de setlists desde {self.custom_config_url}...")
            req = urllib.request.Request(self.custom_config_url, headers={'User-Agent': 'HelixConnection/1.0'})
            with urllib.request.urlopen(req, timeout=1.5) as response:
                content = response.read().decode('utf-8')
                data = json.loads(content)
                loaded = True
                log.info("Nombres de setlists descargados exitosamente desde la nube.")
                
                # Guardar en caché local
                try:
                    with open(self.cache_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    log.info(f"Caché de configuración guardado localmente en {self.cache_file}")
                except Exception as cache_err:
                    log.warning(f"No se pudo guardar el caché local: {cache_err}")
        except Exception as net_err:
            log.warning(f"Error al conectar con la nube ({net_err}). Buscando caché local...")
            
        # 2. Si falló la nube, intentar cargar desde caché local
        if not loaded:
            if os.path.exists(self.cache_file):
                try:
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    loaded = True
                    log.info(f"Configuración cargada desde el caché local: {self.cache_file}")
                except Exception as file_err:
                    log.error(f"Error al leer el archivo de caché local: {file_err}")
            else:
                log.info("No se encontró ningún archivo de caché local.")
                
        # 3. Si se cargó configuración, mapear nombres de setlists
        if loaded and data and isinstance(data, dict):
            custom_setlists = data.get("setlists")
            if isinstance(custom_setlists, dict):
                for sid_str, sl_data in custom_setlists.items():
                    try:
                        sid = int(sid_str)
                        if 0 <= sid < len(self.setlist_names):
                            name = sl_data.get("name")
                            if name:
                                self.setlist_names[sid] = name
                                log.info(f"Setlist #{sid + 1} renombrada dinámicamente a: '{name}'")
                    except (ValueError, TypeError):
                        pass

    def find_device(self):
        """Busca cualquier dispositivo Line 6 en el bus USB."""
        log.info("Buscando pedalera Line 6 en el bus USB...")
        try:
            import libusb_package
            backend = libusb_package.get_libusb1_backend()
        except ImportError:
            backend = None
        devices = list(usb.core.find(find_all=True, idVendor=0x0E41, backend=backend))
        if not devices:
            log.warning("No se encontró ningún dispositivo Line 6 (VID: 0x0E41).")
            return None
        
        # Seleccionamos el primer dispositivo compatible
        for d in devices:
            dev_name = DEVICE_MAP.get(d.idProduct, f"Dispositivo Line 6 Desconocido (PID: 0x{d.idProduct:04x})")
            log.info(f"Dispositivo detectado: {dev_name} (VID: 0x0E41, PID: 0x{d.idProduct:04x})")
            return d
        return None

    def connect(self):
        """Establece conexión USB, reclama la interfaz 0 e inicia el lector asíncrono.

        Es robusto ante sesiones USB residuales dejadas por procesos terminados
        abruptamente: intenta liberar la interfaz antes de reclamarla y reintenta
        el reset USB hasta 3 veces si el dispositivo tarda en estar disponible.
        """
        self.dev = self.find_device()
        if self.dev is None:
            return False, "No se encontró el dispositivo Line 6 en el puerto USB."
        self.product_id = self.dev.idProduct

        # --- Liberar interfaz residual si quedó reclamada por un proceso anterior ---
        log.info("Reclamando interfaz 0 (control de canal nativo)...")
        try:
            if self.dev.is_kernel_driver_active(self.interface):
                log.info("Desacoplando driver del kernel...")
                self.dev.detach_kernel_driver(self.interface)
        except NotImplementedError:
            pass
        except usb.core.USBError as e:
            log.warning(f"No se pudo verificar o desacoplar driver de kernel: {e}")

        # Intentar liberar la interfaz antes de reclamarla para limpiar
        # sesiones huérfanas de ejecuciones anteriores.
        try:
            usb.util.release_interface(self.dev, self.interface)
            log.info("Interfaz residual liberada antes de reclamar.")
            time.sleep(0.2)
        except Exception:
            pass  # Normal si nadie la tenía reclamada

        try:
            usb.util.claim_interface(self.dev, self.interface)
            log.info("Interfaz 0 reclamada con éxito.")
        except usb.core.USBError as e:
            msg = f"No se pudo reclamar la interfaz (¿HX Edit abierto o dispositivo en uso?): {e}"
            log.error(msg)
            self.dev = None
            return False, msg

        # Vaciar datos residuales en el endpoint de entrada
        self.flush_endpoint()

        # Iniciar hilo lector
        self.stop_event.clear()
        self.reader_thread = threading.Thread(
            target=self._reader_loop, name="HelixReaderThread", daemon=True
        )
        self.reader_thread.start()
        log.info("Hilo lector asíncrono iniciado.")
        
        return True, "Conectado exitosamente."

    def is_connected(self):
        """Devuelve True si la Helix parece estar conectada y el hilo de lectura está activo."""
        if not self.dev:
            return False
        if not self.reader_thread or not self.reader_thread.is_alive():
            return False
        return True


    def disconnect(self):
        """Detiene el lector y libera la interfaz USB."""
        log.info("Desconectando de la Helix...")
        
        if self.dev and self.handshake_done:
            # Enviar mensaje de teardown para liberar el Host Mode en la Helix
            try:
                teardown_msg_1 = [0x08, 0x00, 0x00, 0x18, 0xf0, 0x03, 0x02, 0x10, 0x00, 0x0d, 0x00, 0x02, 0x09, 0x02, 0x00, 0x00]
                teardown_msg_2 = [0x08, 0x00, 0x00, 0x18, 0x01, 0x10, 0xef, 0x03, 0x00, 0x1f, 0x00, 0x02, 0x07, 0x1f, 0x00, 0x00]
                
                self.write(teardown_msg_1)
                self.write(teardown_msg_2)
                import time
                time.sleep(0.3) # Permitir que el hilo lector capture las respuestas IN
                log.info("Mensajes de TearDown (Host Release) 1 y 2 enviados y procesados.")
            except Exception as e:
                log.warning(f"No se pudo enviar mensaje TearDown: {e}")

        self.stop_event.set()
        self.handshake_done = False
        
        if self.keep_alive_thread and self.keep_alive_thread.is_alive():
            self.keep_alive_thread.join(timeout=1.0)
            
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1.0)
            
        if self.dev:
            try:
                # Intenta limpiar los endpoints (equivalente a abort pipe)
                try:
                    self.dev.clear_halt(self.endpoint_in)
                    self.dev.clear_halt(self.endpoint_out)
                    log.info("Endpoints liberados (clear_halt).")
                except Exception as e:
                    pass
                
                usb.util.release_interface(self.dev, self.interface)
                usb.util.dispose_resources(self.dev)
                log.info("Interfaz 0 liberada y recursos de USB dispuestos.")
            except Exception as e:
                log.error(f"Error al liberar la interfaz: {e}")
                
            try:
                # Volver a acoplar driver del kernel si aplica
                self.dev.attach_kernel_driver(self.interface)
                log.info("Driver de kernel re-acoplado.")
            except Exception:
                pass
            self.dev = None

    def write(self, data):
        """Escribe datos en el Endpoint 0x01."""
        if not self.dev:
            raise RuntimeError("Dispositivo no conectado.")
        
        with self.write_lock:
            # Reemplazar contador automático "XX" según el canal
            data_to_send = list(data)
            if len(data_to_send) > 9 and data_to_send[9] == "XX":
                channel = data_to_send[4]
                if channel == 0x01:
                    data_to_send[9] = self.x1_counter
                    self.x1_counter = (self.x1_counter + 1) & 0xff
                elif channel == 0x02:
                    data_to_send[9] = self.x2_counter
                    self.x2_counter = (self.x2_counter + 1) & 0xff
                elif channel == 0x80:
                    data_to_send[9] = self.x80_counter
                    self.x80_counter = (self.x80_counter + 1) & 0xff

            # Guardar en log (opcionalmente silencioso para keep-alives)
            # log.debug(f"OUT: {[hex(x) for x in data_to_send]}")
            self.dev.write(self.endpoint_out, data_to_send, timeout=1000)

    def flush_endpoint(self):
        """Limpia datos en el búfer de entrada bulk."""
        try:
            while True:
                self.dev.read(self.endpoint_in, 512, timeout=50)
        except usb.core.USBError:
            pass

    def _reader_loop(self):
        """Bucle continuo del hilo lector para capturar y clasificar eventos del Endpoint 0x81."""
        while not self.stop_event.is_set():
            try:
                # Leer del endpoint de entrada
                data = self.dev.read(self.endpoint_in, 512, timeout=200)
                if len(data) >= 8:
                    offset = 0
                    while offset + 8 <= len(data):
                        payload_len = data[offset] + (data[offset + 1] << 8)
                        pkt_len = payload_len + 8
                        if offset + pkt_len > len(data):
                            break
                        pkt = data[offset : offset + pkt_len]
                        self._classify_and_queue(pkt)
                        offset += pkt_len
            except usb.core.USBError as e:
                # Manejar timeouts normales sin detener el bucle
                if e.backend_error_code == -7 or "timeout" in str(e).lower() or e.errno in (10060, 110):
                    continue
                else:
                    log.error(f"Error de lectura en bus USB: {e}")
                    self.event_queue.put(("error", e))
                    break
            except Exception as e:
                log.error(f"Error inesperado en hilo de lectura: {e}")
                self.event_queue.put(("error", e))
                break

    @staticmethod
    def my_byte_cmp(left, right, length):
        """Compara dos listas de bytes con soporte para comodines 'XX'."""
        if len(left) < length or len(right) < length:
            return False
        for i in range(length):
            if left[i] == 'XX' or right[i] == 'XX':
                continue
            if left[i] != right[i]:
                return False
        return True

    def _classify_and_queue(self, data):
        """Clasifica los paquetes según el protocolo nativo de Helix y responde a keep-alives post-handshake."""
        n = len(data)
        
        # Si el handshake ya terminó, respondemos keep-alives directamente en el hilo de lectura
        if self.handshake_done:
            # Keep-alive x1 enviado por la Helix
            if data[4] == 0xef and data[6] == 0x01 and data[11] in (0x10, 0x08):
                counter = data[9]
                ack = [
                    0x08, 0x00, 0x00, 0x18, 0x01, 0x10, 0xef, 0x03,
                    0x00, "XX", 0x00, 0x08,
                    0x38, (counter + 9) & 0xff, 0x00, 0x00
                ]
                try:
                    self.write(ack)
                except Exception as e:
                    log.warning(f"Error respondiendo ACK keep_alive_x1: {e}")
                return # No encolar para no saturar la cola

            # Keep-alive x2 enviado por la Helix
            elif data[4] == 0xf0 and data[6] == 0x02 and n >= 16 and data[11] == 0x04 and data[12] == 0x09 and data[13] == 0x02:
                ack = [
                    0x08, 0x00, 0x00, 0x18, 0x02, 0x10, 0xf0, 0x03,
                    0x00, "XX", 0x00, 0x08,
                    0x74, 0x77, 0x00, 0x00
                ]
                try:
                    self.write(ack)
                except Exception as e:
                    log.warning(f"Error respondiendo ACK keep_alive_x2: {e}")
                return # No encolar

            # Ignorar respuestas keep-alive de la Helix a nuestros keep-alives para no saturar la cola
            elif data[4] == 0xed and data[6] == 0x80 and data[11] == 0x10:
                return
            elif data[4] == 0xef and data[6] == 0x01 and data[11] == 0x10:
                return
            elif data[4] == 0xf0 and data[6] == 0x02 and data[11] == 0x10:
                return

        # Capture model echo
        if self.capture_model_echoes and len(data) >= 32 and len(data) < 100 and data[4] == 0xed and data[6] in (0x80, 0x03):
            if data[24] == 0x83 and data[25] == 0x66 and data[26] == 0xcd:
                payload = list(data[24:40])
                if len(payload) < 16:
                    payload += [0] * (16 - len(payload))
                if payload[3] == 0x03:
                    self.last_ed03_echo_model = payload
                    log.info(f"Captured model echo from device (payload): {[hex(x) for x in self.last_ed03_echo_model]}")
                else:
                    log.info(f"Ignored non-param-write model echo payload: {[hex(x) for x in payload]}")
                log.info(f"Captured model echo (full packet): {[hex(x) for x in list(data)]}")
                
                # Automatically ACK this model echo/message on channel 80 to prevent device lockup!
                ack = [
                    0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
                    0x00, "XX", 0x00, 0x08,
                    data[12], data[13], data[14], 0x00
                ]
                try:
                    self.write(ack)
                    log.info(f"Automatically ACK'd model echo on channel 80: session={hex(data[12])}, double={hex(data[13])},{hex(data[14])}")
                except Exception as e:
                    log.warning(f"Error sending automatic model echo ACK: {e}")

        # Si el handshake no ha terminado, o si es otro tipo de mensaje, lo clasificamos y encolamos
        # Keep-alive x1 (por si acaso se recibe durante el handshake)
        if data[4] == 0xef and data[6] == 0x01 and data[11] in (0x10, 0x08):
            self.event_queue.put(("keep_alive_x1", data[9]))
            
        # Keep-alive x80
        elif data[4] == 0xed and data[6] == 0x80 and data[11] in (0x10, 0x08):
            self.event_queue.put(("keep_alive_x80", (data[9], data[12])))
            
        # Respuesta del nombre del preset (comparación de firmas según helix_usb)
        elif n >= 39 and self.my_byte_cmp(data[23:], [0x0, 0x83, 0x66, 0xcd, "XX", "XX", 0x67, 0x0, 0x68, 0x86, 0x6b, 0xcd, 0x0, 0x0, 0x6c, 0xcd], 16):
            log.info("Putting preset_name_packet in event_queue")
            self.event_queue.put(("preset_name_packet", data))
            
        # Chunk de preset x80 (Contiene nombre o parámetros de presets)
        elif data[4] == 0xed and data[6] == 0x80 and data[1] == 0x01:
            log.info(f"Putting preset_chunk in event_queue (len={len(data)})")
            self.event_queue.put(("preset_chunk", data))
            
        # Cabecera de preset (Preset Header, n entre 55 y 75 bytes)
        elif data[4] == 0xed and data[6] == 0x80 and data[1] == 0x00 and 55 <= n <= 75:
            log.info(f"Putting preset_header in event_queue (len={len(data)})")
            self.event_queue.put(("preset_header", data))
            
        # Todo lo demás se trata como mensaje RAW
        else:
            log.info(f"Putting raw packet in event_queue (len={len(data)}, ch={data[4]}, sub={data[6]}, type={data[1]})")
            self.event_queue.put(("raw", data))

    def wait_for_event(self, event_type, condition=None, timeout=5.0):
        """Espera un evento específico de la cola de eventos mientras autogestiona ACKs de Keep-Alive."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.stop_event.is_set():
                raise InterruptedError("Operación cancelada por desconexión.")
            try:
                evt_type, data = self.event_queue.get(timeout=0.1)
                
                if evt_type == "error":
                    raise data
                    
                # Respuesta automática a Keep-alive x1 enviado por la Helix (como fallback)
                if evt_type == "keep_alive_x1":
                    counter = data
                    ack = [
                        0x08, 0x00, 0x00, 0x18, 0x01, 0x10, 0xef, 0x03,
                        0x00, "XX", 0x00, 0x08,
                        0x38, (counter + 9) & 0xff, 0x00, 0x00
                    ]
                    try:
                        self.write(ack)
                    except Exception as e:
                        log.warning(f"Error respondiendo fallback keep_alive_x1: {e}")
                    self.last_x1_counter = counter
                    continue
                    
                if evt_type == event_type:
                    if condition is None or condition(data):
                        return data
            except queue.Empty:
                continue
        raise TimeoutError(f"Se agotó el tiempo de espera ({timeout}s) aguardando el evento: {event_type}")

    def perform_handshake(self):
        """Ejecuta la secuencia exacta de saludo (handshake) descrita en el protocolo."""
        log.info("Iniciando secuencia de saludo (handshake) con la Helix...")
        
        # Limpiar cola
        while not self.event_queue.empty():
            self.event_queue.get_nowait()
            
        self.x1_counter = 0x02
        self.x2_counter = 0x02
        self.x80_counter = 0x02

        # 1. Init x1
        log.info("Handshake Paso 1: Enviar Init x1")
        self.write([0x0c,0x00,0x00,0x28,0x01,0x10,0xef,0x03,0x00,0x00,0x00,0x02,0x00,0x01,0x00,0x21,0x00,0x10,0x00,0x00])

        # 2. Esperar respuesta x1
        log.info("Handshake Paso 2: Esperar respuesta x1")
        self.wait_for_event("raw", lambda d: len(d) >= 10 and d[0] == 0x0c and d[4] == 0xef and d[6] == 0x01)

        # 3. ACK x1
        log.info("Handshake Paso 3: Enviar ACK x1")
        self.write([0x11,0x00,0x00,0x18,0x01,0x10,0xef,0x03,0x00,0x02,0x00,0x04,0x00,0x10,0x00,0x00,0x01,0x00,0x05,0x00,0x01,0x00,0x00,0x00,0x05,0x00,0x00,0x00])

        # 4. Esperar Reconfig
        log.info("Handshake Paso 4: Esperar Reconfiguración")
        self.wait_for_event("raw", lambda d: len(d) >= 14 and d[0] == 0x28 and d[4] == 0xef and d[12] == 0x09)

        # 5. Enviar ACKs de Reconfig
        log.info("Handshake Paso 5: Enviar ACKs de Reconfiguración")
        self.write([0x08,0x00,0x00,0x18,0x01,0x10,0xef,0x03,0x00,0x03,0x00,0x08,0x20,0x10,0x00,0x00])
        self.write([0x08,0x00,0x00,0x18,0x01,0x10,0xef,0x03,0x00,0x04,0x00,0x02,0x20,0x10,0x00,0x00])

        # 6. Init x80
        log.info("Handshake Paso 6: Enviar Init x80")
        self.write([0x0c,0x00,0x00,0x28,0x80,0x10,0xed,0x03,0x00,0x00,0x00,0x02,0x00,0x01,0x00,0x21,0x00,0x10,0x00,0x00])

        # 7. Esperar respuesta x80
        log.info("Handshake Paso 7: Esperar respuesta x80")
        self.wait_for_event("raw", lambda d: len(d) >= 10 and d[0] == 0x0c and d[4] == 0xed and d[6] == 0x80)

        # 8. ACK x80
        log.info("Handshake Paso 8: Enviar ACK x80")
        self.write([0x11,0x00,0x00,0x18,0x80,0x10,0xed,0x03,0x00,0x02,0x00,0x04,0x00,0x10,0x00,0x00,0x01,0x00,0x06,0x00,0x01,0x00,0x00,0x00,0x06,0x00,0x00,0x00])

        # 9. Init x2 + Mensaje x80
        log.info("Handshake Paso 9: Enviar Init x2 + Mensaje x80")
        self.write([0x0c,0x00,0x00,0x28,0x02,0x10,0xf0,0x03,0x00,0x00,0x00,0x02,0x00,0x01,0x00,0x21,0x00,0x10,0x00,0x00])
        self.write([0x08,0x00,0x00,0x18,0x80,0x10,0xed,0x03,0x00,0x03,0x00,0x10,0x1a,0x1e,0x00,0x00])

        # 10. Esperar respuesta x2
        log.info("Handshake Paso 10: Esperar respuesta x2")
        self.wait_for_event("raw", lambda d: len(d) >= 10 and d[0] == 0x0c and d[4] == 0xf0 and d[6] == 0x02)

        # 11. ACK x2
        log.info("Handshake Paso 11: Enviar ACK x2")
        self.write([0x11,0x00,0x00,0x18,0x02,0x10,0xf0,0x03,0x00,0x05,0x00,0x04,0x00,0x10,0x00,0x00,0x01,0x00,0x04,0x00,0x01,0x00,0x00,0x00,0x04,0x00,0x00,0x00])

        # 12. Keep-alive x2 + Re-init x1
        log.info("Handshake Paso 12: Enviar Keep-alive x2 + Re-init x1")
        self.write([0x08,0x00,0x00,0x18,0x02,0x10,0xf0,0x03,0x00,0x06,0x00,0x10,0x09,0x10,0x00,0x00])
        self.write([0x0c,0x00,0x00,0x28,0x01,0x10,0xef,0x03,0x00,0x00,0x00,0x02,0x00,0x01,0x00,0x21,0x00,0x10,0x00,0x00])

        # 13. Esperar respuesta x1
        log.info("Handshake Paso 13: Esperar respuesta x1")
        self.wait_for_event("raw", lambda d: len(d) >= 10 and d[0] == 0x0c and d[4] == 0xef and d[6] == 0x01)

        # 14. ACK Re-init x1
        log.info("Handshake Paso 14: Enviar ACK Re-init x1")
        self.write([0x11,0x00,0x00,0x18,0x01,0x10,0xef,0x03,0x00,0x02,0x00,0x04,0x00,0x10,0x00,0x00,0x01,0x00,0x02,0x00,0x01,0x00,0x00,0x00,0x02,0x00,0x00,0x00])

        # 15. Esperar confirmación de re-init x1
        log.info("Handshake Paso 15: Esperar confirmación x1")
        self.wait_for_event("raw", lambda d: len(d) >= 20 and d[4] == 0xef and d[6] == 0x01 and d[18] in (0x02, 0x05))

        # Inicializar los contadores para después del handshake
        self.x1_counter = 0x03
        self.x2_counter = 0x07
        self.x80_counter = 0x04
        self.preset_data_double_cnt = [0x1e, 0x00]

        self.handshake_done = True
        self._start_keep_alive()

        log.info("Handshake finalizado con éxito. Conexión establecida de forma estable.")

    def _start_keep_alive(self):
        """Inicia el hilo para enviar keep-alives a la Helix."""
        self.keep_alive_thread = threading.Thread(target=self._keep_alive_loop, name="HelixKeepAliveThread", daemon=True)
        self.keep_alive_thread.start()

    def _keep_alive_loop(self):
        """Envía periódicamente mensajes keep-alive a la Helix para mantener activa la sesión."""
        time.sleep(0.5)
        while not self.stop_event.is_set():
            try:
                if self.handshake_done:
                    # Keep-alive x1
                    self.write([0x08, 0x00, 0x00, 0x18, 0x01, 0x10, 0xef, 0x03, 0x00, "XX", 0x00, 0x08, 0x72, 0x1e, 0x00, 0x00])
                    # Keep-alive x2
                    self.write([0x08, 0x00, 0x00, 0x18, 0x02, 0x10, 0xf0, 0x03, 0x00, "XX", 0x00, 0x10, 0x09, 0x10, 0x00, 0x00])
                    # Keep-alive x80
                    self.write([0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03, 0x00, "XX", 0x00, 0x10, self.session_no, self.preset_data_double_cnt[0], self.preset_data_double_cnt[1], 0x00])
            except Exception as e:
                log.warning(f"Error en bucle keep-alive: {e}")
            
            # Dormir 1 segundo en total, pero en pequeños intervalos para salir rápido al detener
            for _ in range(10):
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)

    def fetch_active_preset_info(self):
        """Envía las peticiones del preset actual, calcula el índice y extrae el nombre."""
        self.capture_model_echoes = False
        try:
            res = self._fetch_active_preset_info_impl()
        finally:
            self.capture_model_echoes = True
        return res

    def _fetch_active_preset_info_impl(self):
        log.info("Solicitando información del preset actual...")
        self.preset_data_double_cnt = [0x1e, 0x00]
        
        # Limpiar cola de eventos antes de empezar
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except queue.Empty:
                break
        self.session_no = random.randint(4, 250)
        
        # Iniciar lectura del preset actual
        self.write([
            0x19, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03, 0x00, "XX", 0x00, 0x04,
            self.session_no, self.preset_data_double_cnt[0], self.preset_data_double_cnt[1], 0x00,
            0x01, 0x00, 0x06, 0x00, 0x09, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, 0x04, 0x04, 0x64, 0x17, 0x65, 0xc0, 0x00, 0x00, 0x00
        ])
        
        # Enviar petición extra de control sobre canal x1
        self.write([0x08, 0x00, 0x00, 0x18, 0x01, 0x10, 0xef, 0x03, 0x00, "XX", 0x00, 0x08, 0x72, 0x1e, 0x00, 0x00])

        # Esperar la cabecera del preset (Preset Header) para determinar el índice activo
        header_data = self.wait_for_event("preset_header", timeout=5.0)
        header_data = bytes(header_data)
        
        idx_6b = 0
        idx_6c = 0
        preset_name = ""
        
        for i in range(len(header_data) - 3):
            if header_data[i] == 0x6b and header_data[i+1] == 0xcd:
                idx_6b = header_data[i+3]
            if header_data[i] == 0x6c and header_data[i+1] == 0xcd:
                idx_6c = header_data[i+3]
                
                # Check if preset name tag 0x6d is present right after idx_6c
                if i + 4 < len(header_data) and header_data[i+4] == 0x6d:
                    length_byte = header_data[i+5]
                    strlen = length_byte - 0xa0 if length_byte >= 0xa0 else length_byte
                    if i + 6 + strlen <= len(header_data):
                        name_bytes = header_data[i+6 : i+6+strlen]
                        # Split by null terminator if any, decode as ascii
                        preset_name = name_bytes.split(b'\x00')[0].decode('ascii', errors='ignore').strip()
                
        self.active_setlist_idx = idx_6b
        self.active_preset_idx_in_setlist = idx_6c
        
        # Determinar si es de la familia Helix Grande (Floor, LT, Rack) o HX Stomp/POD Go
        is_helix_large = self.product_id in (0x4241, 0x4242, 0x4244, 0x424a)
        if is_helix_large:
            # Helix grande tiene 8 setlists de 128 presets cada una (32 bancos x 4 presets)
            self.active_preset_idx = (idx_6b * 128) + idx_6c
        else:
            # HX Stomp / Stomp XL tiene grupos de 25 presets
            self.active_preset_idx = (idx_6b * 25) + idx_6c
            
        log.info(f"Setlist idx: {self.active_setlist_idx}, Preset idx in setlist: {self.active_preset_idx_in_setlist}, Absolute idx: {self.active_preset_idx}")

        if preset_name:
            self.preset_name = preset_name
            log.info(f"Nombre del preset activo decodificado directamente: '{self.preset_name}'")
        else:
            log.warning("No se pudo decodificar el nombre del preset directamente desde la cabecera.")
            self.preset_name = "Desconocido"

        return {
            "setlist_idx": self.active_setlist_idx,
            "setlist_name": self.get_setlist_name(self.active_setlist_idx),
            "preset_idx_in_setlist": self.active_preset_idx_in_setlist,
            "preset_name": self.preset_name,
            "bank_name": self.get_bank_name(self.active_preset_idx_in_setlist),
            "absolute_preset_idx": self.active_preset_idx
        }

    def get_setlist_name(self, setlist_idx):
        """Devuelve el nombre del setlist según el índice y el dispositivo."""
        is_helix_large = self.product_id in (0x4241, 0x4242, 0x4244, 0x424a)
        if not is_helix_large:
            return "Presets"
        if 0 <= setlist_idx < len(self.setlist_names):
            return self.setlist_names[setlist_idx]
        return f"Setlist {setlist_idx + 1}"

    def get_bank_name(self, preset_idx_in_setlist):
        """Calcula el nombre del banco (ej. 01B o 13D) según el dispositivo."""
        is_helix_large = self.product_id in (0x4241, 0x4242, 0x4244, 0x424a)
        if is_helix_large:
            bank_num = (preset_idx_in_setlist // 4) + 1
            bank_letter = chr(65 + (preset_idx_in_setlist % 4))
        else:
            # HX Stomp / Stomp XL tiene 3 presets por banco (A, B, C)
            bank_num = (preset_idx_in_setlist // 3) + 1
            bank_letter = chr(65 + (preset_idx_in_setlist % 3))
        return f"{bank_num:02d}{bank_letter}"

    def next_editor_ed03_double(self):
        self.editor_ed03_double = (self.editor_ed03_double + 1) & 0xffff
        return [self.editor_ed03_double & 0xff, (self.editor_ed03_double >> 8) & 0xff]
        
    def next_preset_dump_ack_double(self):
        self.preset_dump_ack_ctr = (self.preset_dump_ack_ctr + 1) & 0xffff
        return [self.preset_dump_ack_ctr & 0xff, (self.preset_dump_ack_ctr >> 8) & 0xff]

    def fetch_active_preset_blocks(self, slot_idx=None):
        """Descarga el preset actual por USB, lo parsea y devuelve la lista de bloques activos."""
        if not self.is_connected():
            return False, "No conectado a la Helix"

        self.capture_model_echoes = False
        try:
            res = self._fetch_active_preset_blocks_impl()
            if isinstance(res, list):
                if slot_idx is not None:
                    for b in res:
                        if b.get("slot_idx") == slot_idx:
                            return True, [b]
                    return False, f"Slot {slot_idx} no encontrado o vacío"
                return True, res
            return False, "No se recibieron bloques válidos"
        except Exception as e:
            return False, f"Error al leer bloques: {e}"
        finally:
            self.capture_model_echoes = True

    def _fetch_active_preset_blocks_impl(self):
        log.info("Starting 2-phase preset download...")
        while not self.event_queue.empty():
            self.event_queue.get_nowait()
            
        self.session_no = random.randint(4, 250)
        sess1 = self.session_no
        double1 = self.preset_data_double_cnt
        sess_id1 = 0x04
        cmd_type = 0x04
        phase2_session = max(4, random.randint(4, 250))
        
        # Phase 1 packet: sub=0x04
        phase1_pkt = [
            0x19, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX",  0x00, 0x04,
            sess1, double1[0], double1[1], 0x00,
            0x01, 0x00, 0x06, 0x00, 0x09, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, cmd_type,
            sess_id1, 0x64, 0x17, 0x65,
            0xc0, 0x00, 0x00, 0x00,
        ]
        
        self.write(phase1_pkt)
        self.write([0x08, 0x00, 0x00, 0x18, 0x01, 0x10, 0xef, 0x03, 0x00, "XX", 0x00, 0x08, 0x72, 0x1e, 0x00, 0x00])
        
        # Wait for Phase 1 Response
        start_time = time.time()
        phase1_resp = None
        while time.time() - start_time < 3.0:
            try:
                evt_type, data = self.event_queue.get(timeout=0.1)
                if evt_type == "keep_alive_x1":
                    continue
                log.info(f"Phase 1 Wait got event: {evt_type}, len={len(data)}, ch={data[4]}, sub={data[6]}, t11={data[11]}")
                if evt_type in ("preset_header", "raw") and len(data) >= 36 and data[4] == 0xed and data[6] == 0x80 and data[11] == 0x04:
                    phase1_resp = data
                    break
            except Exception:
                continue
                
        if not phase1_resp:
            log.error("Failed to receive Phase 1 response!")
            return []
            
        # Parse active indices from Phase 1 response
        idx_6b = 0
        idx_6c = 0
        preset_name = ""
        for i in range(len(phase1_resp) - 3):
            if phase1_resp[i] == 0x6b and phase1_resp[i+1] == 0xcd:
                idx_6b = phase1_resp[i+3]
            if phase1_resp[i] == 0x6c and phase1_resp[i+1] == 0xcd:
                idx_6c = phase1_resp[i+3]
                if i + 4 < len(phase1_resp) and phase1_resp[i+4] == 0x6d:
                    length_byte = phase1_resp[i+5]
                    strlen = length_byte - 0xa0 if length_byte >= 0xa0 else length_byte
                    if i + 6 + strlen <= len(phase1_resp):
                        name_bytes = bytes(phase1_resp[i+6 : i+6+strlen])
                        preset_name = name_bytes.split(b'\x00')[0].decode('ascii', errors='ignore').strip()
                        
        self.active_setlist_idx = idx_6b
        self.active_preset_idx_in_setlist = idx_6c
        self.preset_name = preset_name or "Desconocido"
        
        # Send Phase 2
        double = self.next_editor_ed03_double()
        sess_id = 0xf4
        
        phase2_pkt = [
            0x19, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX",  0x00, 0x0c,
            phase2_session, double[0], double[1], 0x00,
            0x01, 0x00, 0x06, 0x00, 0x09, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, 0x03,
            sess_id, 0x64, 0x16, 0x65,
            0xc0, 0x00, 0x00, 0x00,
        ]
        
        self.write(phase2_pkt)
        
        # Download loop
        preset_data = bytearray()
        last_ack_double = [0, 0]
        completed = False
        start_time = time.time()
        
        while time.time() - start_time < 5.0:
            try:
                evt_type, data = self.event_queue.get(timeout=0.1)
                if evt_type == "keep_alive_x1":
                    continue
                if len(data) >= 16 and data[4] == 0xed and data[6] == 0x80 and data[11] == 0x04:
                    if len(data) == 32 and data[16] == 0xa1:
                        # Send FDT ACK
                        fdt_session = (phase2_session + 0x10) & 0xff
                        fdt_ack = [
                            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
                            0x00, "XX", 0x00, 0x08,
                            fdt_session, last_ack_double[0], last_ack_double[1], 0x00,
                        ]
                        self.write(fdt_ack)
                        completed = True
                        break
                    
                    chunk_payload = data[16:]
                    preset_data.extend(chunk_payload)
                    
                    # Send ACK
                    new_double = self.next_preset_dump_ack_double()
                    chunk_ack = [
                        0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
                        0x00, "XX", 0x00, 0x08,
                        phase2_session, new_double[0], new_double[1], 0x00,
                    ]
                    self.write(chunk_ack)
                    last_ack_double = new_double
                    
                    if len(chunk_payload) < 256:
                        completed = True
                        break
            except Exception:
                continue
                
        if not completed:
            log.warning("No se completó la descarga del preset.")
            return []
            
        self.session_no = (phase2_session + 0x10) & 0xff
        self.ed03_cmd_type = (self.ed03_cmd_type + 1) & 0xff
        self.preset_last_ack_double = last_ack_double
        
        hex_str = preset_data.hex()
        
        # DEBUG HACK: Save to disk for split analysis
        with open("preset_hex_split.txt", "w") as f:
            f.write(hex_str)
        
        # Parsear con HxPreset
        try:
            from utils.preset_parser import HxPreset
            
            hx_preset = HxPreset(data_in=hex_str, preset_name=self.preset_name)
            
            blocks = []
            
            def get_path_label(idx):
                if 0 <= idx <= 9:   return "1A"
                if 10 <= idx <= 19: return "1B"
                if 20 <= idx <= 29: return "2A"
                if 30 <= idx <= 39: return "2B"
                return "??"

            for idx, slot in enumerate(hx_preset.slot_info):
                st = getattr(slot, 'slot_type', 0x08)
                if st == 0x08:  # No Slot
                    continue
                
                path_label = get_path_label(idx)
                
                if st in (0x00, 0x01, 0x02, 0x03):
                    io_type = "Entrada" if st in (0x00, 0x02) else "Salida"
                    
                    routing_pos = None
                    try:
                        raw_bytes = slot.raw
                        if isinstance(raw_bytes, bytes) and 0x0d in raw_bytes:
                            idx_0d = list(raw_bytes).index(0x0d)
                            if idx_0d + 1 < len(raw_bytes):
                                routing_pos = raw_bytes[idx_0d + 1]
                    except Exception:
                        pass
                        
                    blocks.append({
                        "slot_idx": idx,
                        "type": "io",
                        "path": path_label,
                        "name": f"{io_type} Path {path_label}",
                        "category": "I/O",
                        "routing_pos": routing_pos,
                        "params_a": getattr(slot, 'parameter_b', []),
                        "dual_name": None,
                        "dual_category": None
                    })
                elif st in (0x06, 0x07): # Standard Slot or Looper
                    names = slot.id_to_names()
                    block_a = names[0]
                    block_b = names[1]
                    
                    hex_a = ''.join('{:02x}'.format(x) for x in slot.amp_effect_slot_a) if getattr(slot, 'amp_effect_slot_a', b'\xff') != b'\xff' else None
                    hex_b = ''.join('{:02x}'.format(x) for x in slot.amp_effect_slot_b) if getattr(slot, 'amp_effect_slot_b', b'\xff') != b'\xff' else None
                    
                    if block_a != '' or block_b != '':
                        blocks.append({
                            "slot_idx": idx,
                            "type": "effect",
                            "path": path_label,
                            "hex_id": hex_a,
                            "name": block_a[1] if block_a != '' else None,
                            "category": block_a[0] if block_a != '' else None,
                            "params_a": getattr(slot, 'parameter_a', []),
                            "dual_hex_id": hex_b,
                            "dual_name": block_b[1] if block_b != '' else None,
                            "dual_category": block_b[0] if block_b != '' else None,
                            "params_b": getattr(slot, 'parameter_b', []) if block_b != '' else []
                        })
            
            return blocks
        except Exception as parse_err:
            log.error(f"Error al parsear bloques del preset: {parse_err}")
            return []

    @staticmethod
    def _assemble_27_write(seq, byte11, ctr, yy, pp, param_selector, slot_bus, float_be):
        return [
            0x27, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, seq, 0x00, byte11,
            ctr & 0xff,
            (ctr >> 8) & 0xff,
            0x00,
            0x00,
            0x01, 0x00, 0x06, 0x00, 0x17, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, pp, yy, 0x64, 0x1e, 0x65,
            0x85, 0x62, slot_bus, 0x1d, 0xc3, 0x1a, 0x00, 0x1c,
            param_selector, 0x77, 0xca, float_be[0], float_be[1], float_be[2], float_be[3], 0x00,
        ]

    def write_block_parameter(self, slot_idx, param_idx, target_db, norm_val=None):
        """
        Envía la secuencia completa para escribir un parámetro en tiempo real.
        Usa el foco previo para adquirir contexto, escribe, y restaura el foco original.
        """
        if not self.is_connected():
            return False, "No conectado a la Helix"

        import struct
        
        # Si no se provee el valor normalizado, lo calculamos asumiendo rango de EQ estándar (-15.0 a +15.0)
        # Nota: Idealmente norm_val debe ser calculado por el parser de presets.
        if norm_val is None:
            norm_val = (target_db - (-15.0)) / 30.0

        float_be_a = list(struct.pack('>f', norm_val))
        float_be_b = list(struct.pack('>f', target_db))
        
        slot_bus = slot_idx
        pp = 3 # Graphic EQ uses default pp = 3 (esto debería ser dinámico pero lo usamos como estándar)
        
        # Capturar eco de foco (usamos la misma técnica exitosa que en test_hellix_write.py)
        focus_pkt_cd04 = [
            0x1d, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX",  0x00, 0x04,
            self.session_no, self.preset_data_double_cnt[0], self.preset_data_double_cnt[1], 0x00,
            0x01, 0x00, 0x06, 0x00, 0x0d, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, 0x04, slot_bus, 0x64, 0x4e, 0x65,
            0x82, 0x62, slot_bus, 0x1a, 0x00, 0x00, 0x00, 0x00,
        ]
        
        focus_pkt_cd03 = [
            0x1d, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX",  0x00, 0x04,
            self.session_no, self.preset_data_double_cnt[0], self.preset_data_double_cnt[1], 0x00,
            0x01, 0x00, 0x06, 0x00, 0x0d, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, 0x03, 0xf9, 0x64, 0x4e, 0x65,
            0x82, 0x62, slot_bus, 0x1a, 0x00, 0x00, 0x00, 0x00,
        ]

        self.last_ed03_echo_model = None
        log.info(f"Intentando capturar foco para slot {slot_bus}...")
        
        try:
            self.write(focus_pkt_cd04)
        except Exception as e:
            return False, f"Error al enviar paquete de foco cd:04: {e}"

        start_wait = time.time()
        while self.last_ed03_echo_model is None and (time.time() - start_wait) < 0.25:
            time.sleep(0.01)
            
        if self.last_ed03_echo_model is None:
            log.info("Reintentando con foco cd:03...")
            try:
                self.write(focus_pkt_cd03)
            except Exception:
                pass
            start_wait = time.time()
            while self.last_ed03_echo_model is None and (time.time() - start_wait) < 0.25:
                time.sleep(0.01)

        if not self.last_ed03_echo_model:
            return False, "La Helix no respondió al cambio de foco. Asegúrese de que no haya menús abiertos en la pedalera."

        # Construir paquetes usando el modelo capturado
        model_block_a = list(self.last_ed03_echo_model)
        seq_a = (model_block_a[4] + 1) & 0xff
        seq_b = (seq_a + 1) & 0xff
        
        ctr_a = self.live_write_ctr
        yy_a = self.live_write_yy
        
        pre_packet_x80 = [
            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX", 0x00, 0x10, self.session_no, self.preset_data_double_cnt[0], self.preset_data_double_cnt[1], 0x00
        ]
        
        pre_packet_x2 = [
            0x08, 0x00, 0x00, 0x18, 0x02, 0x10, 0xf0, 0x03,
            0x00, "XX", 0x00, 0x10, 0x09, 0x10, 0x00, 0x00
        ]
        
        pre_packet_x80_sel = [
            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX", 0x00, 0x08, ctr_a & 0xff, (ctr_a >> 8) & 0xff, 0x00, 0x00
        ]
        
        packet_a = self._assemble_27_write("XX", 0x04, ctr_a, seq_a, pp, param_idx, slot_bus, float_be_a)
        
        ctr_b = (ctr_a + 0x1f) & 0xffff
        seq_b = (seq_a + 1) & 0xff
        packet_b = self._assemble_27_write("XX", 0x0c, ctr_b, seq_b, pp, param_idx, slot_bus, float_be_b)
        
        ctr_post = (ctr_b + 0x1f) & 0xffff
        post_packet_x80_sel = [
            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX", 0x00, 0x08, ctr_post & 0xff, (ctr_post >> 8) & 0xff, 0x00, 0x00
        ]

        # Asegurar foco al slot actual
        restore_focus_pkt = focus_pkt_cd04.copy()
        restore_focus_pkt[28] = slot_bus
        restore_focus_pkt[34] = slot_bus

        # Enviar secuencia con semáforo reentrante y tiempos críticos
        try:
            with self.write_lock:
                self.write(pre_packet_x80)
                time.sleep(0.006)
                self.write(pre_packet_x2)
                time.sleep(0.010)
                self.write(pre_packet_x80_sel)
                time.sleep(0.016)
                self.write(packet_a)
                time.sleep(0.012)
                self.write(packet_b)
                time.sleep(0.012)
                self.write(post_packet_x80_sel)
                
                self.write(restore_focus_pkt)
                time.sleep(0.010)
        except Exception as e:
            return False, f"Error durante la escritura USB: {e}"

        # Actualizar estado interno
        self.live_write_ctr = (ctr_post + 0x1f) & 0xffff
        self.live_write_yy = (seq_b + 1) & 0xff

        return True, "Parámetro modificado exitosamente."


