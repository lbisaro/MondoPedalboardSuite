def print_changes():
    last = None
    with open("scratch/live_out.txt") as f:
        for line in f:
            if ": " in line:
                hex_str = line.split(": ")[1].strip()
                if hex_str != last and hex_str != "0000":
                    print(line.strip())
                    last = hex_str

if __name__ == "__main__":
    print_changes()
