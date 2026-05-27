import sys
import time
import struct
import random
import logging
import os
import threading

# Path setup to import project modules properly
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = current_dir
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)
repos_utils_dir = os.path.join(project_dir, "repos", "helix_usb")
if repos_utils_dir not in sys.path:
    sys.path.insert(1, repos_utils_dir)

from helix_connection import HelixConnection
from utils.preset_parser import HxPreset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("PerfectWrite")

class PerfectHelixConnection(HelixConnection):
    def __init__(self):
        super().__init__()
        # Use Reentrant Lock to allow nesting with conn.write() inside main thread
        self.write_lock = threading.RLock()
        
        self.editor_ed03_double = 0x64e7
        self.preset_dump_ack_ctr = 0x119d
        self.ed03_cmd_type = 0x01
        self.preset_last_ack_double = [0, 0]
        
        # Live write counters
        self.live_write_ctr = 0x6cbd
        self.live_write_yy = 0x17
        self.ed03_live_write_seq_sent = None
        
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
        self.capture_model_echoes = False
        try:
            res = self._download_preset_2phase_impl()
        finally:
            self.capture_model_echoes = True
        return res

    def _download_preset_2phase_impl(self):
        log.info("Starting 2-phase preset download...")
        while not self.event_queue.empty():
            self.event_queue.get_nowait()
            
        self.session_no = random.randint(4, 250)
        sess1 = self.session_no
        double1 = self.preset_data_double_cnt
        sess_id1 = 0x04
        cmd_type = 0x04
        phase2_session = max(4, random.randint(4, 250))
        
        # Phase 1 packet: sub=0x04
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
        self.write([0x08, 0x00, 0x00, 0x18, 0x01, 0x10, 0xef, 0x03, 0x00, "XX", 0x00, 0x08, 0x72, 0x1e, 0x00, 0x00])
        
        # Wait for Phase 1 Response
        start_time = time.time()
        phase1_resp = None
        while time.time() - start_time < 3.0:
            try:
                evt_type, data = self.event_queue.get(timeout=0.1)
                if evt_type == "keep_alive_x1":
                    continue
                if evt_type in ("preset_header", "raw") and len(data) >= 36 and data[4] == 0xed and data[6] == 0x80 and data[11] == 0x04:
                    phase1_resp = data
                    break
            except Exception:
                continue
                
        if not phase1_resp:
            log.error("Failed to receive Phase 1 response!")
            return None
            
        # Parse active indices from Phase 1 response
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
        
        # Send Phase 2
        double = self.next_editor_ed03_double()
        sess_id = 0xf4
        
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
                if evt_type == "keep_alive_x1":
                    continue
                if len(data) >= 16 and data[4] == 0xed and data[6] == 0x80 and data[11] == 0x04:
                    if len(data) == 32 and data[16] == 0xa1:
                        # Send FDT ACK
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
                    
                    if len(chunk_payload) < 256:
                        completed = True
                        break
            except Exception:
                continue
                
        if completed:
            self.session_no = (phase2_session + 0x10) & 0xff
            self.ed03_cmd_type = (self.ed03_cmd_type + 1) & 0xff
            self.preset_last_ack_double = last_ack_double
            
            # Parse blocks using HxPreset
            hex_str = preset_data.hex()
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
            return blocks
        else:
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

def get_slot_param(blocks, slot_index, param_idx=0):
    """Return the parameter value for a given slot index.
    Parameters
    ----------
    blocks: list of dict
        Parsed block list returned by fetch_active_preset_blocks().
    slot_index: int
        Zero‑based slot number (0‑39).
    param_idx: int, optional
        Index of the parameter inside the block (default 0 – first band).
    Returns
    -------
    float or None
        Parameter value in dB if found, otherwise None.
    """
    if not blocks:
        print(" [!] No block list received.")
        return None
    for b in blocks:
        if b["slot_idx"] == slot_index:
            params = b.get('params', b.get('params_a', []))
            if params:
                val = params[param_idx]
                print(f" [+] Slot {slot_index} ({b['name']}) - Parameter {param_idx}: {val} dB")
                return val
            else:
                print(f" [!] Slot {slot_index} does not have parameters.")
                return None
    print(f" [!] Slot {slot_index} not found in active preset blocks.")
    return None

