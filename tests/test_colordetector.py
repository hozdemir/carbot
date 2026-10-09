import unittest

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

BLUE = (255, 0, 0)
RED = (0, 0, 255)


@unittest.skipIf(cv2 is None, "needs numpy and OpenCV")
class ColorDetectorTest(unittest.TestCase):
    def setUp(self):
        from colordetector import ColorDetector

        self.detector = ColorDetector({})

    def frame(self):
        return np.zeros((180, 320, 3), dtype=np.uint8)

    def test_finds_a_blue_target_and_reports_it_relative_to_the_frame(self):
        frame = self.frame()
        cv2.circle(frame, (240, 60), 30, BLUE, -1)

        detection = self.detector.detect(frame)

        self.assertAlmostEqual(detection.x, 240 / 320, delta=0.01)
        self.assertAlmostEqual(detection.y, 60 / 180, delta=0.01)
        self.assertAlmostEqual(detection.radius, 30 / 180, delta=0.02)

    def test_returns_nothing_without_the_target_colour(self):
        frame = self.frame()
        cv2.circle(frame, (160, 90), 30, RED, -1)

        self.assertIsNone(self.detector.detect(frame))

    def test_ignores_targets_smaller_than_the_minimum_radius(self):
        frame = self.frame()
        cv2.circle(frame, (160, 90), 4, BLUE, -1)

        self.assertIsNone(self.detector.detect(frame))

    def test_picks_the_largest_target(self):
        frame = self.frame()
        cv2.circle(frame, (60, 90), 15, BLUE, -1)
        cv2.circle(frame, (250, 90), 35, BLUE, -1)

        detection = self.detector.detect(frame)

        self.assertAlmostEqual(detection.x, 250 / 320, delta=0.01)

    def test_ignores_scattered_single_pixel_noise(self):
        frame = self.frame()
        frame[::7, ::7] = BLUE

        self.assertIsNone(self.detector.detect(frame))

    def test_uses_the_configured_colour_range(self):
        from colordetector import ColorDetector

        redDetector = ColorDetector({"HueLow": "0", "HueHigh": "10"})
        frame = self.frame()
        cv2.circle(frame, (160, 90), 30, RED, -1)

        self.assertIsNotNone(redDetector.detect(frame))


if __name__ == "__main__":
    unittest.main()
