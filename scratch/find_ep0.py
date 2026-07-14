def find_ep0():
    with open("scratch/live_out.txt") as f:
        for line in f:
            if "EP0" in line:
                print(line.strip())

if __name__ == "__main__":
    find_ep0()
