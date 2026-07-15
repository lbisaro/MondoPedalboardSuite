import struct
from scapy.all import rdpcap

def analyze_pcap():
    print("Analizando PruebaDefinitiva.pcapng...")
    packets = rdpcap("PruebaDefinitiva.pcapng")
    first_time = None
    
    with open("scratch/prueba_out_fixed.txt", "w") as f:
        for pkt in packets:
            if not pkt.haslayer("Raw"):
                continue
                
            raw = bytes(pkt.getlayer("Raw").load)
            if first_time is None:
                first_time = pkt.time
            t = pkt.time - first_time
                
            if len(raw) >= 28:
                header_len = struct.unpack('<H', raw[0:2])[0]
                if 27 <= header_len <= len(raw):
                    irp_info = raw[16]
                    endpoint = raw[22]
                    data_len = struct.unpack('<I', raw[24:28])[0]
                    payload = raw[header_len:header_len+data_len]
                    
                    # In USBpcap, direction is in irp_info bit 0
                    is_in = (irp_info & 0x01) != 0
                    ep_num = endpoint & 0x7F
                    
                    if len(payload) > 16:
                        direction = "IN " if is_in else "OUT"
                        hex_str = payload.hex()
                        f.write(f"T+{t:06.2f}s {direction} EP{ep_num} len={len(payload):<3} : {hex_str}\n")

if __name__ == "__main__":
    analyze_pcap()
