import sys
import os
import time
import usb.core
import usb.util
import libusb_package
import threading

def listen_ep5():
    backend = libusb_package.get_libusb1_backend()
    dev = usb.core.find(idVendor=0x0E41, idProduct=0x424a, backend=backend)
    
    if not dev:
        print("Helix no encontrada.")
        return
        
    print("Helix detectada. Configurando...")
    try:
        cfg = dev.get_active_configuration()
    except usb.core.USBError:
        try:
            dev.set_configuration()
        except Exception as e:
            print(f"Advertencia al configurar: {e}")
    
    intf_num = 5
    print(f"Reclamando interfaz {intf_num}...")
    try:
        usb.util.claim_interface(dev, intf_num)
    except Exception as e:
        print(f"No se pudo reclamar la interfaz {intf_num}: {e}")
        print("Asegúrate de que HX Edit y nuestra app MondoPedalboard estén completamente CERRADOS.")
        return
        
    print("Escuchando en el Endpoint 0x85 (Interrupt IN)...")
    print("¡Por favor, mueve un bloque o haz un cambio en la pedalera física y observa la salida!")
    
    try:
        while True:
            try:
                # El endpoint 0x85 es de tipo Interrupt.
                data = dev.read(0x85, 64, timeout=1000)
                if data:
                    print(f"T={time.time():.2f} - EVENTO RECIBIDO ({len(data)} bytes): {bytes(data).hex()}")
            except usb.core.USBError as e:
                if e.errno == 10060 or getattr(e, 'backend_error_code', 0) == -7 or "timeout" in str(e).lower():
                    continue
                print(f"Error USB: {e}")
                break
    except KeyboardInterrupt:
        print("Saliendo...")
    finally:
        usb.util.dispose_core(dev)
        try:
            usb.util.release_interface(dev, intf_num)
            print("Interfaz liberada.")
        except:
            pass

if __name__ == "__main__":
    listen_ep5()
