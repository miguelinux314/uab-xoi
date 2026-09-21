import socket

interface_name = "wlp5s0"  # Needs manual configuration
source_mac = bytes([0x00, 0x11, 0x22, 0x33, 0x44, 0x55])
destination_mac = bytes([0xff, 0xff, 0xff, 0xff, 0xff, 0xff])
packet_type = bytes([0x12, 0x34])
payload_data = bytes([0x78, 0x6f, 0x69, 0x20, 0x75, 0x61, 0x62])

# This socket sends Layer 2 packets directly.
s = socket.socket(family=socket.AF_PACKET, 
                  type=socket.SOCK_RAW, 
                  proto=socket.ntohs(socket.ETH_P_ALL))
s.bind((interface_name, 0))

for i in range(5):
    frame = destination_mac + source_mac + packet_type + payload_data
    s.send(frame)
    print(f"Sent frame {i + 1}/5: {len(frame)=}, {payload_data=}.")
