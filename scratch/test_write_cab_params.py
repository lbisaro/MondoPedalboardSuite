import time
import sys
import os

# Add parent directory to path so we can import helix_connection
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helix_connection import HelixConnection

def main():
    conn = HelixConnection()
    ok, msg = conn.connect()
    if not ok:
        print("Error:", msg)
        return

    print("Connected. Performing handshake...")
    conn.perform_handshake()

    ok, blocks = conn.fetch_active_preset_blocks()
    if not ok:
        print("Error fetching blocks:", blocks)
        return

    cab_block = None
    for b in blocks:
        if b.get('category') == 'Cab':
            cab_block = b
            break

    if not cab_block:
        print("No Cab block found in the current preset.")
        return

    slot_idx = cab_block['slot_idx']
    print(f"Found Cab block at slot {slot_idx}")

    # The user's target parameters:
    # 0: Mic (0)
    # 1: Position (0.24)
    # 2: Distance (1.0)
    # 3: Angle (0.0)
    # 4: LowCut (70.0)
    # 5: HighCut (11000.0)
    # 6: Level (0.0)
    
    targets = [
        {"raw": 0.0, "norm": 0.0 / 15.0},                 # Mic (0 to 15)
        {"raw": 0.24, "norm": 0.24 / 10.0},               # Position (0 to 10)
        {"raw": 1.0, "norm": (1.0 - 1.0) / 11.0},         # Distance (1 to 12 -> range 11)
        {"raw": 0.0, "norm": 0.0 / 1.0},                  # Angle (enum: 0 or 45, max index is 1)
        {"raw": 70.0, "norm": (70.0 - 0.0) / 500.0},      # Low Cut (0 to 500 -> range 500)
        {"raw": 11000.0, "norm": (11000.0 - 500.0) / 19600.0}, # High Cut (500 to 20100 -> range 19600)
        {"raw": 0.0, "norm": 0.0 / 10.0}                  # Level (0 to 10 -> range 10)
    ]

    print("Writing parameters...")
    for idx, target in enumerate(targets):
        raw = target["raw"]
        norm = target["norm"]
        print(f"  -> Setting param {idx}: RAW={raw:.2f}, NORM={norm:.4f}")
        
        ok, msg = conn.write_block_parameter(slot_idx, idx, target_db=raw, norm_val=norm)
        if not ok:
            print(f"     [Error]: {msg}")
        else:
            print("     [OK]")
            
        time.sleep(0.05) # Small pause between parameter writes to avoid saturating

    print("Done writing parameters.")
    
if __name__ == '__main__':
    main()
