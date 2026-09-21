a = 0xff
print(a)
for _ in range(8):
    a = (a << 1) & 0xff
    print(a)