def main():
    conn = PerfectHelixConnection()
    try:
        success, msg = conn.connect()
        if not success:
            print(f" [!] Error al conectar: {msg}")
            return
        conn.perform_handshake()
        
        # 1. Download initial preset layout
        print("\n[+] Downloading initial preset blocks...")
        success, res = conn.fetch_active_preset_blocks()
        if not success:
            print(f" [!] Error al leer bloques: {res}")
            return
        blocks = res
        print(" [+] Blocks found in preset:")
        for b in blocks:
            print(f"   - Slot {b['slot_idx']}: {b['name']}")
        # Target the actual Graphic EQ slot based on CLI args (default to 4)
        target_slot_index = int(sys.argv[1]) if len(sys.argv) > 1 else 4
        initial_val = get_slot_param(blocks, target_slot_index, param_idx=0)
        
        # 2. Prepare live write sequence
        target_db = 5.0
        norm_val = (target_db - (-15.0)) / 30.0
        if initial_val is not None and abs(initial_val - target_db) < 0.1:
            target_db = -2.5
            norm_val = (target_db - (-15.0)) / 30.0
            
        print(f"\n[+] Writing parameter change: Target = {target_db} dB (Norm = {norm_val})")
        
        # Counter management
        ctr_a = conn.live_write_ctr
        yy_a = conn.live_write_yy
        
        float_be_a = list(struct.pack('>f', norm_val))
        float_be_b = list(struct.pack('>f', target_db))
        
        # Usa directamente el índice proporcionado sin sumarle offset
        slot_bus = target_slot_index
        pp = 3 # Graphic EQ uses default pp = 3
        param_idx = 0 # 31.25Hz EQ band
        
        # Build raw frame list
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
        
        # Next counters for leg B
        ctr_b = (ctr_a + 0x1f) & 0xffff
        yy_b = (yy_a + 1) & 0xff
        
        packet_b = assemble_27_write("XX", 0x0c, ctr_b, yy_b, pp, param_idx, slot_bus, float_be_b)
        
        # Post-packet counter
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
        
        # Focus slot packet targeting Slot 4 (slot_bus = 5) - cd:03 style (hxlinux)
        focus_pkt_cd03 = [
            0x1d, 0x00, 0x00, 0x18,
            0x80, 0x10, 0xed, 0x03,
            0x00, "XX",  0x00, 0x04,
            conn.session_no, conn.preset_data_double_cnt[0], conn.preset_data_double_cnt[1], 0x00,
            0x01, 0x00, 0x06, 0x00,
            0x0d, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, 0x03,   # Variante cd:03
            0xf9, 0x64, 0x4e, 0x65,   # 0xf9 tag
            0x82, 0x62, slot_bus, 0x1a,
            0x00, 0x00, 0x00, 0x00,
        ]
        
        # Clear last echo model to ensure we capture a new one from the focus command
        conn.last_ed03_echo_model = None
        
        # Try cd:04 focus first
        log.info(f"Sending focus slot packet cd:04 for slot_bus {slot_bus}...")
        conn.write(focus_pkt_cd04)
        
        # Wait up to 250ms for a new echo model
        start_focus_wait = time.time()
        while conn.last_ed03_echo_model is None and (time.time() - start_focus_wait) < 0.25:
            time.sleep(0.01)
            
        if conn.last_ed03_echo_model is None:
            # If cd:04 failed, try cd:03 focus
            log.info(f"cd:04 did not return echo. Trying focus slot packet cd:03 for slot_bus {slot_bus}...")
            conn.write(focus_pkt_cd03)
            
            # Wait up to 250ms more
            start_focus_wait = time.time()
            while conn.last_ed03_echo_model is None and (time.time() - start_focus_wait) < 0.25:
                time.sleep(0.01)
                
        if conn.last_ed03_echo_model:
            log.info(f"SUCCESS: Captured slot focus model echo: {[hex(x) for x in conn.last_ed03_echo_model]}")
            
            # Leg A
            model_block_a = list(conn.last_ed03_echo_model)
            seq_a = (model_block_a[4] + 1) & 0xff
            packet_a[28] = seq_a
            
            # Leg B
            seq_b = (seq_a + 1) & 0xff
            packet_b[28] = seq_b
            
            conn.live_write_yy = (seq_b + 1) & 0xff
        else:
            log.warning("Slot focus model echo not received from hardware. Using default static replay.")
            
        # Send the 6-packet live write sequence under the reentrant write lock!
        log.info("Acquiring reentrant write lock and sending sequence...")
        with conn.write_lock:
            conn.write(pre_packet_x80)
            time.sleep(0.006)   # 6 ms (increased)
            conn.write(pre_packet_x2)
            time.sleep(0.010)   # 10 ms (increased)
            conn.write(pre_packet_x80_sel)
            time.sleep(0.016)   # 16 ms (increased)
            conn.write(packet_a)
            time.sleep(0.012)   # 12 ms (increased)
            conn.write(packet_b)
            time.sleep(0.012)   # 12 ms (increased)
            conn.write(post_packet_x80_sel)
            
            # Restore original focus to prevent slot shift
            # If we don't want to leave the focus stuck on the newly edited slot,
            # we can restore it to the slot the user originally had selected.
            # But since we don't read the original focus before writing, let's just 
            # ensure we don't advance the focus. We can leave it on target_slot_index.
            # Wait! The user says "el foco en la pantalla cambia al bloque 6" because the script
            # was hardcoded to target_slot_index = 5 (slot_bus = 6).
            # We don't necessarily need to shift it back if we target the correct slot.
            # But let's restore focus to the intended slot_bus just in case the write sequence moved it.
            restore_focus_pkt = focus_pkt_cd04.copy()
            restore_focus_pkt[28] = slot_bus
            restore_focus_pkt[34] = slot_bus
            log.info(f"Ensuring focus remains on slot_bus {slot_bus}...")
            conn.write(restore_focus_pkt)
            time.sleep(0.010)
            
        # Advance counters in our state
        conn.live_write_ctr = (ctr_post + 0x1f) & 0xffff
        if not conn.last_ed03_echo_model:
            conn.live_write_yy = (yy_b + 1) & 0xff
            
        # Wait 1.0 second and download preset blocks again to read back the value
        # Wait longer to allow device to process write and update state
        time.sleep(2.0)  # increased from 1.0 s to 2.0 s for reliability
        print("\n[+] Downloading preset blocks again to verify change...")
        success, res = conn.fetch_active_preset_blocks()
        updated_blocks = res if success else None
        final_val = get_slot_param(updated_blocks, target_slot_index, param_idx=0)
        
        if final_val is not None and abs(final_val - target_db) < 0.1:
            print("\n====================================================")
            print(" [SUCCESS] REAL-TIME PARAMETER WRITE CONFIRMED!")
            print(f" Value successfully changed to {final_val} dB via Native USB!")
            print("====================================================")
        else:
            print("\n====================================================")
            print(" [FAILURE] The parameter value did not change.")
            print("====================================================")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
