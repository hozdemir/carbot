from typing import Optional

import cv2
import numpy as np

from detection import Detection


class ColorDetector:
    """Finds the largest blob of the configured HSV colour range in a BGR frame."""

    def __init__(self, followConfig):
        self.lowerBound = np.array([
            int(followConfig.get("HueLow", 100)),
            int(followConfig.get("SatLow", 150)),
            int(followConfig.get("ValLow", 50)),
        ])
        self.upperBound = np.array([
            int(followConfig.get("HueHigh", 140)),
            int(followConfig.get("SatHigh", 255)),
            int(followConfig.get("ValHigh", 255)),
        ])
        self.minRadius = float(followConfig.get("MinRadius", 0.04))

    def detect(self, frame) -> Optional[Detection]:
        height, width = frame.shape[:2]

        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lowerBound, self.upperBound)
        # Erode then dilate so single-pixel noise does not count as a target.
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)

        contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
        if len(contours) == 0:
            return None

        largest = max(contours, key=cv2.contourArea)
        (centerX, centerY), radius = cv2.minEnclosingCircle(largest)

        if radius / height < self.minRadius:
            return None

        return Detection(x=centerX / width, y=centerY / height, radius=radius / height)
