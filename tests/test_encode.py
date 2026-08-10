"""Кодирование test_value в слова datastore: config.encode_value / decode_words."""

import pytest

from config import decode_words, encode_value


@pytest.mark.parametrize(
    "value, fmt, reg_size, expected",
    [
        (42, "uint", 1, [42]),
        (70000, "uint", 2, [1, 4464]),
        (-1, "int", 1, [0xFFFF]),
        (-70000, "int", 2, [0xFFFE, 0xEE90]),
        (1.0, "float", 2, [0x3F80, 0x0000]),
    ],
)
def test_big_endian_puts_high_word_first(value, fmt, reg_size, expected):
    assert encode_value(value, fmt, reg_size, "big-endian") == expected


def test_little_endian_swaps_words():
    big = encode_value(70000, "uint", 2, "big-endian")
    assert encode_value(70000, "uint", 2, "little-endian") == list(reversed(big))


def test_single_word_ignores_byte_order():
    assert encode_value(42, "uint", 1, "little-endian") == encode_value(42, "uint", 1, "big-endian")


@pytest.mark.parametrize("value, expected", [(True, [1]), (0, [0]), (42, [1])])
def test_coil_and_discrete_encode_as_one_bit(value, expected):
    assert encode_value(value, None, 1) == expected


def test_bit_register_stores_whole_word():
    """Регистр с bit нормализуется в uint16 — в datastore ложится слово целиком."""
    assert encode_value(42, "uint", 1) == [42]


def test_unknown_byte_order_rejected():
    with pytest.raises(ValueError, match="byte_order"):
        encode_value(1, "uint", 1, "middle-endian")


def test_unsupported_format_size_pair_rejected():
    with pytest.raises(ValueError, match="unsupported"):
        encode_value(1.0, "float", 1)


@pytest.mark.parametrize(
    "value, fmt, reg_size, byte_order",
    [
        (70000, "uint", 2, "big-endian"),
        (70000, "uint", 2, "little-endian"),
        (-5, "int", 1, "big-endian"),
        (25.5, "float", 2, "big-endian"),
    ],
)
def test_decode_reverses_encode(value, fmt, reg_size, byte_order):
    words = encode_value(value, fmt, reg_size, byte_order)
    assert decode_words(words, fmt, byte_order) == pytest.approx(value)
