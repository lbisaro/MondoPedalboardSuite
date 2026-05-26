import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)
repos_dir = os.path.join(project_dir, "repos", "helix_usb")
if repos_dir not in sys.path:
    sys.path.insert(1, repos_dir)

from utils.preset_parser import HxPreset

def main():
    filepath = os.path.join(project_dir, "preset_hex_split.txt")
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    with open(filepath, "r") as f:
        hex_str = f.read().strip()

    preset = HxPreset(data_in=hex_str, preset_name="Test")
    
    print("All slots found in preset:")
    for idx, slot in enumerate(preset.slot_info):
        st = getattr(slot, 'slot_type', 0x08)
        if st == 0x08:
            continue
        names = slot.id_to_names()
        print(f"Slot {idx}: type={hex(st)}, name={names[0]}")
        print(f"  raw hex: {slot.raw.hex()}")
        print(f"  parameter_a: {getattr(slot, 'parameter_a', [])}")
        print(f"  parameter_b: {getattr(slot, 'parameter_b', [])}")

if __name__ == "__main__":
    main()
