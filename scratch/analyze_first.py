import sys
from scapy.all import PcapReader

def analyze():
    print("Leyendo Accion3.pcapng")
    count = 0
    with PcapReader("Accion3.pcapng") as pcap_reader:
        for packet in pcap_reader:
            count += 1
            if count == 1:
                packet.show()
                break

if __name__ == "__main__":
    analyze()
