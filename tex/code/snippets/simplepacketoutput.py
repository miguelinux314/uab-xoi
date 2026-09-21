with (open(__file__, "rb") as input_file, 
      open("/dev/stdout", "wb") as output_file):
    # Read at most 255 bytes from the file
    payload: bytes = input_file.read(255)
    # The + operation concatenates bytes
    output_file.write(bytes(len(payload)) + payload)