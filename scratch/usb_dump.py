import sys
import time
import usb.core
import usb.util
from helix_connection import HelixConnection

def main():
    print("====================================================")
    print(" Helix LT Native USB Raw Sniffer")
    print("====================================================")
    
    conn = HelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        # Detener el hilo lector de HelixConnection para leer directamente desde el endpoint
        conn.stop_event.set()
        if conn.reader_thread and conn.reader_thread.is_alive():
            conn.reader_thread.join(timeout=1.0)
        
        print("\n[+] Hilo lector apagado. Sniffing directo en Endpoint 0x81 activo.")
        print("Gira la perilla 31.25Hz del EQ en tu Helix LT...")
        print("Presiona Ctrl+C para salir.")
        
        # Vaciar cola
        while not conn.event_queue.empty():
            conn.event_queue.get_nowait()
            
        last_time = time.time()
        while True:
            try:
                # Leer directamente del USB Endpoint 0x81
                data = conn.dev.read(conn.endpoint_in, 512, timeout=500)
                if data:
                    t_gap = time.time() - last_time
                    last_time = time.time()
                    
                    # Ignorar los keep-alives comunes para ver solo los cambios de perillas
                    # Keep-alives x1 (0xef/0x01) y x2 (0xf0/0x02) y x80 (0xed/0x80)
                    is_keep_alive = False
                    if len(data) >= 10:
                        if data[4] == 0xef and data[6] == 0x01:
                            is_keep_alive = True
                        elif data[4] == 0xf0 and data[6] == 0x02 and data[11] == 0x04:
                            is_keep_alive = True
                        elif data[4] == 0xed and data[6] == 0x80 and data[11] == 0x10:
                            is_keep_alive = True
                            
                    if not is_keep_alive:
                        hex_str = ", ".join(f"0x{x:02x}" for x in data)
                        print(f"\n[+{t_gap:.3f}s] Recibidos {len(data)} bytes:")
                        print(f"  {hex_str}")
            except usb.core.USBError as e:
                # Ignorar timeouts normales (error -7 o timeout en str)
                if e.backend_error_code == -7 or "timeout" in str(e).lower() or e.errno in (10060, 110):
                    continue
                else:
                    print(f" [!] Error USB: {e}")
                    break
    except KeyboardInterrupt:
        print("\n[+] Sniffing finalizado.")
    finally:
        conn.disconnect()
        print("Conexión cerrada.")

if __name__ == "__main__":
    main()
