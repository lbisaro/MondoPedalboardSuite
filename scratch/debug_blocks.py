import sys
import os
import random

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)
repos_utils_dir = os.path.join(project_dir, "repos", "helix_usb")
if repos_utils_dir not in sys.path:
    sys.path.insert(1, repos_utils_dir)

from helix_connection import HelixConnection

def main():
    conn = HelixConnection()
    conn.connect()
    conn.perform_handshake()
    
    print("\n[+] Solicitando preset...")
    
    # Limpiar cola de eventos antes de empezar
    while not conn.event_queue.empty():
        conn.event_queue.get_nowait()
        
    new_session_no = random.randint(4, 250)
    conn.session_no = new_session_no
    
    request_preset_session_id = conn.request_preset_session_id
    conn.request_preset_session_id = (request_preset_session_id + 2) & 0xff
    
    preset_req_packet = [
        0x19, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03, 0x00, "XX", 0x00, 0x0c,
        new_session_no, conn.preset_data_double_cnt[0], conn.preset_data_double_cnt[1], 0x00,
        0x01, 0x00, 0x06, 0x00, 0x09, 0x00, 0x00, 0x00,
        0x83, 0x66, 0xcd, 0x03, request_preset_session_id, 0x64, 0x16, 0x65, 0xc0, 0x00, 0x00, 0x00
    ]
    conn.write(preset_req_packet)
    
    # Wait for chunks and print headers
    import time
    start_time = time.time()
    while time.time() - start_time < 3.0:
        try:
            evt_type, data = conn.event_queue.get(timeout=0.1)
            if evt_type in ("preset_chunk", "raw"):
                pkt = list(data)
                if len(pkt) >= 16 and pkt[4] == 0xed and pkt[6] == 0x80:
                    print(f"Chunk received: len={len(pkt)}, header={[hex(x) for x in pkt[:16]]}, new_session_no={hex(new_session_no)}")
        except Exception:
            continue
            
    conn.disconnect()

if __name__ == '__main__':
    main()
