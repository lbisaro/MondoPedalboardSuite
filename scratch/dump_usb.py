import struct
import sys

def parse_pcapng(filename, out_filename):
    try:
        from scapy.all import rdpcap, PcapReader
    except ImportError:
        print("Scapy not found")
        return

    out = open(out_filename, 'w')
    try:
        with PcapReader(filename) as pcap:
            packet_idx = 0
            for packet in pcap:
                packet_idx += 1
                # scapy might wrap the packet in a Raw layer, or it might just be the bytes
                raw = bytes(packet)
                if len(raw) < 28:
                    continue
                
                # USBPcap header is at least 27 bytes, typically 28
                # struct usbpcap_packet_header
                header_len = struct.unpack('<H', raw[0:2])[0]
                if header_len < 27 or header_len > len(raw):
                    continue
                
                endpoint = raw[22]
                transfer = raw[23]
                data_len = struct.unpack('<I', raw[24:28])[0]
                
                payload = raw[header_len:header_len+data_len]
                if not payload:
                    continue
                
                direction = "IN " if (endpoint & 0x80) else "OUT"
                ep_num = endpoint & 0x7F
                
                hex_payload = payload.hex()
                # break hex into 32 byte chunks for easier reading
                chunks = [hex_payload[i:i+64] for i in range(0, len(hex_payload), 64)]
                out.write(f"Packet {packet_idx:05d} [{direction} EP{ep_num}] len={data_len}:\n")
                for chunk in chunks:
                    out.write(f"  {chunk}\n")
                out.write("\n")
    except Exception as e:
        print(f"Error reading {filename}: {e}")
    finally:
        out.close()
        print(f"Dumped {filename} to {out_filename}")

if __name__ == "__main__":
    parse_pcapng("Accion1.pcapng", "scratch/accion1_dump.txt")
    parse_pcapng("Accion2.pcapng", "scratch/accion2_dump.txt")
