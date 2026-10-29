import numpy as np
import pytest

from app.volumes.sampling import sample_function

CUBE = [[-1.5, 1.5], [-1.5, 1.5], [-1.5, 1.5]]


def test_sample_has_requested_resolution():
    grid = sample_function("x**2 + y**2 + z**2 - 1", CUBE, 32)

    assert grid.shape == (32, 32, 32)
    assert grid.origin == (-1.5, -1.5, -1.5)


def test_sample_center_of_sphere_is_inside():
    grid = sample_function("x**2 + y**2 + z**2 - 1", CUBE, 32)

    assert grid.values.min() < -0.99
    assert grid.values[15, 15, 15] < 0


def test_sample_corners_are_outside():
    grid = sample_function("x**2 + y**2 + z**2 - 1", CUBE, 16)

    assert grid.values[0, 0, 0] > 0
    assert grid.values[-1, -1, -1] > 0


def test_sample_indexes_values_as_x_y_z():
    domain = [[0, 1], [10, 20], [100, 300]]

    grid = sample_function("x + y + z", domain, 5)

    x = np.linspace(0, 1, 5)
    y = np.linspace(10, 20, 5)
    z = np.linspace(100, 300, 5)
    expected = x[:, None, None] + y[None, :, None] + z[None, None, :]
    np.testing.assert_allclose(grid.values, expected)


def test_sample_spacing_matches_distance_between_samples():
    domain = [[0, 1], [10, 20], [100, 300]]

    grid = sample_function("x", domain, 5)

    assert grid.spacing == pytest.approx((0.25, 2.5, 50.0))
