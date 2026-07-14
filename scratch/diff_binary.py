def load_packets(filename):
    packets = []
    with open(filename, 'r') as f:
        content = f.read()
    
    for p in content.split("Packet "):
        if not p.strip(): continue
        lines = p.split('\n')
        header = lines[0]
        hex_data = "".join(l.strip() for l in lines[1:])
        try:
            raw_bytes = bytes.fromhex(hex_data)
            packets.append({"header": header, "data": raw_bytes})
        except:
            pass
    return packets

def compare():
    p1 = load_packets("scratch/accion1_dump.txt")
    p2 = load_packets("scratch/accion2_dump.txt")
    
    size_map1 = {}
    for p in p1:
        l = len(p["data"])
        if l not in size_map1: size_map1[l] = []
        size_map1[l].append(p)
        
    size_map2 = {}
    for p in p2:
        l = len(p["data"])
        if l not in size_map2: size_map2[l] = []
        size_map2[l].append(p)
        
    for l, list1 in size_map1.items():
        if l > 30 and l in size_map2:
            list2 = size_map2[l]
            for idx1, pkt1 in enumerate(list1):
                d1 = pkt1["data"]
                best_match = None
                best_diff_count = 999999
                
                for idx2, pkt2 in enumerate(list2):
                    d2 = pkt2["data"]
                    if d1 == d2:
                        best_diff_count = 0
                        break
                    
                    # count diffs ignoring offsets 9, 12, 13
                    diffs = 0
                    for i in range(l):
                        if i in (9, 12, 13, 26, 27): continue # ignoring possible sequence/timestamp bytes
                        if d1[i] != d2[i]:
                            diffs += 1
                            
                    if diffs < best_diff_count:
                        best_diff_count = diffs
                        best_match = pkt2
                
                # We want packets that have AT LEAST 1 real diff, but less than say 500 (meaning they are the same packet type)
                if best_match and 0 < best_diff_count < 500:
                    d2 = best_match["data"]
                    print(f"Interesting Diff in packet of size {l} (Real Diff count: {best_diff_count})")
                    print(f"  A1 Header: {pkt1['header']}")
                    print(f"  A2 Header: {best_match['header']}")
                    for i in range(l):
                        if i in (9, 12, 13, 26, 27) and d1[i] != d2[i]: continue
                        if d1[i] != d2[i]:
                            print(f"    Offset {i:04X}: A1={d1[i]:02X} A2={d2[i]:02X}")
                    print("-" * 40)

if __name__ == "__main__":
    compare()
