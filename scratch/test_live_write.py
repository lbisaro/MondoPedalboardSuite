import sys
import time
import struct
import logging
from helix_connection import HelixConnection

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger("TestLiveWrite")

def print_slot_4_param_0(blocks):
    if not blocks:
        print(" [!] No se recibieron bloques.")
        return None
    for b in blocks:
        if b["slot_idx"] == 4:
            params = b.get('params_a', [])
            if params:
                val = params[0]
                print(f" [+] Slot 4 ({b['name']}) - Parámetro 0: {val} dB")
                return val
            else:
                print(" [!] El Slot 4 no tiene parámetros en params_a.")
                return None
    print(" [!] No se encontró el Slot 4.")
    return None

def assemble_27_write(seq, byte11, ctr, yy, pp, param_selector, slot_bus, float_be):
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

def main():
    print("====================================================")
    print(" Helix Native Live Parameter Write Test")
    print("====================================================")
    
    conn = HelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        print("\n[+] Leyendo estado inicial...")
        preset_info = conn.fetch_active_preset_info()
        print(f" [+] Preset activo: '{preset_info['preset_name']}' en banco {preset_info['bank_name']}")
        
        # Escanear cola de eventos en busca de 83 66 cd
        last_echo = None
        # Hacemos una copia de los eventos acumulados
        temp_queue = []
        while not conn.event_queue.empty():
            temp_queue.append(conn.event_queue.get())
        
        print(f" [+] Analizando {len(temp_queue)} eventos en la cola inicial...")
        for evt_type, data in temp_queue:
            conn.event_queue.put((evt_type, data))
            d_bytes = bytes(data)
            print(f"   Event: {evt_type}, Len: {len(d_bytes)}, Hex: {d_bytes.hex()}")
            
            # Buscar 83 66 cd en cualquier posición
            for i in range(len(d_bytes) - 2):
                if d_bytes[i] == 0x83 and d_bytes[i+1] == 0x66 and d_bytes[i+2] == 0xcd:
                    # Extraer 16 bytes si es posible, de lo contrario lo que quede
                    end_idx = min(i + 16, len(d_bytes))
                    last_echo = list(d_bytes[i:end_idx])
                    # Si quedó más corto de 16, rellenar con ceros
                    while len(last_echo) < 16:
                        last_echo.append(0x00)
                    print(f" [***] ¡ENCONTRADO ECO DE MODELO!: {[hex(x) for x in last_echo]}")
                    break
        
        blocks = conn.fetch_active_preset_blocks()
        initial_val = print_slot_4_param_0(blocks)
        
        # También buscar en la cola después de leer bloques
        temp_queue = []
        while not conn.event_queue.empty():
            temp_queue.append(conn.event_queue.get())
        
        print(f" [+] Analizando {len(temp_queue)} eventos tras leer bloques...")
        for evt_type, data in temp_queue:
            conn.event_queue.put((evt_type, data))
            d_bytes = bytes(data)
            print(f"   Event: {evt_type}, Len: {len(d_bytes)}, Hex: {d_bytes.hex()}")
            
            for i in range(len(d_bytes) - 2):
                if d_bytes[i] == 0x83 and d_bytes[i+1] == 0x66 and d_bytes[i+2] == 0xcd:
                    end_idx = min(i + 16, len(d_bytes))
                    last_echo = list(d_bytes[i:end_idx])
                    while len(last_echo) < 16:
                        last_echo.append(0x00)
                    print(f" [***] ¡ENCONTRADO ECO DE MODELO POST-BLOCKS!: {[hex(x) for x in last_echo]}")
                    break
        
        # Parámetros del cambio
        slot_idx = 4
        param_idx = 0
        pp = 3
        
        # Mapeo de slot a slot_bus
        slot_bus = (slot_idx + 1) if slot_idx < 8 else (slot_idx + 3)

        # Trama de Focus Slot (activar el slot en el hardware utilizando variante cd:04 tipo HX Edit)
        focus_packet = [
            0x1d, 0x00, 0x00, 0x18,
            0x80, 0x10, 0xed, 0x03,
            0x00, "XX",  0x00, 0x04,
            conn.session_no, conn.preset_data_double_cnt[0], conn.preset_data_double_cnt[1], 0x00,
            0x01, 0x00, 0x06, 0x00,
            0x0d, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, 0x04,   # Variante cd:04
            slot_bus, 0x64, 0x4e, 0x65, # slot_bus como tag
            0x82, 0x62, slot_bus, 0x1a,
            0x00, 0x00, 0x00, 0x00,
        ]
        
        # Limpiar el último eco antes de enfocar para asegurarnos de que capturemos uno nuevo
        conn.last_ed03_echo_model = None
        
        print(f"\n[+] Enviando enfoque a Slot {slot_idx} (slot_bus {slot_bus})...")
        conn.write(focus_packet)
        
        # Esperar a que el hilo lector capture el eco del modelo
        print(" [+] Esperando eco de modelo del Slot 4 desde el hardware...")
        start_wait = time.time()
        while conn.last_ed03_echo_model is None and (time.time() - start_wait) < 1.0:
            time.sleep(0.02)
            
        if conn.last_ed03_echo_model:
            print(f" [***] ¡Eco de modelo capturado para el Slot 4!: {[hex(x) for x in conn.last_ed03_echo_model]}")
        else:
            print(" [!] Advertencia: No se recibió un eco de modelo nuevo del hardware. Usando valores por defecto.")
            
        # Ahora que tenemos el eco (o no), construimos los paquetes de escritura
        # Queremos cambiar la banda de 31.25Hz (EQ Gráfico) a +5.0 dB
        # Rango: -15.0 a +15.0 dB.
        # Valor normalizado: (5.0 - (-15.0)) / 30.0 = 20.0 / 30.0 = 0.666667
        target_db = 5.0
        norm_val = (target_db - (-15.0)) / 30.0
        
        # Inicialización de contadores live write
        # En hxlinux: live_write_ctr: 0x6cbd, live_write_yy: 0x17
        live_write_ctr = 0x6cbd
        live_write_yy = 0x17
        
        # Preparación de valores float BE
        float_be_a = list(struct.pack('>f', norm_val))
        float_be_b = list(struct.pack('>f', target_db))
        
        # Trama 1: pre_packet_x80 (delay 0)
        pre_packet_x80 = [
            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX", 0x00, 0x10, conn.session_no, conn.preset_data_double_cnt[0], conn.preset_data_double_cnt[1], 0x00
        ]
        
        # Trama 2: pre_packet_x2 (delay 4ms)
        pre_packet_x2 = [
            0x08, 0x00, 0x00, 0x18, 0x02, 0x10, 0xf0, 0x03,
            0x00, "XX", 0x00, 0x10, 0x09, 0x10, 0x00, 0x00
        ]
        
        # Trama 3: pre_packet_x80_sel (delay 8ms)
        pre_packet_x80_sel = [
            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX", 0x00, 0x08, live_write_ctr & 0xff, (live_write_ctr >> 8) & 0xff, 0x00, 0x00
        ]
        
        # Trama 4: packet_a (leg A) (delay 12ms)
        packet_a = assemble_27_write("XX", 0x04, live_write_ctr, live_write_yy, pp, param_idx, slot_bus, float_be_a)
        
        # Incrementar contadores para leg B
        live_write_ctr = (live_write_ctr + 0x1f) & 0xffff
        live_write_yy = (live_write_yy + 1) & 0xff
        
        # Trama 5: packet_b (leg B) (delay 8ms)
        packet_b = assemble_27_write("XX", 0x0c, live_write_ctr, live_write_yy, pp, param_idx, slot_bus, float_be_b)
        
        # Si capturamos un eco de modelo del hardware, superponer los bytes correspondientes
        if conn.last_ed03_echo_model:
            # Clonar el bloque y asignar yy
            model_block_a = list(conn.last_ed03_echo_model)
            model_block_a[4] = live_write_yy
            packet_a[24:40] = model_block_a
            
            model_block_b = list(conn.last_ed03_echo_model)
            model_block_b[4] = (live_write_yy + 1) & 0xff
            packet_b[24:40] = model_block_b
            
        # Incrementar contadores para post_packet
        live_write_ctr = (live_write_ctr + 0x1f) & 0xffff
        live_write_yy = (live_write_yy + 1) & 0xff
        
        # Trama 6: post_packet_x80_sel (delay 8ms)
        post_packet_x80_sel = [
            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX", 0x00, 0x08, live_write_ctr & 0xff, (live_write_ctr >> 8) & 0xff, 0x00, 0x00
        ]
        
        print(f"\n[+] Enviando secuencia de 6 tramas para cambiar parámetro a {target_db} dB (norm: {norm_val})...")
        print(f"  packet_a: {' '.join(f'{x:02x}' if isinstance(x, int) else str(x) for x in packet_a)}")
        print(f"  packet_b: {' '.join(f'{x:02x}' if isinstance(x, int) else str(x) for x in packet_b)}")
        
        conn.write(pre_packet_x80)
        time.sleep(0.004)
        conn.write(pre_packet_x2)
        time.sleep(0.008)
        conn.write(pre_packet_x80_sel)
        time.sleep(0.012)
        conn.write(packet_a)
        time.sleep(0.008)
        conn.write(packet_b)
        time.sleep(0.008)
        conn.write(post_packet_x80_sel)
        
        print("[+] Secuencia enviada. Esperando 1 segundo para leer el resultado...")
        time.sleep(1.0)
        
        blocks = conn.fetch_active_preset_blocks()
        final_val = print_slot_4_param_0(blocks)
        
        if final_val is not None:
            if abs(final_val - target_db) < 0.1:
                print("\n[SUCCESS] ¡El parámetro cambió exitosamente en el dispositivo!")
            else:
                print(f"\n[FAILURE] El parámetro no cambió (sigue siendo {final_val} dB).")
                
    except Exception as e:
        print(f"\n [!] Error: {e}")
    finally:
        conn.disconnect()
        print("\nConexión cerrada.")

if __name__ == "__main__":
    main()
