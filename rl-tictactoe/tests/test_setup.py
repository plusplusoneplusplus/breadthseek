"""Simple test to verify the setup works."""


def test_basic():
    """Test that pytest works."""
    assert 1 + 1 == 2


def test_numpy_import():
    """Test that numpy can be imported."""
    import numpy as np
    
    arr = np.array([1, 2, 3])
    assert arr.sum() == 6
