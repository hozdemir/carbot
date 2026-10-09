import pigpio
from apa102_pi.driver import apa102

LED_COUNT = 8
MAX_BRIGHTNESS = 31


def parseColor(value):
    """Turns "#ff8800" or "FF8800" into 0xFF8800."""
    text = str(value).strip().lstrip("#")
    if len(text) != 6:
        raise ValueError("Expected a colour like #ff8800, got {!r}".format(value))
    return int(text, 16)


def formatColor(color):
    return "#{:06x}".format(color)


class LightsController:
    def __init__(self, config):
        lightsConfig = config["LIGHTS"] if config.has_section("LIGHTS") else {}
        self.color = parseColor(lightsConfig.get("Color", "FFFFFF"))
        self.brightness = clampBrightness(int(lightsConfig.get("Brightness", MAX_BRIGHTNESS)))

        self.lights = apa102.APA102(num_led=LED_COUNT, order='rgb')
        self.lights.set_global_brightness(self.brightness)
        self.lightsStatus = False

    def lightsOn(self):
        for ix in range(0, LED_COUNT):
            self.lights.set_pixel_rgb(ix, self.color)
        self.lights.show()
        self.lightsStatus = True

    def lightsOff(self):
        self.lights.clear_strip()
        self.lightsStatus = False

    def setColor(self, color):
        """Changes the light colour; lights that are on change straight away."""
        self.color = parseColor(color)
        if self.lightsStatus:
            self.lightsOn()

    def setBrightness(self, brightness):
        """Changes the APA102 global brightness (0-31); lights that are on change straight away."""
        self.brightness = clampBrightness(int(brightness))
        self.restoreBrightness()
        if self.lightsStatus:
            self.lightsOn()

    def restoreBrightness(self):
        """Puts back the configured brightness after something else (the startup animation) changed it."""
        self.lights.set_global_brightness(self.brightness)

    def stop(self):
        self.lightsOff()
        self.lights.cleanup()
        self.lightsStatus = False


def clampBrightness(brightness):
    return max(0, min(MAX_BRIGHTNESS, brightness))
