import asyncio
import configparser
import os
import sys
import tempfile
import types
import unittest
from unittest import mock


def _stubLightHardware():
    """startupSequence imports the LED driver, which needs the Pi; tests only use its path helper."""
    for name in ("pigpio", "apa102_pi", "apa102_pi.driver"):
        sys.modules.setdefault(name, types.ModuleType(name))
    # Leave a driver another test installed in place.
    if not hasattr(sys.modules["apa102_pi.driver"], "apa102"):
        sys.modules["apa102_pi.driver"].apa102 = types.SimpleNamespace(APA102=object)


_stubLightHardware()

from startupSequence import startupSoundPath  # noqa: E402
from tts import TTSSpeaker  # noqa: E402

REPOSITORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeAudioManager:
    def lowerVolume(self, token):
        pass

    def restoreVolume(self, token):
        pass


class FakeProcess:
    async def communicate(self):
        return b"", b""


class TTSSpeakerQueueTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        config = configparser.ConfigParser(interpolation=None)
        config.read_dict({"AUDIO": {"TTSCommand": "say {}", "SoundCommand": "play {}"}})
        self.commands = []
        patcher = mock.patch("asyncio.create_subprocess_shell", side_effect=self._recordCommand)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.speaker = TTSSpeaker(config, alsa=None, audioManager=FakeAudioManager())

    def tearDown(self):
        self.speaker.task.cancel()
        self.loop.run_until_complete(asyncio.sleep(0))
        self.loop.close()
        asyncio.set_event_loop(None)

    async def _recordCommand(self, command, **kwargs):
        self.commands.append(command)
        return FakeProcess()

    def test_plays_sounds_and_speech_in_the_order_they_were_queued(self):
        self.speaker.playSound("/sounds/startup.wav")
        self.speaker.sayText("Merhaba")

        self.loop.run_until_complete(asyncio.sleep(0.01))

        self.assertEqual(self.commands, ["play /sounds/startup.wav", "say Merhaba"])

    def test_quotes_sound_paths_for_the_shell(self):
        self.speaker.playSound("/my sounds/boot.wav")

        self.loop.run_until_complete(asyncio.sleep(0.01))

        self.assertEqual(self.commands, ["play '/my sounds/boot.wav'"])


class StartupSoundPathTest(unittest.TestCase):
    def test_resolves_the_default_sound_relative_to_the_repository(self):
        path = startupSoundPath("sounds/startup.wav")

        self.assertEqual(path, os.path.join(REPOSITORY, "sounds", "startup.wav"))

    def test_keeps_absolute_paths(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as sound:
            self.assertEqual(startupSoundPath(sound.name), sound.name)

    def test_returns_none_when_unset(self):
        self.assertIsNone(startupSoundPath(""))

    def test_returns_none_for_a_missing_file(self):
        self.assertIsNone(startupSoundPath("sounds/does-not-exist.wav"))


if __name__ == "__main__":
    unittest.main()
