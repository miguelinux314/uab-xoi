import typing
import struct

def layer2_encapsulate(address: int, data: bytes) -> bytes:
    """Encapsulate a PDU of layer 3 into a PDU of layer 2."""
    assert 0x0000 <= address <= 0xffff, "Invalid layer 2 address"
    assert len(data) <= 0xffff, "Too much data for a layer 2 PDU"
    return bytes(struct.pack(">H", address)
                 + struct.pack(">H", len(data))
                 + data)

def layer3_encapsulate(offset: int, data: bytes) -> bytes:
    """Encapsulate a chunk of user data into a PDU of layer 3."""
    assert 0x0000 <= offset <= 0xffff, "Invalid layer 3 offset"
    assert len(data) <= 0xffff, "Too much data for a layer 3 PDU"
    return bytes(struct.pack(">H", offset)
                 + struct.pack(">H", len(data))
                 + data)

def stack_send(data: bytes, output_file: typing.BinaryIO):
    layer3_pdu = layer3_encapsulate(offset=0, data=data)
    layer2_pdu = layer2_encapsulate(address=0xabcd, data=layer3_pdu)
    output_file.write(layer2_pdu)

if __name__ == '__main__':
    with (open(__file__, "rb") as input_file,
          open("/dev/stdout", "wb") as output_file):
        payload = input_file.read()
        stack_send(data=payload, output_file=output_file)
