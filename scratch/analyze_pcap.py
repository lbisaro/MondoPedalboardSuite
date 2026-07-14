import sys
import os

try:
    from scapy.all import rdpcap, PcapReader
except ImportError as e:
    print(f"Error importing scapy: {e}")
    sys.exit(1)

def analyze(file_path):
    print(f"Analyzing {file_path}")
    count = 0
    try:
        with PcapReader(file_path) as pcap_reader:
            for packet in pcap_reader:
                count += 1
                if count <= 5:
                    print(f"Packet {count}:")
                    print(packet.summary())
                    packet.show()
                else:
                    break
    except Exception as e:
        print(f"Error reading pcap: {e}")

if __name__ == "__main__":
    analyze("Accion1.pcapng")
