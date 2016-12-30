from itertools import takewhile
import struct


class BitReader:
    def __init__(self, stream):
        self.stream = stream
        self.position = 8

    def read_bit(self):
        if self.position >= 8:
            x = self.stream.read(1)
            if not len(x):
                x = byte(1)
            self.current_byte = ord(x)
            self.position = 0

        value = (self.current_byte >> (8 - self.position - 1)) & 0x01
        self.position += 1
        return value

    def read_bits(self, count):
        result = 0
        for i in range(count):
            result = result | (self.read_bit() << (count - i - 1))
        return result

    def read_byte(self):
        return self.read_bits(8)

    def read_bits_reversed(self, count):
        result = 0
        for i in range(count):
            result = result | (self.read_bit() << i)
        return result


def filesystem(data):
    SECTOR_SIZE = 0x1000

    fs = {}
    data = data[4:]  # header BCFS

    def getint(pos):
        return struct.unpack('<L', data[pos:pos + 4])[0]

    offset = 0
    while offset + SECTOR_SIZE + 3 < len(data):
        if getint(offset) == 2:
            content = b''
            name = bytes(takewhile(lambda x: x != 0, data[offset+4:])).decode()
            size = getint(offset + 0x8c)

            blocks_offset = offset + 0x94

            block_count = 0
            block_id = getint(blocks_offset + 4 * block_count)
            while block_id != 0:
                offset = block_id * SECTOR_SIZE
                content += data[offset: offset + SECTOR_SIZE]

                block_count += 1
                block_id = getint(blocks_offset + 4 * block_count)

            fs[name] = content[:size]

        offset += SECTOR_SIZE

    return fs


def read_gpx(filename):
    data = open(filename, 'rb')

    header = data.read(4)
    assert header == b'BCFZ'

    expected_length = struct.unpack('<L', data.read(4))[0]

    io = BitReader(data)
    result = []

    while len(result) < expected_length:
        flag = io.read_bit()
        if flag == 1:
            word_size = io.read_bits(4)
            offset = io.read_bits_reversed(word_size)
            size = io.read_bits_reversed(word_size)
            source_position = len(result) - offset
            to_read = min([offset, size])
            result += result[source_position: source_position + to_read]
        else:
            size = io.read_bits_reversed(2)
            for i in range(size):
                result.append(io.read_byte())

    return filesystem(bytes(result))
