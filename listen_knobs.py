import sys
import time
from helix_connection import HelixConnection

def main():
    print("====================================================")
    print(" Helix Knob Sniffer / Listener Tool")
    print("====================================================")
    print("Asegúrate de que HX Edit esté cerrado.")
    print("Ejecuta este script y gira la perilla de 31.25Hz del Graphic EQ")
    print("en el Slot 4 de tu Helix. Imprimiremos los bytes recibidos.")
    print("====================================================")
    
    conn = HelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        print("\n[+] Escuchando cambios en la Helix. Gira una perilla ahora...")
        print("Presiona Ctrl+C para detener.")
        
        while True:
            try:
                # Sacar eventos de la cola
                if not conn.event_queue.empty():
                    evt_type, data = conn.event_queue.get_nowait()
                    
                    # Ignorar keep-alives para no saturar la pantalla
                    if "keep_alive" in evt_type:
                        continue
                        
                    hex_bytes = [f"0x{x:02x}" for x in data]
                    print(f"\n [+] Recibido Evento '{evt_type}' (Longitud {len(data)}):")
                    print("     " + ", ".join(hex_bytes))
                    
                time.sleep(0.01)
            except Exception as e:
                print(f" [!] Error en la lectura: {e}")
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n[+] Escucha finalizada por el usuario.")
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
