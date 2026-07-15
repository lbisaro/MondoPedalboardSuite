import sys
import usb.core
import libusb_package
backend = libusb_package.get_libusb1_backend()
dev = usb.core.find(idVendor=0x0E41, idProduct=0x424a, backend=backend)
if dev:
    for cfg in dev:
        for intf in cfg:
            print(f"Interface: {intf.bInterfaceNumber} Alt: {intf.bAlternateSetting}")
            print(f"  Class: 0x{intf.bInterfaceClass:02x} SubClass: 0x{intf.bInterfaceSubClass:02x} Protocol: 0x{intf.bInterfaceProtocol:02x}")
            for ep in intf:
                print(f"    Endpoint: 0x{ep.bEndpointAddress:02x} Attr: 0x{ep.bmAttributes:02x} MaxPacketSize: {ep.wMaxPacketSize}")
else:
    print("Device not found")
