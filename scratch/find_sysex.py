def find_sysex():
    with open("scratch/live_out.txt") as f:
        for line in f:
            if "f0" in line.split("len=")[-1]:
                print(line.strip())

if __name__ == "__main__":
    find_sysex()
