import sys
import time
import os
import json
import struct

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from helix_connection import HelixConnection
from utils.modules import _models_db, _load_db

def test_change_model(conn, slot_idx, new_hex_id_str, slot_bus=0x01):
    """
    Cambia el modelo de un bloque utilizando el paquete descubierto por Wireshark.
    El hex_id_str viene en formato "0x0283".
    """
    if not conn.is_connected():
        return False, "No conectado a la Helix"
        
    try:
        hex_id = int(new_hex_id_str, 16)
        # hex_id es de 3 bytes, ej: cd 03 08
        # En la cadena hexadecimal "cd0308", el primer byte es cd.
        h1 = (hex_id >> 16) & 0xFF
        h2 = (hex_id >> 8) & 0xFF
        h3 = hex_id & 0xFF
    except ValueError:
        return False, f"hex_id inválido: {new_hex_id_str}"
        
    print(f"[!] Enviando paquete de cambio de modelo al slot {slot_idx} con hex_id {h1:02x} {h2:02x} {h3:02x}")
    
    # 1. Paquete de cambio de modelo directo
    packet = [
        0x25, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
        0x00, "XX", 0x00, 0x04,
        conn.session_no, conn.preset_data_double_cnt[0], conn.preset_data_double_cnt[1], 0x00,
        0x01, 0x00, 0x06, 0x00, 0x15, 0x00, 0x00, 0x00,
        0x83, 0x66, 0xcd, slot_idx, 0x00, 0x64, 0x28, 0x65,
        0x82, 0x62, slot_bus, 0x64, 0x83, 0x17, 0xc2, 0x19,
        h1, h2, h3, 0x1a, 0xff, 0x00, 0x00, 0x00,
    ]
    conn.write(packet)
    time.sleep(0.1)
    
    return True, "Comando de cambio de modelo enviado."

def main():
    print("====================================================")
    print(" Prueba de Cambio de Cab en Helix")
    print("====================================================")
    
    _load_db()
    
    cabs_disponibles = {k: v for k, v in _models_db.items() if v.get("category") in ["Cab", "Impulse Response", "IR"]}
    print(f"[+] Se encontraron {len(cabs_disponibles)} Cabs en la base de datos local.")
    
    conn = HelixConnection()
    success, msg = conn.connect()
    
    if not success:
        print(f" [!] Error al conectar: {msg}")
        return
        
    try:
        conn.perform_handshake()
        
        print("\n[+] Leyendo bloques del preset activo...")
        success, blocks = conn.fetch_active_preset_blocks()
        if not success:
            print(f" [!] No se pudo leer el preset: {blocks}")
            return
            
        cab_block = next((b for b in blocks if b.get('category') in ['Cab', 'Impulse Response', 'IR']), None)
        
        if not cab_block:
            print(" [!] No se encontró ningún bloque Cab en el preset actual.")
            return
            
        print(f" [+] Cab actual detectado:")
        print(f"     Slot: {cab_block['slot_idx']}")
        print(f"     Nombre: {cab_block['name']}")
        print(f"     Hex ID Actual: {cab_block['hex_id']}")
        
        print("\n[+] Mostrando los primeros 10 Cabs disponibles en la DB para cambiar:")
        cab_keys = list(cabs_disponibles.keys())[:10]
        for idx, k in enumerate(cab_keys):
            print(f"     [{idx}]: {cabs_disponibles[k]['name']} (ID: {k})")
            
        print("\nIntroduce el número del Cab al que quieres cambiar (0-9) o 'q' para salir:")
        user_input = input(">> ").strip()
        
        if user_input.lower() == 'q':
            return
            
        try:
            seleccion = int(user_input)
            if 0 <= seleccion < len(cab_keys):
                target_model_id = cab_keys[seleccion]
                
                # Buscar el hex_id real iterando usb_mapping en modules.json
                with open(os.path.join(parent_dir, "utils", "modules.json"), "r", encoding="utf-8") as f:
                    data = json.load(f)
                usb_mapping = data.get("usb_mapping", {})
                
                real_hex_id_str = None
                for hid, mapping in usb_mapping.items():
                    if mapping.get("model_id") == target_model_id:
                        real_hex_id_str = hid
                        break
                        
                if not real_hex_id_str:
                    print(f" [!] No se encontró el hex_id para {target_model_id} en usb_mapping.")
                else:
                    print(f"\n[+] Intentando cambiar al Cab: {cabs_disponibles[target_model_id]['name']} (Hex ID: {real_hex_id_str})...")
                    
                    # Intentamos enviar el comando
                    ok, res_msg = test_change_model(conn, cab_block['slot_idx'], real_hex_id_str)
                    print(f" Resultado: {res_msg}")
                
            else:
                print("Selección inválida.")
        except ValueError:
            print("Entrada no válida.")
            
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
