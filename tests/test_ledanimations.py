import asyncio
import configparser
import random
import sys
import types
import unittest
from unittest import mock

import ledanimations
from ledanimations import WHITE, cometFrame, hsv, rainbowFrame, scale, solidFrame, sparkleFrame

LEDS = 8


class FramesTest(unittest.TestCase):
    def test_hsv_gives_pure_primaries(self):
        self.assertEqual(hsv(0.0), 0xFF0000)
        self.assertEqual(hsv(1 / 3), 0x00FF00)
        self.assertEqual(hsv(2 / 3), 0x0000FF)

    def test_scale_dims_each_channel(self):
        self.assertEqual(scale(0xFF8040, 0.5), 0x804020)
        self.assertEqual(scale(0xFFFFFF, 0), 0)
        self.assertEqual(scale(0x123456, 2), 0x123456)

    def test_comet_lights_the_head_brightest(self):
        frame = cometFrame(0.0, LEDS)

        self.assertEqual(len(frame), LEDS)
        self.assertGreater(frame[0], 0)
        self.assertEqual(frame[LEDS - 1], 0)

    def test_comet_reaches_the_far_end_halfway_through_a_sweep(self):
        frame = cometFrame(0.25, LEDS, sweeps=2)

        brightest = max(range(LEDS), key=lambda index: brightness(frame[index]))
        self.assertEqual(brightest, LEDS - 1)

    def test_sparkle_fades_and_relights_leds(self):
        rng = random.Random(1)
        frame = [WHITE] * LEDS

        for _ in range(5):
            frame = sparkleFrame(frame, rng)

        self.assertEqual(len(frame), LEDS)
        self.assertTrue(any(color not in (0, WHITE) for color in frame))

    def test_sparkle_without_new_lights_only_fades(self):
        frame = sparkleFrame([WHITE] * LEDS, random.Random(1), chance=0, fade=0.5)

        self.assertEqual(frame, [0x808080] * LEDS)

    def test_rainbow_gives_every_led_a_different_colour(self):
        frame = rainbowFrame(0.0, LEDS)

        self.assertEqual(len(set(frame)), LEDS)

    def test_rainbow_can_fade_out(self):
        self.assertEqual(rainbowFrame(0.3, LEDS, value=0), [0] * LEDS)

    def test_solid_frame(self):
        self.assertEqual(solidFrame(WHITE, 3), [WHITE, WHITE, WHITE])


def brightness(color):
    return ((color >> 16) & 0xFF) + ((color >> 8) & 0xFF) + (color & 0xFF)


class FakeStrip:
    def __init__(self):
        self.pixels = [0] * LEDS
        self.frames = []
        self.brightness = None

    def set_global_brightness(self, value):
        self.brightness = value

    def set_pixel_rgb(self, index, color):
        self.pixels[index] = color

    def show(self):
        self.frames.append(list(self.pixels))

    def clear_strip(self):
        self.pixels = [0] * LEDS
        self.frames.append(list(self.pixels))


class FakeLightsController:
    def __init__(self):
        self.lights = FakeStrip()
        self.brightness = 20

    def restoreBrightness(self):
        self.lights.set_global_brightness(self.brightness)


class FakeClock:
    """Moves time on by a fixed step on every read, so the light show runs through its phases instantly."""

    def __init__(self, step):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now


def _stubLightHardware():
    for name in ("pigpio", "apa102_pi", "apa102_pi.driver"):
        sys.modules.setdefault(name, types.ModuleType(name))
    if not hasattr(sys.modules["apa102_pi.driver"], "apa102"):
        sys.modules["apa102_pi.driver"].apa102 = types.SimpleNamespace(APA102=object)


class LightShowTest(unittest.TestCase):
    def setUp(self):
        _stubLightHardware()
        import startupSequence

        self.startupSequence = startupSequence
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.close()
        asyncio.set_event_loop(None)

    def controller(self, lightsController):
        config = configparser.ConfigParser(interpolation=None)
        config.read_dict({
            "AUDIO": {"Greeting": "", "StartupSound": ""},
            "SERVO": {"Neutral": "0", "Min": "-70", "Max": "90"},
        })
        controller = self.startupSequence.StartupSequenceController(config, mock.Mock(), lightsController, mock.Mock())
        # Only the light show is under test, not the whole boot sequence the constructor schedules.
        controller.task.cancel()
        return controller

    def test_plays_through_every_phase_and_ends_dark_at_the_configured_brightness(self):
        lights = FakeLightsController()
        controller = self.controller(lights)

        with mock.patch.object(self.startupSequence, "FRAME_INTERVAL", 0), \
                mock.patch.object(self.startupSequence.time, "time", FakeClock(0.01)):
            self.loop.run_until_complete(controller.playLightShow())

        frames = lights.lights.frames
        self.assertGreater(len(frames), 50)
        self.assertIn([WHITE] * LEDS, frames)
        self.assertGreater(len({tuple(frame) for frame in frames}), 30)
        self.assertEqual(frames[-1], [0] * LEDS)
        self.assertEqual(lights.lights.brightness, 20)

    def test_turns_the_lights_off_if_interrupted(self):
        lights = FakeLightsController()
        controller = self.controller(lights)

        async def interrupt():
            show = asyncio.get_event_loop().create_task(controller.playLightShow())
            await asyncio.sleep(0.05)
            show.cancel()
            await asyncio.gather(show, return_exceptions=True)

        self.loop.run_until_complete(interrupt())

        self.assertEqual(lights.lights.frames[-1], [0] * LEDS)


if __name__ == "__main__":
    unittest.main()
