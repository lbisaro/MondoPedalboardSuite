import re

def find_ascii(filename, out_filename):
    print(f"==== Extracting ASCII from {filename} ====")
    with open(filename, 'r') as f:
        content = f.read()
    
    with open(out_filename, 'w', encoding='utf-8') as out:
        packets = content.split("Packet ")
        for p in packets:
            if not p.strip(): continue
            lines = p.split('\n')
            header = lines[0]
            hex_data = "".join(l.strip() for l in lines[1:])
            try:
                raw_bytes = bytes.fromhex(hex_data)
                strings = re.findall(b'[ -~]{10,}', raw_bytes)
                if strings:
                    out.write(f"--- Packet {header}\n")
                    for s in strings:
                        out.write("  " + s.decode('ascii') + "\n")
            except Exception as e:
                pass

if __name__ == "__main__":
    find_ascii("scratch/accion1_dump.txt", "scratch/accion1_strings.txt")
    find_ascii("scratch/accion2_dump.txt", "scratch/accion2_strings.txt")
