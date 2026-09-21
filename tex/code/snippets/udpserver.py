import socket

port = 4567
s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
s.bind(('', port))
while True:
    user_datagram = s.recvfrom(1024)
    print(f"Received UDP on {port=}: {user_datagram!r}")