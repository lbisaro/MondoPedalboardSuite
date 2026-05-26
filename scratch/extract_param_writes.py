import json
import os

def parse_capdata(raw):
    if not raw:
        return None
    try:
        return [int(x, 16) for x in raw.split(":")]
    except ValueError:
        return None

def main():
    paths = [
        r"c:\Users\lbisa\OneDrive\Documentos\soft\Line 6\MondoPedalboardSuite\repos\hxlinux\src\Paquets Json\save\Out_Change_Param_#0.json",
        r"c:\Users\lbisa\OneDrive\Documentos\soft\Line 6\MondoPedalboardSuite\repos\hxlinux\src\Paquets Json\save\Merge_Change_Param_#0.json"
    ]
    for json_path in paths:
        if not os.path.exists(json_path):
            print(f"File not found: {json_path}")
            continue

        print(f"\nReading {json_path}...")
        with open(json_path, "r", encoding="utf-8") as f:
            packets = json.load(f)

        print(f"Total packets: {len(packets)}")
    
    count = 0
    for pkt in packets:
        layers = pkt.get("_source", {}).get("layers", {})
        usb = layers.get("usb", {})
        cap_raw = layers.get("usb.capdata") or usb.get("usb.capdata")
        cap = parse_capdata(cap_raw)
        if not cap:
            continue
            
        direction = "OUT" if usb.get("usb.src") == "host" else "IN"
        
        # Check for 80:10:ed:03 anywhere in the packet
        for i in range(len(cap) - 3):
            if cap[i:i+4] == [0x80, 0x10, 0xed, 0x03]:
                frame_num = layers.get("frame", {}).get("frame.number", "unknown")
                hex_str = " ".join(f"{x:02x}" for x in cap)
                src = usb.get("usb.src", "unknown")
                dst = usb.get("usb.dst", "unknown")
                print(f"Frame #{frame_num} ({direction}, len={len(cap)}, src={src}, dst={dst}): {hex_str}")
                count += 1
                break
        if count >= 30:
            break

if __name__ == "__main__":
    main()
