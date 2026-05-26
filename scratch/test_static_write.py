import sys
import os
import time
import struct
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from helix_connection import HelixConnection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("TestStaticWrite")

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
    conn = HelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        print("\n[1] Reading preset blocks initially...")
        blocks = conn.fetch_active_preset_blocks()
        
        target_slot = 4
        param_idx = 0
        initial_val = None
        for b in blocks:
            if b["slot_idx"] == target_slot:
                params = b.get("params_a", [])
                if params:
                    initial_val = params[param_idx]
                    print(f" [+] Slot {target_slot} ({b['name']}) - Param {param_idx}: {initial_val} dB")
        
        target_db = 5.0
        if initial_val is not None and abs(initial_val - target_db) < 0.1:
            target_db = -2.5
            
        norm_val = (target_db - (-15.0)) / 30.0
        print(f"\n[2] Target value: {target_db} dB (normalized: {norm_val})")
        
        float_be_a = list(struct.pack('>f', norm_val))
        float_be_b = list(struct.pack('>f', target_db))
        
        slot_bus = 5
        pp = 3
        
        # Build sequence packets
        ctr_a = 0x6cbd
        yy_a = 0x17
        
        pre_packet_x80 = [
            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX", 0x00, 0x10, conn.session_no, conn.preset_data_double_cnt[0], conn.preset_data_double_cnt[1], 0x00
        ]
        
        pre_packet_x2 = [
            0x08, 0x00, 0x00, 0x18, 0x02, 0x10, 0xf0, 0x03,
            0x00, "XX", 0x00, 0x10, 0x09, 0x10, 0x00, 0x00
        ]
        
        pre_packet_x80_sel = [
            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX", 0x00, 0x08, ctr_a & 0xff, (ctr_a >> 8) & 0xff, 0x00, 0x00
        ]
        
        packet_a = assemble_27_write("XX", 0x04, ctr_a, yy_a, pp, param_idx, slot_bus, float_be_a)
        
        ctr_b = (ctr_a + 0x1f) & 0xffff
        yy_b = (yy_a + 1) & 0xff
        packet_b = assemble_27_write("XX", 0x0c, ctr_b, yy_b, pp, param_idx, slot_bus, float_be_b)
        
        ctr_post = (ctr_b + 0x1f) & 0xffff
        post_packet_x80_sel = [
            0x08, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03,
            0x00, "XX", 0x00, 0x08, ctr_post & 0xff, (ctr_post >> 8) & 0xff, 0x00, 0x00
        ]
        
        # Focus slot packet targeting Slot 4 (slot_bus = 5) - cd:04 style (HX Edit)
        focus_pkt_cd04 = [
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
        
        print("\n[3] Sending focus packet (this will be ACK'd by reader thread)...")
        conn.write(focus_pkt_cd04)
        time.sleep(0.3)
        
        print("\n[4] Sending uncorrupted parameter write sequence...")
        with conn.write_lock:
            conn.write(pre_packet_x80)
            time.sleep(0.006)
            conn.write(pre_packet_x2)
            time.sleep(0.010)
            conn.write(pre_packet_x80_sel)
            time.sleep(0.016)
            conn.write(packet_a)
            time.sleep(0.012)
            conn.write(packet_b)
            time.sleep(0.012)
            conn.write(post_packet_x80_sel)
            
        print(" [+] Waiting 2.0 seconds...")
        time.sleep(2.0)
        
        print("\n[5] Reading preset blocks again to verify change...")
        updated_blocks = conn.fetch_active_preset_blocks()
        final_val = None
        for b in updated_blocks:
            if b["slot_idx"] == target_slot:
                params = b.get("params_a", [])
                if params:
                    final_val = params[param_idx]
                    print(f" [+] Slot {target_slot} ({b['name']}) - Param {param_idx}: {final_val} dB")
                    
        if final_val is not None and abs(final_val - target_db) < 0.1:
            print("\n[SUCCESS] Parameter changed via static write!")
        else:
            print("\n[FAILURE] Parameter did not change.")
            
    except Exception as e:
        log.error(f"Error: {e}")
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
