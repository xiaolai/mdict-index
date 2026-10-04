"""The pure-Python LZO1X decoder, against vectors and (when present) the real liblzo2.

The committed vectors were produced by liblzo2 (lzo1x_1 and lzo1x_999) from invented text,
so the decoder is checked on GitHub too, where the system library may be absent.
"""
import ctypes
import ctypes.util
import random
import unittest

from lzo1x import LZOError, decompress

PAIR = ("The quick brown fox jumps over the lazy dog. 敏捷的棕色狐狸跳过了懒狗。" * 4).encode()
VECTORS = [
    (b"hello", "1668656c6c6f110000"),
    (b"abcabcabcabcabcabcabcabcabcabcabcabc" * 3, "03616263616263203314000f616263616263616263616263616263616263110000"),
    (b"abcabcabcabcabcabcabcabcabcabcabcabc" * 3, "1461626320480800110000"),
    (PAIR, "004954686520717569636b2062726f776e20666f78206a756d7073206f76657220746865206c617a7920646f672e20e6958fe68db7"
           "e79a84e6a395e889b2e78b90e78bb8e8b7b3e8bf87e4ba86e68792e78b97e380825468652071756920c34c010eb7b3e8bf87e4ba86e6"
           "8792e78b97e38082110000"),
    (PAIR, "3154686520717569636b2062726f776e20666f78206a756d7073206f76657220745803001f6c617a7920646f672e20e6958fe68db7"
           "e79a84e6a395e889b2e78b90e78bb8e8b7b3e8bf87e4ba86e68792e78b97e3808220db4c01110000"),
    (bytes(300), "02000000000020f31000000100000000000000000000000000000000000000110000"),
    (bytes(300), "120020000b0000110000"),
]


def _liblzo2():
    for candidate in (ctypes.util.find_library("lzo2"), "/opt/homebrew/lib/liblzo2.dylib", "liblzo2.so.2"):
        if candidate:
            try:
                return ctypes.CDLL(candidate)
            except OSError:
                continue
    return None


LIB = _liblzo2()


class Vectors(unittest.TestCase):
    def test_committed_vectors_decode_exactly(self):
        for expected, hexdata in VECTORS:
            self.assertEqual(decompress(bytes.fromhex(hexdata)), expected)

    def test_malformed_input_raises_instead_of_reading_out_of_range(self):
        good = bytes.fromhex(VECTORS[3][1])
        for bad in [b"", good[:10], good[:-3], b"\x00\x00", b"\x20\xff\xff"]:
            with self.assertRaises(LZOError, msg=bad.hex()):
                decompress(bad)

    def test_bytes_after_the_end_marker_are_an_error(self):
        # liblzo2 reports these as LZO_E_INPUT_NOT_CONSUMED; a silent success would hide a misframed block.
        for hexdata in ("1668656c6c6f110000ff", VECTORS[2][1] + "00"):
            with self.assertRaises(LZOError, msg=hexdata):
                decompress(bytes.fromhex(hexdata))


@unittest.skipUnless(LIB, "liblzo2 not installed")
class AgainstLibLZO(unittest.TestCase):
    def compress(self, data: bytes, fn: str) -> bytes:
        out = ctypes.create_string_buffer(len(data) + len(data) // 16 + 64 + 3)
        n = ctypes.c_size_t(0)
        wrk = ctypes.create_string_buffer(1 << 20)
        self.assertEqual(getattr(LIB, fn)(data, ctypes.c_size_t(len(data)), out, ctypes.byref(n), wrk), 0)
        return out.raw[:n.value]

    def test_round_trips_every_shape_of_input(self):
        rng = random.Random(1)
        cases = [b"", b"a", b"abc" * 5000, bytes(70000), PAIR * 200, bytes(rng.randrange(256) for _ in range(50000)),
                 b"".join(b"x" * rng.randrange(1, 300) + bytes(rng.randrange(256) for _ in range(rng.randrange(1, 60)))
                          for _ in range(2000))]
        for fn in ("lzo1x_1_compress", "lzo1x_999_compress"):
            for data in cases:
                self.assertEqual(decompress(self.compress(data, fn)), data, (fn, len(data)))


if __name__ == "__main__":
    unittest.main()
