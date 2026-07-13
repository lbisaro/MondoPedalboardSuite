import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helix_connection import HelixConnection

def main():
    conn = HelixConnection()
    ok, msg = conn.connect()
    if not ok:
        print("Error:", msg)
        return

    conn.perform_handshake()

    ok, blocks = conn.fetch_active_preset_blocks()
    cab_block = next((b for b in blocks if b.get('category') == 'Cab'), None)
    
    if not cab_block:
        print("No Cab block found.")
        return

    slot_idx = cab_block['slot_idx']
    import json
    print(f"Original Cab Params for {cab_block['name']}: {json.dumps(cab_block, indent=2)}")
    
    # Try to write HighCut (index 5 for normal, index 2 for legacy)
    # Let's write Mic (index 0 for normal) to 57 Dynamic (RAW 0.0)
    
    idx = 0
    raw_val = 0.0
    norm_val = 0.0
    
    print(f"Writing param {idx} to {raw_val} (norm: {norm_val})")
    ok, msg = conn.write_block_parameter(slot_idx, idx, target_db=raw_val, norm_val=norm_val, is_int=True)
    print("Write result:", ok, msg)
    
    time.sleep(1)
    
    ok, blocks2 = conn.fetch_active_preset_blocks()
    cab_block2 = next((b for b in blocks2 if b.get('slot_idx') == slot_idx), None)
    print(f"New Cab Params: {cab_block2.get('params_a')}")

if __name__ == '__main__':
    main()
