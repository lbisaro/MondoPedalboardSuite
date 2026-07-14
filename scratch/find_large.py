def find_large():
    with open("scratch/live_out.txt") as f:
        for line in f:
            if "len=" in line:
                try:
                    l = int(line.split("len=")[1].split(":")[0])
                    if l > 20: # ignore small keepalives
                        print(line.strip())
                except:
                    pass

if __name__ == "__main__":
    find_large()
