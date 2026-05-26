import sys
import os
import time
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from helix_connection import HelixConnection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("TestChangeParameter")

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
        
        target_val = 5.0
        if initial_val is not None and abs(initial_val - target_val) < 0.1:
            target_val = -2.5
            
        print(f"\n[2] Modifying Slot {target_slot} Param {param_idx} to {target_val} dB using change_parameter...")
        conn.change_parameter(target_slot, param_idx, target_val)
        
        print(" [+] Waiting 1.0 second...")
        time.sleep(1.0)
        
        print("\n[3] Reading preset blocks again to verify change...")
        updated_blocks = conn.fetch_active_preset_blocks()
        final_val = None
        for b in updated_blocks:
            if b["slot_idx"] == target_slot:
                params = b.get("params_a", [])
                if params:
                    final_val = params[param_idx]
                    print(f" [+] Slot {target_slot} ({b['name']}) - Param {param_idx}: {final_val} dB")
                    
        if final_val is not None and abs(final_val - target_val) < 0.1:
            print("\n[SUCCESS] Parameter changed via change_parameter!")
        else:
            print("\n[FAILURE] Parameter did not change.")
            
    except Exception as e:
        log.error(f"Error: {e}")
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
