import sys
import time
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from helix_connection import HelixConnection

def main():
    if len(sys.argv) < 2:
        print("Uso: python test_unificado.py <numero_de_slot>")
        print("Ejemplo: python test_unificado.py 5")
        return

    slot_idx = int(sys.argv[1])
    target_db = 5.0

    print("====================================================")
    print(" Prueba de Conexión Unificada Helix")
    print("====================================================")
    
    conn = HelixConnection()
    success, msg = conn.connect()
    
    if not success:
        print(f" [!] Error al conectar: {msg}")
        return
        
    print(f" [+] {msg}")
    
    # IMPORTANTE: Inicializar handshake para establecer canales
    try:
        conn.perform_handshake()
    except Exception as e:
        print(f" [!] Error en handshake: {e}")
        return
        
    try:
        # Verificar estado (redundante pero útil para probar is_connected)
        if not conn.is_connected():
            print(" [!] La conexión se perdió inmediatamente después de conectar.")
            return

        # 1. Leer bloque específico
        print(f"\n[+] Leyendo bloque en slot {slot_idx}...")
        success, res = conn.fetch_active_preset_blocks(slot_idx=slot_idx)
        if not success:
            print(f" [!] No se pudo leer el bloque: {res}")
            return
            
        block = res[0]
        print(f"     Encontrado: {block.get('name', 'Desconocido')} en slot {block.get('slot_idx')}")

        # 2. Escribir parámetro
        print(f"\n[+] Escribiendo parámetro 0 a {target_db} dB...")
        write_ok, write_msg = conn.write_block_parameter(slot_idx=slot_idx, param_idx=0, target_db=target_db)
        if not write_ok:
            print(f" [!] Falla en escritura: {write_msg}")
            return
            
        print(f" [+] {write_msg}")
        
        # 3. Leer de nuevo para verificar
        time.sleep(2.0)
        print("\n[+] Verificando cambio...")
        success, res = conn.fetch_active_preset_blocks(slot_idx=slot_idx)
        if success:
            updated_block = res[0]
            params = updated_block.get('params_a', updated_block.get('params', []))
            if params and len(params) > 0:
                final_val = params[0]
                if abs(final_val - target_db) < 0.1:
                    print("\n====================================================")
                    print(f" [SUCCESS] El valor es ahora {final_val} dB")
                    print("====================================================")
                else:
                    print(f"\n [FAILURE] El valor sigue siendo {final_val} dB")
        else:
            print(f" [!] Falla al leer después de escribir: {res}")
            
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
