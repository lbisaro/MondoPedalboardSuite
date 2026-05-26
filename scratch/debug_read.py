import sys
import time
import logging
from helix_connection import HelixConnection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("DebugRead")

class DebugHelixConnection(HelixConnection):
    def _classify_and_queue(self, data):
        # Print raw packet details
        print(f"[RAW IN] Len: {len(data)} | Hex: {bytes(data).hex()}")
        # Call super method to process it as normal
        super()._classify_and_queue(data)

def main():
    conn = DebugHelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        print("\n=== REQUESTING PRESET INFO ===")
        info = conn.fetch_active_preset_info()
        print(f"Preset Info: {info}")
        
        print("\n=== REQUESTING PRESET BLOCKS ===")
        # We manually send the request packet and monitor what comes back
        # to see if the device is ignoring it, or sending it on a different format.
        conn.session_no = 0x55 # use a fixed session no for tracking
        request_preset_session_id = conn.request_preset_session_id
        conn.request_preset_session_id += 2
        
        preset_req_packet = [
            0x19, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03, 0x00, "XX", 0x00, 0x0c,
            conn.session_no, conn.preset_data_double_cnt[0], conn.preset_data_double_cnt[1], 0x00,
            0x01, 0x00, 0x06, 0x00, 0x09, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, 0x03, request_preset_session_id, 0x64, 0x16, 0x65, 0xc0, 0x00, 0x00, 0x00
        ]
        
        print(f"Sending preset request packet with session_no={conn.session_no}, double_cnt={conn.preset_data_double_cnt}")
        conn.write(preset_req_packet)
        
        # Wait 3 seconds to capture all responses
        time.sleep(3.0)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
