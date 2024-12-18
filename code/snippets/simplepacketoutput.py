import sys

# By default, read this script and write to the standard output
if len(sys.argv) != 3:
    sys.argv = [sys.argv[0], __file__, "/dev/stdout"]

with open(sys.argv[1], "rb") as input_file, \
        open(sys.argv[2], "wb") as output_file:
    # Read at most 255 bytes from the file
    payload: bytes = input_file.read(255)
    # The + operation concatenates bytes
    output_file.write(bytes(len(payload)) + payload)