import sys
import time

sys.path.append(r"c:\Users\lbisa\OneDrive\Documentos\soft\Line 6\MondoPedalboardSuite")
from helix_connection import HelixConnection

def main():
    conn = HelixConnection()
    try:
        conn.connect()
        conn.perform_handshake()
        
        # Limpiar cola
        while not conn.event_queue.empty():
            conn.event_queue.get_nowait()
            
        print("Solicitando preset...")
        conn.session_no = 0x44
        # Petición de preset
        conn.write([
            0x19, 0x00, 0x00, 0x18, 0x80, 0x10, 0xed, 0x03, 0x00, 0x04, 0x00, 0x04,
            conn.session_no, 0x1e, 0x00, 0x00, 0x01, 0x00, 0x06, 0x00, 0x09, 0x00, 0x00, 0x00,
            0x83, 0x66, 0xcd, 0x04, 0x04, 0x64, 0x17, 0x65, 0xc0, 0x00, 0x00, 0x00
        ])
        conn.write([0x08, 0x00, 0x00, 0x18, 0x01, 0x10, 0xef, 0x03, 0x00, 0x03, 0x00, 0x08, 0x72, 0x1e, 0x00, 0x00])
        
        # Esperar y capturar el preset_header
        header = conn.wait_for_event("preset_header", timeout=5.0)
        print("\n=== PRESET HEADER BYTES ===")
        print("Hex:", bytes(header).hex())
        
        # Decodificar ASCII visible
        decoded = "".join(chr(b) if 32 <= b <= 126 else "." for b in header)
        print("ASCII:", decoded)
        
        # Analizar campos estructurados
        print("\nCampos decodificados en el header:")
        for i in range(len(header) - 1):
            val = header[i]
            # Buscar strings (longitudes entre 0xa0 y 0xff)
            if 0xa0 <= val <= 0xff:
                strlen = val - 0xa0
                if i + 1 + strlen <= len(header):
                    str_bytes = header[i+1 : i+1+strlen]
                    try:
                        s = str_bytes.decode('ascii', errors='ignore')
                        if any(c.isalnum() for c in s):
                            print(f"Index {i} (tag? 0x{header[i-2]:02x} 0x{header[i-1]:02x}): length={strlen}, string='{s}'")
                    except Exception:
                        pass
                        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.disconnect()

if __name__ == "__main__":
    main()
