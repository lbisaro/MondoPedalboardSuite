import usb1

def dump_endpoints():
    with usb1.USBContext() as context:
        dev = context.getByVendorIDAndProductID(0x0e41, 0x424a)
        if not dev:
            print("No se encontró la Helix")
            return
            
        for config in dev.iterConfigurations():
            print(f"Configuration: {config.getConfigurationValue()}")
            for intf in config:
                for alt in intf:
                    print(f"  Interface {alt.getNumber()} Alt {alt.getAlternateSetting()}")
                    for ep in alt:
                        ep_addr = ep.getAddress()
                        ep_attr = ep.getAttributes()
                        ep_type = ep_attr & 0x03
                        ep_dir = "IN " if ep_addr & 0x80 else "OUT"
                        type_str = ["CONTROL", "ISOCHRONOUS", "BULK", "INTERRUPT"][ep_type]
                        print(f"    Endpoint 0x{ep_addr:02X} {ep_dir} {type_str}")

if __name__ == "__main__":
    dump_endpoints()
