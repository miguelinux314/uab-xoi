import socket

interface_name = "wlp5s0"  # Needs manual configuration

# This socket receives Layer 2 packets directly.
s = socket.socket(
    family=socket.AF_PACKET, type=socket.SOCK_RAW, proto=socket.ntohs(socket.ETH_P_ALL))
s.bind((interface_name, 0))

for i in range(5):
    frame = s.recv(1514)
    if frame[12:14] != bytes([0x12, 0x34]):
        continue
    print(f"Received frame {i + 1}/5, {len(frame)} bytes. Payload: {frame[14:]!r}")
