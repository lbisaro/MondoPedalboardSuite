from scapy.all import rdpcap
import struct

def analyze_accion3():
    print("Analizando Accion3.pcapng con scapy...")
    packets = rdpcap("Accion3.pcapng")
    
    first_time = None
    
    with open("scratch/accion3_out.txt", "w") as f:
        for pkt in packets:
            if not pkt.haslayer("Raw"):
                continue
                
            raw = bytes(pkt.getlayer("Raw").load)
            
            if first_time is None:
                first_time = pkt.time
                
            t = pkt.time - first_time
            if t < 20.0:
                continue
                
            if len(raw) >= 28:
                header_len = struct.unpack('<H', raw[0:2])[0]
                if 27 <= header_len <= len(raw):
                    endpoint = raw[20]
                    data_len = struct.unpack('<I', raw[22:26])[0]
                    payload = raw[header_len:header_len+data_len]
                    
                    is_in = (endpoint & 0x80) != 0
                    ep_num = endpoint & 0x7F
                    
                    if len(payload) > 16:
                        direction = "IN " if is_in else "OUT"
                        hex_str = payload.hex()
                        f.write(f"T+{t:06.2f}s {direction} EP{ep_num} len={len(payload):<3} : {hex_str}\n")

if __name__ == "__main__":
    analyze_accion3()
