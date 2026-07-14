def reconstruct():
    sysex_buf = []
    with open("scratch/live_out.txt") as f:
        for line in f:
            if "len=8" in line:
                try:
                    hex_data = line.split("len=8: ")[1].strip()
                    b = bytes.fromhex(hex_data)
                    word1 = b[0:4]
                    word2 = b[4:8]
                    
                    for word in (word1, word2):
                        cin = word[0] & 0x0F
                        if cin == 4:
                            sysex_buf.extend(word[1:4])
                        elif cin == 5:
                            sysex_buf.append(word[1])
                            if sysex_buf:
                                print(f"SysEx: {bytes(sysex_buf).hex()}")
                                sysex_buf = []
                        elif cin == 6:
                            sysex_buf.extend(word[1:3])
                            if sysex_buf:
                                print(f"SysEx: {bytes(sysex_buf).hex()}")
                                sysex_buf = []
                        elif cin == 7:
                            sysex_buf.extend(word[1:4])
                            if sysex_buf:
                                print(f"SysEx: {bytes(sysex_buf).hex()}")
                                sysex_buf = []
                        elif cin == 0xB:
                            print(f"CC: {word.hex()}")
                        elif cin == 0xC:
                            print(f"PC: {word.hex()}")
                except Exception as e:
                    pass

if __name__ == "__main__":
    reconstruct()
