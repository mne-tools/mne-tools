# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import pytest
from packaging.requirements import Requirement

from mne_tools.helpers import (
    format_dependency_pins,
    format_operating_systems,
    get_display_name,
)


@pytest.mark.parametrize(
    "dep, ignore_upper_pin, want",
    [
        ("numpy >= 2.0, < 3", False, " ≥ 2.0, < 3"),
        # dropping the upper pin must not leave its separator behind
        ("numpy >= 2.0, < 3", True, " ≥ 2.0"),
        # ... nor discard the specifiers that follow it
        ("x >= 1, < 3, != 2.5", True, " ≥ 1,!=2.5"),
        # `<=` is an upper pin too
        ("y >= 1, <= 3", True, " ≥ 1"),
        ("packaging", True, ""),
    ],
)
def test_format_dependency_pins(dep, ignore_upper_pin, want):
    """Test formatting version specifiers, with and without upper pins."""
    assert format_dependency_pins(Requirement(dep), ignore_upper_pin) == want


@pytest.mark.parametrize(
    "name, want",
    [
        ("numpy", "NumPy"),
        ("NumPy", "NumPy"),  # lookup is canonicalized
        ("lazy_loader", "lazy-loader"),  # unmapped, falls back to canonical name
        ("tqdm", "tqdm"),
    ],
)
def test_get_display_name(name, want):
    """Test styling package names as their projects do."""
    assert get_display_name(name) == want


@pytest.mark.parametrize(
    "classifiers, want",
    [
        # `POSIX` adds nothing next to `POSIX :: Linux`, and `Unix` is a family
        (
            [
                "Operating System :: MacOS",
                "Operating System :: Microsoft :: Windows",
                "Operating System :: POSIX",
                "Operating System :: POSIX :: Linux",
                "Operating System :: Unix",
                "Programming Language :: Python :: 3",
            ],
            ["Linux", "Windows", "macOS"],
        ),
        # a family on its own is the most specific thing declared, so keep it
        (["Operating System :: Unix"], ["Unix"]),
        (["Operating System :: MacOS", "Operating System :: MacOS :: MacOS X"], ["macOS"]),
        (["Programming Language :: Python :: 3"], []),
    ],
)
def test_format_operating_systems(classifiers, want):
    """Test extracting operating systems from trove classifiers."""
    assert format_operating_systems(classifiers) == want
