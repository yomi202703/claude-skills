"""Property-based tests for pure helpers in xlsx_primitives.py.

Uses hypothesis to generate diverse inputs and assert invariants that
should hold regardless of input shape.
"""
import datetime
from hypothesis import given, strategies as st

import xlsx_primitives as xc  # cell_type / sanitize_slug live here


@given(
    st.one_of(
        st.none(),
        st.text(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.datetimes(),
        st.dates(),
        st.binary(),
        st.lists(st.integers(), max_size=3),  # unexpected type → "o"
    )
)
def test_cell_type_returns_valid_code(v):
    result = xc.cell_type(v)
    assert result in {"e", "b", "n", "d", "s", "o"}, f"unexpected code: {result!r}"


@given(st.text(), st.integers(min_value=1, max_value=128))
def test_sanitize_slug_length_and_fallback(name, max_len):
    slug = xc.sanitize_slug(name, max_len=max_len)
    assert isinstance(slug, str)
    assert len(slug) <= max_len
    assert len(slug) >= 1  # fallback "workbook" guarantees non-empty


@given(st.text())
def test_sanitize_slug_no_underscore_runs(name):
    slug = xc.sanitize_slug(name)
    assert "__" not in slug, "consecutive underscores should be collapsed"
    assert not slug.startswith("_"), "leading underscores should be stripped"
    assert not slug.endswith("_"), "trailing underscores should be stripped"


@given(st.one_of(st.none(), st.just(""), st.just("   ")))
def test_cell_type_empty_variants(v):
    assert xc.cell_type(v) == "e"


@given(st.booleans())
def test_cell_type_bool_not_conflated_with_number(v):
    # bool is a subclass of int in Python — regression guard
    assert xc.cell_type(v) == "b"


@given(st.datetimes())
def test_cell_type_datetime(v):
    assert xc.cell_type(v) == "d"
