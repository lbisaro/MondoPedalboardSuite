import hid
import time

def listen_hid():
    print("Buscando dispositivos HID de la Helix...")
    target_path = None
    for device in hid.enumerate():
        if device['vendor_id'] == 0x0E41 and device['product_id'] == 0x424a:
            print(f"Encontrado HID: {device}")
            # En Windows a menudo se usa la ruta para abrir un dispositivo específico.
            target_path = device['path']
            
    if not target_path:
        print("No se encontraron interfaces HID para la Helix.")
        return
        
    print(f"Abriendo {target_path}...")
    h = hid.device()
    try:
        h.open_path(target_path)
        h.set_nonblocking(0) # Bloqueante
        print("Conectado al canal HID de la Helix. ¡Mueve un bloque físico!")
        
        while True:
            # Leer 8 bytes (MaxPacketSize del Endpoint 0x85)
            # En hidapi el primer byte suele ser el Report ID, así que pedimos 9 bytes
            data = h.read(9, timeout_ms=1000)
            if data:
                print(f"T={time.time():.2f} - EVENTO HID RECIBIDO: {bytes(data).hex()}")
    except KeyboardInterrupt:
        print("Saliendo...")
    except Exception as e:
        print(f"Error HID: {e}")
    finally:
        h.close()

if __name__ == "__main__":
    listen_hid()
