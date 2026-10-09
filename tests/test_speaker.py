import sys
import types
import unittest
from unittest import mock

from speaker import enableSpeaker


def fusionHatDevice(enable_speaker):
    package = types.ModuleType("fusion_hat")
    device = types.ModuleType("fusion_hat.device")
    device.enable_speaker = enable_speaker
    package.device = device
    return {"fusion_hat": package, "fusion_hat.device": device}


class EnableSpeakerTest(unittest.TestCase):
    def test_switches_the_speaker_on(self):
        calls = []

        with mock.patch.dict(sys.modules, fusionHatDevice(lambda: calls.append("on"))):
            self.assertTrue(enableSpeaker())

        self.assertEqual(calls, ["on"])

    def test_keeps_the_server_running_without_permission(self):
        def denied():
            raise PermissionError(13, "Permission denied", "/sys/class/fusion_hat/fusion_hat/speaker")

        with mock.patch.dict(sys.modules, fusionHatDevice(denied)):
            self.assertFalse(enableSpeaker())

    def test_keeps_the_server_running_when_the_driver_is_missing(self):
        def missing():
            raise IOError("Fusion Hat driver not loaded")

        with mock.patch.dict(sys.modules, fusionHatDevice(missing)):
            self.assertFalse(enableSpeaker())


if __name__ == "__main__":
    unittest.main()
