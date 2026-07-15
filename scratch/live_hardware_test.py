import sys
import os
import time
import logging

# Add parent directory to path so it can find helix_connection
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("HardwareTest")

from helix_connection import HelixConnection

def main():
    conn = HelixConnection()
    ok, msg = conn.connect()
    if not ok:
        print(f"Error: {msg}")
        return
        
    print("Conectando y haciendo handshake...")
    conn.perform_handshake()
    print("Handshake completado. ¡Helix conectada!")
    print("\n=======================================================")
    print("POR FAVOR, MUEVE O CAMBIA UN BLOQUE EN LA PANTALLA DE LA HELIX AHORA")
    print("=======================================================\n")
    
    # Vamos a espiar la cola de eventos durante 15 segundos
    start = time.time()
    while time.time() - start < 15:
        try:
            evt, data = conn.event_queue.get(timeout=0.5)
            if evt not in ("keep_alive_x1", "keep_alive_x80"):
                if isinstance(data, (bytes, bytearray, list)):
                    hex_data = "".join(f"{x:02x}" for x in data)
                    print(f"[{evt}] Recibido: {hex_data}")
                else:
                    print(f"[{evt}] {data}")
        except Exception:
            pass
            
    print("\nPrueba finalizada. Desconectando...")
    conn.disconnect()

if __name__ == "__main__":
    main()
