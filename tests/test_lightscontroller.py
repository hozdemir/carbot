import configparser
import sys
import types
import unittest


class FakeAPA102:
    def __init__(self, num_led, order):
        self.pixels = [0] * num_led
        self.shown = None
        self.brightness = None

    def set_global_brightness(self, brightness):
        self.brightness = brightness

    def set_pixel_rgb(self, index, color):
        self.pixels[index] = color

    def show(self):
        self.shown = list(self.pixels)

    def clear_strip(self):
        self.pixels = [0] * len(self.pixels)
        self.shown = list(self.pixels)

    def cleanup(self):
        pass


def _stubLedDriver():
    """lightscontroller imports the APA102 driver and pigpio, which only exist on the Pi."""
    sys.modules.setdefault("pigpio", types.ModuleType("pigpio"))
    package = sys.modules.setdefault("apa102_pi", types.ModuleType("apa102_pi"))
    driver = sys.modules.setdefault("apa102_pi.driver", types.ModuleType("apa102_pi.driver"))
    driver.apa102 = types.SimpleNamespace(APA102=FakeAPA102)
    package.driver = driver


_stubLedDriver()

from lightscontroller import LED_COUNT, LightsController, formatColor, parseColor  # noqa: E402
import lightscontroller  # noqa: E402

# Another test may have imported lightscontroller first with a different stand-in.
lightscontroller.apa102 = types.SimpleNamespace(APA102=FakeAPA102)


def lightsConfig(**lights):
    config = configparser.ConfigParser()
    if lights:
        config.read_dict({"LIGHTS": lights})
    return config


class LightsControllerTest(unittest.TestCase):
    def test_defaults_to_full_brightness_white_without_config(self):
        controller = LightsController(lightsConfig())
        controller.lightsOn()

        self.assertEqual(controller.lights.shown, [0xFFFFFF] * LED_COUNT)
        self.assertEqual(controller.lights.brightness, 31)

    def test_uses_the_configured_colour_and_brightness(self):
        controller = LightsController(lightsConfig(Color="00FF00", Brightness="10"))
        controller.lightsOn()

        self.assertEqual(controller.lights.shown, [0x00FF00] * LED_COUNT)
        self.assertEqual(controller.lights.brightness, 10)

    def test_changing_the_colour_updates_lights_that_are_on(self):
        controller = LightsController(lightsConfig())
        controller.lightsOn()

        controller.setColor("#ff8800")

        self.assertEqual(controller.lights.shown, [0xFF8800] * LED_COUNT)

    def test_changing_the_colour_does_not_turn_the_lights_on(self):
        controller = LightsController(lightsConfig())

        controller.setColor("#ff8800")

        self.assertFalse(controller.lightsStatus)
        self.assertIsNone(controller.lights.shown)

    def test_brightness_is_clamped_and_applied(self):
        controller = LightsController(lightsConfig())

        controller.setBrightness(99)
        self.assertEqual(controller.lights.brightness, 31)

        controller.setBrightness(-5)
        self.assertEqual(controller.lights.brightness, 0)

    def test_restore_brightness_undoes_the_startup_animation_change(self):
        controller = LightsController(lightsConfig(Brightness="12"))
        controller.lights.set_global_brightness(1)

        controller.restoreBrightness()

        self.assertEqual(controller.lights.brightness, 12)

    def test_rejects_invalid_colours(self):
        controller = LightsController(lightsConfig())

        for invalid in ("red", "#12345", "#gggggg", ""):
            with self.assertRaises(ValueError):
                controller.setColor(invalid)

    def test_parses_and_formats_colours(self):
        self.assertEqual(parseColor("#FF8800"), 0xFF8800)
        self.assertEqual(parseColor("ff8800"), 0xFF8800)
        self.assertEqual(formatColor(0x00FF00), "#00ff00")


if __name__ == "__main__":
    unittest.main()
