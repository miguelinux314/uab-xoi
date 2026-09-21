def print_ip_binary(ip: str):
    parts = [int(s) for s in ip.split(".")]
    print(" ".join(f"{part:8d}" for part in parts))
    print(" ".join(f"{part:08b}" for part in parts))
    
print_ip_binary(ip = "192.168.0.1")
