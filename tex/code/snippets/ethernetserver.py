import socket

interface_name = "wlp5s0"  # Needs manual configuration

# This socket receives Layer 2 packets directly.
s = socket.socket(family=socket.AF_PACKET, 
                  type=socket.SOCK_RAW, 
                  proto=socket.ntohs(socket.ETH_P_ALL))
s.bind((interface_name, 0))

valid_frames = 0
while valid_frames < 5:
    frame = s.recv(1514)
    if frame[12:14] != bytes([0x12, 0x34]):
        continue
    valid_frames += 1
    print(f"Received frame {valid_frames + 1}/5, {len(frame)} bytes. "
          f"Payload: {frame[14:]!r}")
