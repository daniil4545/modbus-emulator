import sys
sys.path.insert(0, ".")

import pytest

from config import encode_value


def test_big_endian_uint32():
    assert encode_value(100000, "uint", 2, "big-endian") == [0x0001, 0x86A0]


def test_little_endian_uint32():
    assert encode_value(100000, "uint", 2, "little-endian") == [0x86A0, 0x0001]


def test_little_endian_float32():
    # 25.0 as float32: struct.pack(">f", 25.0) = 0x41C80000
    # big-endian words: [0x41C8, 0x0000]
    # little-endian words (word-swap): [0x0000, 0x41C8]
    assert encode_value(25.0, "float", 2, "big-endian") == [0x41C8, 0x0000]
    assert encode_value(25.0, "float", 2, "little-endian") == [0x0000, 0x41C8]


def test_single_register_ignores_byte_order():
    big = encode_value(1000, "uint", 1, "big-endian")
    little = encode_value(1000, "uint", 1, "little-endian")
    assert big == little


def test_coil_ignores_byte_order():
    assert encode_value(1, None, 1, "big-endian") == encode_value(1, None, 1, "little-endian")


def test_invalid_byte_order_raises():
    with pytest.raises(ValueError, match="unknown byte_order"):
        encode_value(100, "uint", 2, "bad-value")
