import sys
import time
import struct
from helix_connection import HelixConnection

def print_slot_4_param_0(blocks):
    if not blocks:
        print(" [!] No se recibieron bloques.")
        return None
    print(" [+] All blocks found in the active preset:")
    for b in blocks:
        print(f"   - Slot {b['slot_idx']} ({b.get('path', '??')}): {b['name']} (params_a len: {len(b.get('params_a', []))})")
    for b in blocks:
        if b["slot_idx"] == 4:
            params = b.get('params_a', [])
            if params:
                val = params[0]
                print(f" [+] Slot 4 ({b['name']}) - Parámetro 0: {val} (Tipo: {type(val).__name__})")
                return val
            else:
                print(" [!] El Slot 4 no tiene parámetros en params_a.")
                return None
    print(" [!] No se encontró el Slot 4.")
    return None

def send_test_packet(conn, channel, endpoint, session_quad, slot_idx, parameter_idx, float_val, length_offset):
    # Pack float to big-endian IEEE754 with 0x04 length tag
    val_bytes = [0xca, 0x04] + list(struct.pack('>f', float_val))
    
    packet = [
        0x00, 0x00, 0x00, 0x18, channel, 0x10, endpoint, 0x03, 0x00, "XX", 0x00, 0x04,
        session_quad[0], session_quad[1], session_quad[2], session_quad[3],
        0x01, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, # index 20 will be second_length_byte
        0x83, 0x66, 0xcd, 0x04, 0x34, 0x64, 0x4e, 0x65, 0x82, 0x62,
        slot_idx,
        0x1d, 0xc3, 0x1a, 0x00, 0x1c,
        parameter_idx
    ] + val_bytes
    
    # Recalculate lengths
    packet[0] = len(packet) - length_offset
    packet[20] = packet[0] - 16
    
    hex_str = ", ".join(f"0x{x:02x}" if isinstance(x, int) else str(x) for x in packet)
    print(f" -> Enviando a Canal {hex(channel)} / EP {hex(endpoint)}, Session {session_quad}, Offset -{length_offset}")
    conn.write(packet)

def main():
    print("====================================================")
    print(" Helix Native Parameter Write Diagnostic Tool")
    print("====================================================")
    
    conn = HelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        print("\n[+] Leyendo estado inicial...")
        blocks = conn.fetch_active_preset_blocks()
        initial_val = print_slot_4_param_0(blocks)
        
        # Test 1: Canal 0x02, EP 0xf0, Session ID x2 hardcoded, Offset 9
        print("\n--- TEST 1: Canal 0x02 / EP 0xf0 (UI channel) con Session ID fijo [0x09, 0x02, 0x00, 0x00] y Offset 9 ---")
        send_test_packet(conn, channel=0x02, endpoint=0xf0, session_quad=[0x09, 0x02, 0x00, 0x00], slot_idx=4, parameter_idx=0, float_val=-0.5, length_offset=9)
        time.sleep(0.6)
        blocks = conn.fetch_active_preset_blocks()
        print_slot_4_param_0(blocks)
        
        # Test 2: Canal 0x80, EP 0xed, Session ID activa, Offset 11
        print("\n--- TEST 2: Canal 0x80 / EP 0xed (Control channel) con Session ID activo y Offset 11 ---")
        active_quad = [conn.session_no, conn.preset_data_double_cnt[0], conn.preset_data_double_cnt[1], 0x00]
        send_test_packet(conn, channel=0x80, endpoint=0xed, session_quad=active_quad, slot_idx=4, parameter_idx=0, float_val=0.5, length_offset=11)
        time.sleep(0.6)
        blocks = conn.fetch_active_preset_blocks()
        print_slot_4_param_0(blocks)

        # Test 3: Canal 0x02, EP 0xf0, Session ID activa, Offset 9
        print("\n--- TEST 3: Canal 0x02 / EP 0xf0 con Session ID activo y Offset 9 ---")
        send_test_packet(conn, channel=0x02, endpoint=0xf0, session_quad=active_quad, slot_idx=4, parameter_idx=0, float_val=-0.2, length_offset=9)
        time.sleep(0.6)
        blocks = conn.fetch_active_preset_blocks()
        print_slot_4_param_0(blocks)
        
        # Test 4: Canal 0x80, EP 0xed, Session ID fijo [0xf4, 0x1e, 0x00, 0x00], Offset 11
        print("\n--- TEST 4: Canal 0x80 / EP 0xed con Session ID fijo [0xf4, 0x1e, 0x00, 0x00] y Offset 11 ---")
        send_test_packet(conn, channel=0x80, endpoint=0xed, session_quad=[0xf4, 0x1e, 0x00, 0x00], slot_idx=4, parameter_idx=0, float_val=0.2, length_offset=11)
        time.sleep(0.6)
        blocks = conn.fetch_active_preset_blocks()
        print_slot_4_param_0(blocks)
        
    except Exception as e:
        print(f"\n [!] Error crítico: {e}")
    finally:
        conn.disconnect()
        print("\nConexión cerrada. Diagnóstico completado.")

if __name__ == "__main__":
    main()
