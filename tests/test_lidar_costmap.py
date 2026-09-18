import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from scheduler.core import Costmap


FIXTURE = Path(__file__).parent / "fixtures" / "lidar_multifloor_96.png"


class LidarRenderedMapCompatibilityTests(unittest.TestCase):
    def test_fixture_is_preprocessed_from_large_attachment(self):
        im = Image.open(FIXTURE).convert("L")
        self.assertEqual(im.size, (96, 54))
        self.assertLessEqual(max(im.size), 512)

    def test_perspective_background_conflicts_with_default_threshold(self):
        a = np.asarray(Image.open(FIXTURE).convert("L"))
        # The perspective background is around 193-196 gray. At threshold=100
        # it looks traversable to the current occupancy-grid semantics.
        self.assertGreater(int(a[5, 5]), 100)
        default = Costmap(a, resolution=.1, threshold=100, radius=0)
        stricter = Costmap(a, resolution=.1, threshold=200, radius=0)
        self.assertTrue(default.valid((5, 5)))
        self.assertFalse(stricter.valid((5, 5)))

    def test_strict_threshold_plus_default_footprint_collapses_free_space(self):
        a = np.asarray(Image.open(FIXTURE).convert("L"))
        default = Costmap(a, resolution=.1, threshold=100, radius=.2)
        strict = Costmap(a, resolution=.1, threshold=200, radius=.2)
        default_free = float((~default.blocked).mean())
        strict_free = float((~strict.blocked).mean())
        self.assertGreater(default_free, .30)
        self.assertLess(strict_free, .01)
        self.assertLess(strict_free, default_free / 10)

    def test_render_is_not_a_single_floor_occupancy_grid(self):
        a = np.asarray(Image.open(FIXTURE).convert("L"))
        grid = Costmap(a, resolution=.1, threshold=100, radius=0)
        # Current Costmap encodes only x/y cells. The supplied image contains
        # two perspective floors and elevator shafts, so floor/portal topology
        # cannot be inferred from the raster alone.
        self.assertEqual(grid.blocked.ndim, 2)
        self.assertEqual(grid.pixels.shape, (54, 96))


if __name__ == "__main__":
    unittest.main()
