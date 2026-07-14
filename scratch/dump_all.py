import struct
def dump_all():
    try:
        from scapy.all import PcapReader
        with PcapReader("Accion3.pcapng") as pcap:
            start_time = None
            for packet in pcap:
                curr_time = float(packet.time)
                if start_time is None: start_time = curr_time
                time_s = curr_time - start_time
                
                raw = bytes(packet)
                if len(raw) < 28: continue
                header_len = struct.unpack('<H', raw[0:2])[0]
                payload = raw[header_len:]
                if not payload: continue
                
                endpoint = raw[22]
                dir_str = "IN " if (endpoint & 0x80) else "OUT"
                if len(payload) > 20:
                    print(f"T+{time_s:06.2f}s {dir_str} len={len(payload)}")
    except Exception as e:
        print(e)
if __name__ == "__main__": dump_all()
