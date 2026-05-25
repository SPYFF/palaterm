"""Shared pytest fixtures.

Anything more complex than a one-line wrapper around
:mod:`tests.fixtures` belongs there, not here.
"""

from __future__ import annotations

import pytest
from palaterm.canvas import Canvas

from .fixtures import build_fixed_canvas


@pytest.fixture
def fixed_canvas() -> Canvas:
    """The deterministic 50-shape canvas used by tests and benches."""
    return build_fixed_canvas()


@pytest.fixture
def empty_canvas() -> Canvas:
    """A fresh, empty canvas."""
    return Canvas()
