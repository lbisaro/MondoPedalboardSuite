def dump_ep3():
    with open("scratch/live_out.txt") as f:
        for line in f:
            if "EP3" in line:
                print(line.strip())

if __name__ == "__main__":
    dump_ep3()
