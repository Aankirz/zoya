"""Screenshot → click coordinates (§9.6, AUDIT B10): the #1 computer-use bug."""

import pytest

from zoya.screen import capture_size, image_to_screen
from zoya.tools import ToolError

RETINA = (0.0, 0.0, 1512.0, 982.0)  # built-in 14" display, 2.0 backing scale, in points
EXTERNAL_RIGHT = (1512.0, 0.0, 1920.0, 1080.0)  # 1.0 scale monitor to the right
EXTERNAL_LEFT_ABOVE = (-2560.0, -400.0, 2560.0, 1440.0)  # left of and above the main display


def test_retina_display_is_captured_at_point_size_so_coordinates_are_identical():
    assert capture_size(1512, 982, 1600) == (1512, 982)
    assert image_to_screen(700, 450, 1512, 982, RETINA) == (700, 450)


def test_wide_display_is_downscaled_to_the_max_width_keeping_aspect():
    assert capture_size(1512, 982, 1280) == (1280, 831)
    assert capture_size(2560, 1440, 1280) == (1280, 720)


def test_downscaled_retina_screenshot_scales_back_to_points():
    x, y = image_to_screen(640, 415.5, 1280, 831, RETINA)

    assert x == pytest.approx(756)
    assert y == pytest.approx(491)


def test_external_display_to_the_right_adds_its_origin():
    x, y = image_to_screen(640, 360, 1280, 720, EXTERNAL_RIGHT)

    assert (x, y) == (pytest.approx(1512 + 960), pytest.approx(540))


def test_display_with_negative_origin_maps_into_negative_global_points():
    x, y = image_to_screen(0, 0, 1280, 720, EXTERNAL_LEFT_ABOVE)

    assert (x, y) == (-2560, -400)


def test_bottom_right_pixel_stays_on_its_own_display():
    x, y = image_to_screen(1279, 719, 1280, 720, EXTERNAL_RIGHT)

    assert x < 1512 + 1920 and y < 1080


@pytest.mark.parametrize("x, y", [(-1, 10), (10, -0.5), (1280, 10), (10, 720), (5000, 5000)])
def test_points_outside_the_screenshot_are_refused(x, y):
    with pytest.raises(ToolError):
        image_to_screen(x, y, 1280, 720, EXTERNAL_RIGHT)
