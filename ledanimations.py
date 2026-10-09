"""Frames for the LED animations. Each function returns one frame as a list of 0xRRGGBB colours, one per LED, so the
animations can be tested without the LED strip."""
import colorsys

WHITE = 0xFFFFFF


def hsv(hue, saturation=1.0, value=1.0):
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, max(0.0, min(1.0, value)))
    return (round(red * 255) << 16) | (round(green * 255) << 8) | round(blue * 255)


def scale(color, factor):
    factor = max(0.0, min(1.0, factor))
    red = round(((color >> 16) & 0xFF) * factor)
    green = round(((color >> 8) & 0xFF) * factor)
    blue = round((color & 0xFF) * factor)
    return (red << 16) | (green << 8) | blue


def cometFrame(progress, ledCount, sweeps=2, glow=1.8):
    """A bright dot running back and forth along the strip `sweeps` times while progress goes 0..1, glowing onto its
    neighbours, its colour cycling through the rainbow."""
    span = 2 * (ledCount - 1)
    position = (progress * sweeps * span) % span
    head = position if position <= ledCount - 1 else span - position

    frame = []
    for index in range(ledCount):
        brightness = 1.0 - abs(index - head) / glow
        frame.append(hsv(progress + index * 0.04, value=brightness) if brightness > 0 else 0)
    return frame


def sparkleFrame(previous, rng, chance=0.35, fade=0.55):
    """Every LED fades a little and some light up again in a random colour, so the strip twinkles."""
    frame = []
    for color in previous:
        if rng.random() < chance:
            frame.append(hsv(rng.random()))
        else:
            frame.append(scale(color, fade))
    return frame


def rainbowFrame(offset, ledCount, value=1.0):
    """Each LED a different colour of the rainbow, shifted along by offset (0..1)."""
    return [hsv(offset + index / ledCount, value=value) for index in range(ledCount)]


def solidFrame(color, ledCount):
    return [color] * ledCount
