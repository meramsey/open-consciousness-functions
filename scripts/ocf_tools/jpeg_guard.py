"""Read-only validation of public JPEG cover coding and exact scan boundaries.

Pillow deliberately tolerates extraneous entropy bytes. Count the DCT blocks
and Huffman symbols instead (ITU-T T.81, annexes B, C, F and G). This accepts
8-bit sequential/progressive Huffman JPEG; other coding modes fail closed.
No pixels are re-encoded and no approved input bytes are changed.
"""

from array import array

from .utils import OCFError

MESSAGE = "cover contains invalid JPEG coding, image metadata or unused scan data"


def _require(value):
    if not value:
        raise OCFError(MESSAGE)


class _Bits:
    def __init__(self, data, position):
        self.data, self.position = data, position
        self.value = self.remaining = 0

    def read(self, count):
        result = 0
        for _ in range(count):
            if not self.remaining:
                _require(self.position < len(self.data))
                self.value = self.data[self.position]
                self.position += 1
                if self.value == 255:
                    _require(self.position < len(self.data) and self.data[self.position] == 0)
                    self.position += 1
                self.remaining = 8
            self.remaining -= 1
            result = (result << 1) | ((self.value >> self.remaining) & 1)
        return result

    def boundary(self):
        # Only at most seven one-bits may complete the final entropy byte.
        _require((self.value & ((1 << self.remaining) - 1)) == (1 << self.remaining) - 1)
        self.remaining = 0
        _require(self.position < len(self.data) and self.data[self.position] == 255)
        while self.position < len(self.data) and self.data[self.position] == 255:
            self.position += 1
        _require(self.position < len(self.data) and self.data[self.position] != 0)
        return self.data[self.position]


def _symbol(bits, table):
    code = 0
    for length in range(1, 17):
        code = (code << 1) | bits.read(1)
        value = table.get((length, code))
        if value is not None:
            return value
    raise OCFError(MESSAGE)


