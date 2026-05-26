import sys
import os
import time
import struct
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)
repos_utils_dir = os.path.join(project_dir, "repos", "helix_usb")
if repos_utils_dir not in sys.path:
    sys.path.insert(1, repos_utils_dir)

from helix_connection import HelixConnection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("TestCombined")

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
    conn.connect()
    conn.perform_handshake()
    
    print("\n[1] Fetching blocks 1st time...")
    blocks1 = conn.fetch_active_preset_blocks()
    print(f"Blocks 1st time count: {len(blocks1)}")
    
    # Target slot 4
    target_slot_index = 4
    target_db = 5.0
    norm_val = (target_db - (-15.0)) / 30.0
    
    ctr_a = 0x6cbd
    yy_a = 0x17
    
    float_be_a = list(struct.pack('>f', norm_val))
    float_be_b = list(struct.pack('>f', target_db))
    
    slot_bus = 5
    pp = 3
    param_idx = 0
    
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
    
    # Focus packet cd:04
    focus_pkt_cd04 = [
        0x1d, 0x00, 0x00, 0x18,
        0x80, 0x10, 0xed, 0x03,
        0x00, "XX",  0x00, 0x04,
        conn.session_no, conn.preset_data_double_cnt[0], conn.preset_data_double_cnt[1], 0x00,
        0x01, 0x00, 0x06, 0x00,
        0x0d, 0x00, 0x00, 0x00,
        0x83, 0x66, 0xcd, 0x04,
        slot_bus, 0x64, 0x4e, 0x65,
        0x82, 0x62, slot_bus, 0x1a,
        0x00, 0x00, 0x00, 0x00,
    ]
    
    print("\n[2] Sending focus...")
    conn.write(focus_pkt_cd04)
    time.sleep(0.5) # Wait for device
    
    # If we captured model echo, apply it
    if conn.last_ed03_echo_model:
        print(f"Captured model echo: {[hex(x) for x in conn.last_ed03_echo_model]}")
        model_block_a = list(conn.last_ed03_echo_model)
        seq_a = (model_block_a[4] + 1) & 0xff
        model_block_a[4] = seq_a
        packet_a[24:40] = model_block_a
        
        model_block_b = list(conn.last_ed03_echo_model)
        seq_b = (seq_a + 1) & 0xff
        model_block_b[4] = seq_b
        packet_b[24:40] = model_block_b
    else:
        print("No model echo captured!")
        
    print("\n[3] Sending live write sequence...")
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
        
    print("\n[4] Sleeping 2.0s...")
    time.sleep(2.0)
    
    print("\n[5] Fetching blocks 2nd time...")
    blocks2 = conn.fetch_active_preset_blocks()
    print(f"Blocks 2nd time count: {len(blocks2)}")
    
    conn.disconnect()

if __name__ == '__main__':
    main()
