import struct
import sys

def extract_isolated(filename):
    try:
        from scapy.all import PcapReader
    except ImportError:
        print("Scapy not found")
        return

    try:
        with PcapReader(filename) as pcap:
            prev_time = None
            packet_idx = 0
            
            phase = 0 # 0=initial, 1=after first pause (the action), 2=after second pause
            
            for packet in pcap:
                packet_idx += 1
                curr_time = float(packet.time)
                raw = bytes(packet)
                
                delta = 0.0
                if prev_time is not None:
                    delta = curr_time - prev_time
                    if delta > 2.0:
                        phase += 1
                        print(f"\n======================================")
                        print(f"--- PAUSE OF {delta:.2f} SECONDS (Entering Phase {phase}) ---")
                        print(f"======================================\n")
                
                if phase == 1:
                    if len(raw) >= 28:
                        header_len = struct.unpack('<H', raw[0:2])[0]
                        if 27 <= header_len <= len(raw):
                            endpoint = raw[22]
                            data_len = struct.unpack('<I', raw[24:28])[0]
                            payload = raw[header_len:header_len+data_len]
                            if payload:
                                direction = "IN " if (endpoint & 0x80) else "OUT"
                                ep_num = endpoint & 0x7F
                                hex_payload = payload.hex()
                                print(f"Packet {packet_idx:05d} [+{delta:.3f}s] [{direction} EP{ep_num}] len={data_len}: {hex_payload}")
                
                prev_time = curr_time
                
    except Exception as e:
        print(f"Error reading {filename}: {e}")

if __name__ == "__main__":
    extract_isolated("Accion3.pcapng")
