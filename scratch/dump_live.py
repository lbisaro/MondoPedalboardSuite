import struct
import sys

def parse_pcapng(filename):
    try:
        from scapy.all import PcapReader
    except ImportError:
        return

    out = []
    try:
        with PcapReader(filename) as pcap:
            packet_idx = 0
            start_time = None
            for packet in pcap:
                packet_idx += 1
                curr_time = float(packet.time)
                if start_time is None: start_time = curr_time
                
                raw = bytes(packet)
                if len(raw) < 28:
                    continue
                
                header_len = struct.unpack('<H', raw[0:2])[0]
                if header_len < 27 or header_len > len(raw):
                    continue
                
                endpoint = raw[22]
                payload = raw[header_len:]
                if not payload:
                    continue
                
                direction = "IN " if (endpoint & 0x80) else "OUT"
                ep_num = endpoint & 0x7F
                
                out.append({
                    "time": curr_time - start_time,
                    "dir": direction,
                    "ep": ep_num,
                    "len": len(payload),
                    "data": payload
                })
    except Exception as e:
        print(f"Error: {e}")
        
    return out

def analyze():
    packets = parse_pcapng("Accion3.pcapng")
    if not packets: return
    
    for p in packets:
        # Ignore keepalive-like traffic which is very small or very frequent.
        # Helix usually sends keepalives of len 10 or 12.
        # We look for packets after 3 seconds to skip handshake.
        if p["time"] > 4.0:
            if p["dir"] == "OUT":
                print(f"T+{p['time']:06.2f}s {p['dir']} EP{p['ep']} len={p['len']}: {p['data'].hex()}")

if __name__ == "__main__":
    analyze()
