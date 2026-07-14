import struct
import sys

def birdseye(filename):
    try:
        from scapy.all import PcapReader
    except ImportError:
        print("Scapy not found")
        return

    try:
        with open("scratch/birdseye.txt", "w") as out:
            with PcapReader(filename) as pcap:
                packet_idx = 0
                start_time = None
                for packet in pcap:
                    packet_idx += 1
                    curr_time = float(packet.time)
                    if start_time is None: start_time = curr_time
                    
                    raw = bytes(packet)
                    if len(raw) >= 28:
                        header_len = struct.unpack('<H', raw[0:2])[0]
                        if 27 <= header_len <= len(raw):
                            data_len = struct.unpack('<I', raw[24:28])[0]
                            endpoint = raw[22]
                            if data_len > 0:
                                direction = "IN " if (endpoint & 0x80) else "OUT"
                                out.write(f"{packet_idx:04d}: T+{curr_time - start_time:06.2f}s {direction} {data_len} bytes\n")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    birdseye("Accion3.pcapng")
