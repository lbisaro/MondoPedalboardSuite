from scapy.all import rdpcap
import struct

def check_directions():
    packets = rdpcap("Accion3.pcapng")
    count = 0
    for pkt in packets:
        if pkt.haslayer("Raw"):
            raw = bytes(pkt.getlayer("Raw").load)
            if len(raw) >= 28:
                header_len = struct.unpack('<H', raw[0:2])[0]
                if 27 <= header_len <= len(raw):
                    endpoint = raw[22]
                    ep_num = endpoint & 0x7F
                    is_in = (endpoint & 0x80) != 0
                    
                    data_len = struct.unpack('<I', raw[24:28])[0]
                    payload = raw[header_len:header_len+data_len]
                    
                    if len(payload) > 16:
                        direction = "IN " if is_in else "OUT"
                        print(f"{direction} EP{ep_num} len={len(payload)} : {payload[:8].hex()}")
                        
        count += 1
        if count > 20:
            break

if __name__ == "__main__":
    try:
        check_directions()
    except Exception as e:
        print(e)
