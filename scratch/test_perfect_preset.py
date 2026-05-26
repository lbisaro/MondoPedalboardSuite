import sys
import time
import struct
import random
import logging
from helix_connection import HelixConnection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("PerfectPreset")

class PerfectHelixConnection(HelixConnection):
    def __init__(self):
        super().__init__()
        # Initialize internal counters matching hxlinux
        self.editor_ed03_double = 0x64e7 # starts at PRESET_ED03_TRANSACTION_FIRST.wrapping_sub(1)
        self.preset_dump_ack_ctr = 0x119d # session=0x9d, ctr_bas=0x11
        self.ed03_cmd_type = 0x01
        self.preset_last_ack_double = [0, 0]
        
    def next_x80_cnt(self):
        self.x80_counter = (self.x80_counter + 1) & 0xff
        return self.x80_counter
        
    def next_editor_ed03_double(self):
        self.editor_ed03_double = (self.editor_ed03_double + 1) & 0xffff
        return [self.editor_ed03_double & 0xff, (self.editor_ed03_double >> 8) & 0xff]
        
    def next_preset_dump_ack_double(self):
        self.preset_dump_ack_ctr = (self.preset_dump_ack_ctr + 1) & 0xffff
        return [self.preset_dump_ack_ctr & 0xff, (self.preset_dump_ack_ctr >> 8) & 0xff]

    def download_preset_2phase(self):
        log.info("Starting 2-phase preset download...")
        
        # Clear event queue
        while not self.event_queue.empty():
            self.event_queue.get_nowait()
            
        self.session_no = random.randint(4, 250)
        sess1 = self.session_no
        double1 = self.preset_data_double_cnt
        sess_id1 = 0x04
        cmd_type = 0x04
        
        # Select random independent session for Phase 2
        phase2_session = max(4, random.randint(4, 250))
        
        log.info(f"Phase 1: session_no={hex(sess1)}, double1={[hex(x) for x in double1]}, sess_id1={hex(sess_id1)}, cmd_type={hex(cmd_type)}, phase2_session={hex(phase2_session)}")
        
        # Phase 1 packet: sub=0x04, requesting preset name/info
        phase1_pkt = [
            0x19, 0x00, 0x00, 0x18,
            0x80, 0x10, 0xed, 0x03,
            0x00, "XX",  0x00, 0x04,
            sess1, double1[0], double1[1], 0x00,
            0x01, 0x00, 0x06, 0x00,
            0x09, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, cmd_type,
            sess_id1, 0x64, 0x17, 0x65,
            0xc0, 0x00, 0x00, 0x00,
        ]
        
        self.write(phase1_pkt)
        
        # Send extra control packet on canal x1 (required by the device to trigger Phase 1 response)
        self.write([0x08, 0x00, 0x00, 0x18, 0x01, 0x10, 0xef, 0x03, 0x00, "XX", 0x00, 0x08, 0x72, 0x1e, 0x00, 0x00])
        
        # Wait for Phase 1 Response
        log.info("Waiting for Phase 1 response...")
        start_time = time.time()
        phase1_resp = None
        while time.time() - start_time < 3.0:
            try:
                evt_type, data = self.event_queue.get(timeout=0.1)
                log.info(f"Dequeued event: {evt_type}, len={len(data)}, hex={bytes(data)[:16].hex()}...")
                # Keep-alives can be received, let the thread handle it or we ignore them.
                if evt_type == "keep_alive_x1":
                    continue
                # Phase 1 response is typically preset_header or raw with sub=0x04, len >= 36
                if evt_type in ("preset_header", "raw") and len(data) >= 36 and data[4] == 0xed and data[6] == 0x80 and data[11] == 0x04:
                    phase1_resp = data
                    log.info(f"Phase 1 response matched! Len: {len(data)}")
                    break
            except Exception:
                continue
                
        if not phase1_resp:
            log.error("Failed to receive Phase 1 response!")
            return False
            
        # Parse active indices from Phase 1 response (similar to fetch_active_preset_info)
        idx_6b = 0
        idx_6c = 0
        preset_name = ""
        for i in range(len(phase1_resp) - 3):
            if phase1_resp[i] == 0x6b and phase1_resp[i+1] == 0xcd:
                idx_6b = phase1_resp[i+3]
            if phase1_resp[i] == 0x6c and phase1_resp[i+1] == 0xcd:
                idx_6c = phase1_resp[i+3]
                if i + 4 < len(phase1_resp) and phase1_resp[i+4] == 0x6d:
                    length_byte = phase1_resp[i+5]
                    strlen = length_byte - 0xa0 if length_byte >= 0xa0 else length_byte
                    if i + 6 + strlen <= len(phase1_resp):
                        name_bytes = bytes(phase1_resp[i+6 : i+6+strlen])
                        preset_name = name_bytes.split(b'\x00')[0].decode('ascii', errors='ignore').strip()
                        
        self.active_setlist_idx = idx_6b
        self.active_preset_idx_in_setlist = idx_6c
        self.preset_name = preset_name or "Desconocido"
        log.info(f"Preset detected: '{self.preset_name}' (Setlist: {self.active_setlist_idx}, Preset: {self.active_preset_idx_in_setlist})")
        
        # Send Phase 2
        double = self.next_editor_ed03_double()
        sess_id = 0xf4 # First Phase 2 request uses 0xf4
        
        log.info(f"Phase 2: session_no={hex(phase2_session)}, double={[hex(x) for x in double]}, sess_id={hex(sess_id)}")
        
        phase2_pkt = [
            0x19, 0x00, 0x00, 0x18,
            0x80, 0x10, 0xed, 0x03,
            0x00, "XX",  0x00, 0x0c,
            phase2_session, double[0], double[1], 0x00,
            0x01, 0x00, 0x06, 0x00,
            0x09, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, 0x03,
            sess_id, 0x64, 0x16, 0x65,
            0xc0, 0x00, 0x00, 0x00,
        ]
        
        self.write(phase2_pkt)
        
        # Download loop
        preset_data = bytearray()
        last_ack_double = [0, 0]
        completed = False
        start_time = time.time()
        
        while time.time() - start_time < 5.0:
            try:
                evt_type, data = self.event_queue.get(timeout=0.1)
                log.info(f"Phase 2 Dequeued event: {evt_type}, len={len(data)}, hex={bytes(data)[:16].hex()}...")
                if evt_type == "keep_alive_x1":
                    continue
                if len(data) >= 16 and data[4] == 0xed and data[6] == 0x80 and data[11] == 0x04:
                    # Check if FDT (end of transfer): length 32, sub=0x04, data[16] == 0xa1
                    if len(data) == 32 and data[16] == 0xa1:
                        log.info("FDT received! Completing transaction...")
                        # Send FDT ACK
                        cnt = self.next_x80_cnt()
                        fdt_session = (phase2_session + 0x10) & 0xff
                        fdt_ack = [
                            0x08, 0x00, 0x00, 0x18,
                            0x80, 0x10, 0xed, 0x03,
                            0x00, "XX", 0x00, 0x08,
                            fdt_session, last_ack_double[0], last_ack_double[1], 0x00,
                        ]
                        self.write(fdt_ack)
                        completed = True
                        break
                    
                    # Chunk received
                    chunk_payload = data[16:]
                    preset_data.extend(chunk_payload)
                    
                    # Send ACK
                    new_double = self.next_preset_dump_ack_double()
                    chunk_ack = [
                        0x08, 0x00, 0x00, 0x18,
                        0x80, 0x10, 0xed, 0x03,
                        0x00, "XX", 0x00, 0x08,
                        phase2_session, new_double[0], new_double[1], 0x00,
                    ]
                    self.write(chunk_ack)
                    last_ack_double = new_double
                    
                    # If this chunk was partial (< 256 bytes payload), it's also completion
                    if len(chunk_payload) < 256:
                        log.info("Received partial chunk. Completing transaction...")
                        completed = True
                        break
            except Exception as e:
                continue
                
        if completed:
            self.session_no = (phase2_session + 0x10) & 0xff
            self.ed03_cmd_type = (self.ed03_cmd_type + 1) & 0xff
            self.preset_last_ack_double = last_ack_double
            log.info(f"Preset successfully downloaded. Total size: {len(preset_data)} bytes. Session aligned to {hex(self.session_no)}")
            
            # Save data to cache file to parse blocks
            hex_str = preset_data.hex()
            # Try parsing blocks using HxPreset
            try:
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                # Ensure utils/ is in path
                utils_dir = os.path.join(os.path.dirname(current_dir), "utils")
                if utils_dir not in sys.path:
                    sys.path.insert(0, utils_dir)
                    
                from utils.preset_parser import HxPreset
                hx_preset = HxPreset(data_in=hex_str, preset_name=self.preset_name)
                
                blocks = []
                for idx, slot in enumerate(hx_preset.slot_info):
                    st = getattr(slot, 'slot_type', 0x08)
                    if st == 0x08:
                        continue
                    if st in (0x06, 0x07):
                        names = slot.id_to_names()
                        if names[0] != '' or names[1] != '':
                            blocks.append({
                                "slot_idx": idx,
                                "name": names[0],
                                "params": getattr(slot, 'parameter_a', [])
                            })
                log.info(f"Parsed {len(blocks)} active blocks:")
                for b in blocks:
                    log.info(f"  Slot {b['slot_idx']}: {b['name']} (Params: {b['params']})")
                return blocks
            except Exception as pe:
                log.error(f"Error parsing preset blocks: {pe}")
                return True
        else:
            log.error("Preset download transaction failed or timed out.")
            # Reset
            self.editor_ed03_double = 0x64e7
            self.preset_last_ack_double = [0, 0]
            self.request_preset_session_id = 0xf4
            return False

def main():
    conn = PerfectHelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        blocks = conn.download_preset_2phase()
        if not blocks:
            print("Failed to download blocks.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