class _JPEG:
    def __init__(self):
        self.components = {}
        self.tables = {}
        self.quantizers = set()
        self.interval = 0
        self.scans = 0
        self.progressive = False

    def frame(self, marker, payload):
        _require(not self.components and len(payload) >= 6 and payload[0] == 8)
        height, width = int.from_bytes(payload[1:3], "big"), int.from_bytes(payload[3:5], "big")
        count = payload[5]
        _require(0 < width <= 12000 and 0 < height <= 12000)
        _require(1 <= count <= 4 and len(payload) == 6 + 3 * count)
        self.progressive = marker == 0xC2
        for offset in range(6, len(payload), 3):
            identity, sampling, quantizer = payload[offset : offset + 3]
            h, v = sampling >> 4, sampling & 15
            _require(identity not in self.components and 1 <= h <= 4 and 1 <= v <= 4)
            _require(quantizer <= 3)
            self.components[identity] = {"h": h, "v": v, "q": quantizer, "levels": [-1] * 64}
        max_h = max(c["h"] for c in self.components.values())
        max_v = max(c["v"] for c in self.components.values())
        _require(sum(c["h"] * c["v"] for c in self.components.values()) <= 10)
        self.columns = (width + max_h * 8 - 1) // (max_h * 8)
        self.rows = (height + max_v * 8 - 1) // (max_v * 8)
        for c in self.components.values():
            c["columns"] = (width * c["h"] + max_h * 8 - 1) // (max_h * 8)
            c["rows"] = (height * c["v"] + max_v * 8 - 1) // (max_v * 8)
            c["stride"] = self.columns * c["h"]
            c["nonzero"] = array("Q", [0]) * (c["stride"] * self.rows * c["v"])

    def huffman(self, payload):
        _require(payload)
        position = 0
        while position < len(payload):
            _require(position + 17 <= len(payload))
            selector = payload[position]
            counts = payload[position + 1 : position + 17]
            _require(selector >> 4 <= 1 and selector & 15 <= 3)
            position += 17
            total = sum(counts)
            _require(0 < total <= 256 and position + total <= len(payload))
            symbols = payload[position : position + total]
            _require(len(set(symbols)) == total)
            if selector < 16:
                _require(all(s <= 11 for s in symbols))
            else:
                _require(all(s & 15 <= 10 for s in symbols))
            table, code, index = {}, 0, 0
            for length, count in enumerate(counts, 1):
                # JPEG reserves the all-one code for entropy padding.
                _require(code + count < 1 << length)
                for _ in range(count):
                    table[length, code] = symbols[index]
                    code += 1
                    index += 1
                code <<= 1
            self.tables[selector] = table
            position += total
        _require(position == len(payload))

    def quantization(self, payload):
        _require(payload)
        position = 0
        while position < len(payload):
            selector = payload[position]
            precision, identity = selector >> 4, selector & 15
            _require(precision <= 1 and identity <= 3)
            size = 1 + 64 * (precision + 1)
            _require(position + size <= len(payload))
            values = payload[position + 1 : position + size]
            _require(
                all(
                    int.from_bytes(values[i : i + precision + 1], "big") > 0
                    for i in range(0, len(values), precision + 1)
                )
            )
            self.quantizers.add(identity)
            position += size

    def block(self, bits, component, index, dc, ac, start, stop, high):
        mask = component["nonzero"][index]
        if start == 0:
            if high:
                bits.read(1)
            else:
                bits.read(_symbol(bits, dc))
            if self.progressive:
                return
            start = 1
        k = start
        if not self.eob:
            while k <= stop:
                run, size = divmod(_symbol(bits, ac), 16)
                if size:
                    _require(not high or size == 1)
                    bits.read(size)
                elif run != 15:
                    if not self.progressive:
                        _require(run == 0)
                    self.eob = (1 << run) + bits.read(run)
                    break
                if high:
                    zeros = run + (not size)
                    while k <= stop:
                        if mask & (1 << k):
                            bits.read(1)
                        elif zeros:
                            zeros -= 1
                        else:
                            break
                        k += 1
                        if not size and zeros == 0:
                            break
                    _require(zeros == 0)
                else:
                    k += run + (not size)
                if size:
                    _require(k <= stop)
                    mask |= 1 << k
                    k += 1
                else:
                    _require(k <= stop + 1)
        if self.eob:
            if high:
                for coefficient in range(k, stop + 1):
                    if mask & (1 << coefficient):
                        bits.read(1)
            self.eob -= 1
        component["nonzero"][index] = mask

    def scan(self, payload, data, position):
        _require(self.components and len(payload) >= 6)
        count = payload[0]
        _require(1 <= count <= len(self.components) and len(payload) == 4 + count * 2)
        start, stop, approximation = payload[-3:]
        high, low = approximation >> 4, approximation & 15
        _require(0 <= start <= stop <= 63)
        if self.progressive:
            _require((start == stop == 0) or (start > 0 and count == 1))
            _require(low <= 13 and (high == 0 or high == low + 1))
        else:
            _require((start, stop, high, low) == (0, 63, 0, 0))
        selected, identities = [], set()
        for offset in range(1, count * 2 + 1, 2):
            identity, selector = payload[offset : offset + 2]
            _require(identity in self.components and identity not in identities)
            identities.add(identity)
            c = self.components[identity]
            _require(c["q"] in self.quantizers)
            _require(start == 0 or c["levels"][0] >= 0)
            _require(all(c["levels"][k] == (high if high else -1) for k in range(start, stop + 1)))
            for k in range(start, stop + 1):
                c["levels"][k] = low
            _require(selector >> 4 <= 3 and selector & 15 <= 3)
            dc, ac = self.tables.get(selector >> 4), self.tables.get(16 | (selector & 15))
            _require((start > 0 or high or dc is not None) and (stop == 0 or ac is not None))
            selected.append((c, dc, ac))
        bits = _Bits(data, position)
        columns = self.columns if count > 1 else selected[0][0]["columns"]
        rows = self.rows if count > 1 else selected[0][0]["rows"]
        total = columns * rows
        self.eob = 0
        restart = 0
        for mcu in range(total):
            if self.interval and mcu and mcu % self.interval == 0:
                _require(self.eob == 0 and bits.boundary() == 0xD0 + restart)
                bits.position += 1
                restart = (restart + 1) % 8
            y, x = divmod(mcu, columns)
            for c, dc, ac in selected:
                for v in range(c["v"] if count > 1 else 1):
                    for h in range(c["h"] if count > 1 else 1):
                        index = (
                            ((y * c["v"] + v) * c["stride"] + x * c["h"] + h)
                            if count > 1
                            else y * c["stride"] + x
                        )
                        self.block(bits, c, index, dc, ac, start, stop, high)
        _require(self.eob == 0)
        marker = bits.boundary()
        _require(not 0xD0 <= marker <= 0xD7)
        self.scans += 1
        # boundary() stops at the marker code; caller reads the complete marker.
        return bits.position - 1


def check_jpeg(data):
    """Reject unconsumed coding bytes and opaque metadata, preserving input."""
    _require(data.startswith(b"\xff\xd8"))
    jpeg, position = _JPEG(), 2
    while position < len(data):
        _require(data[position] == 255)
        while position < len(data) and data[position] == 255:
            position += 1
        _require(position < len(data))
        marker = data[position]
        position += 1
        if marker == 0xD9:
            _require(
                position == len(data)
                and jpeg.scans
                and all(c["levels"][0] >= 0 for c in jpeg.components.values())
            )
            return
        _require(position + 2 <= len(data))
        length = int.from_bytes(data[position : position + 2], "big")
        end = position + length
        _require(length >= 2 and end <= len(data))
        payload = data[position + 2 : end]
        if marker == 0xE0:
            _require(
                len(payload) == 14
                and payload[:5] == b"JFIF\0"
                and payload[5] == 1
                and payload[6] <= 2
                and payload[7] <= 2
                and payload[12:] == b"\0\0"
            )
        elif marker == 0xEE:
            _require(
                len(payload) == 12
                and payload[:5] == b"Adobe"
                and payload[7:11] == b"\0" * 4
                and payload[11] <= 2
            )
        elif marker in {0xC0, 0xC1, 0xC2}:
            jpeg.frame(marker, payload)
        elif marker == 0xC4:
            jpeg.huffman(payload)
        elif marker == 0xDB:
            jpeg.quantization(payload)
        elif marker == 0xDD:
            _require(len(payload) == 2)
            jpeg.interval = int.from_bytes(payload, "big")
        elif marker == 0xDA:
            position = jpeg.scan(payload, data, end)
            continue
        else:
            raise OCFError(MESSAGE)
        position = end
    raise OCFError(MESSAGE)
