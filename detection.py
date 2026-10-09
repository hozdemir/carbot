from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    """A target found in a frame. x and y are 0..1 from the top-left corner, radius is a fraction of the frame
    height, so the values do not depend on the capture resolution."""
    x: float
    y: float
    radius: float
