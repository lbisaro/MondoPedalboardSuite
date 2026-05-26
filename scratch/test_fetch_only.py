import sys
import time
import logging
from helix_connection import HelixConnection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("TestFetch")

def main():
    conn = HelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        print("\n[+] Calling fetch_active_preset_info()...")
        info = conn.fetch_active_preset_info()
        print(f"[+] Result: {info}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
