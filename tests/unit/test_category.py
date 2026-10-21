"""Unit tests for category domain entity and Unicode normalization."""

import unicodedata
from datetime import datetime, timezone

import pytest

from noteapp.domain.entities.category import Category
from noteapp.domain.errors import ValidationError


def make_category(name: str, color_hex: str = "#123ABC") -> Category:
    return Category(
        id="cat-1",
        name=name,
        color_hex=color_hex,
        created_at=datetime.now(timezone.utc),
    )


def test_category_name_is_trimmed():
    category = make_category("  Học tập  ")
    assert category.name == "Học tập"


def test_category_unicode_nfc_and_nfd_produce_same_name_key():
    nfc_name = "Học tập"
    nfd_name = unicodedata.normalize("NFD", nfc_name)

    category_a = make_category(nfc_name)
    category_b = make_category(nfd_name)

    assert category_a.name == "Học tập"
    assert category_b.name == "Học tập"
    assert category_a.name_key == category_b.name_key


def test_category_case_insensitivity():
    category_upper = make_category("HỌC TẬP")
    category_lower = make_category("học tập")

    assert category_upper.name_key == category_lower.name_key


def test_category_valid_hex_color():
    category = make_category("Học tập", "#123ABC")
    assert category.color_hex == "#123ABC"


@pytest.mark.parametrize("invalid_name", ["", "   ", None])
def test_category_blank_name_raises_validation_error(invalid_name):
    with pytest.raises(ValidationError):
        make_category(invalid_name)
