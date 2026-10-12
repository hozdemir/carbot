import asyncio
import configparser
import json
import os
import tempfile
import unittest
from unittest import mock

from tts import TTSSpeaker
from voices import Voices


class VoiceFiles:
    """Writes fake Piper voice files (an empty model and its .onnx.json) into a temporary folder."""

    def __init__(self, testCase):
        self.directory = tempfile.TemporaryDirectory()
        testCase.addCleanup(self.directory.cleanup)

    def model(self, name, sampleRate=22050, config=True):
        path = os.path.join(self.directory.name, name + ".onnx")
        open(path, "w").close()
        if config:
            with open(path + ".json", "w") as f:
                json.dump({"audio": {"sample_rate": sampleRate}}, f)
        return path


class VoicesTest(unittest.TestCase):
    def setUp(self):
        self.files = VoiceFiles(self)

    def test_reads_each_voice_and_its_sample_rate(self):
        voices = Voices({"tr": self.files.model("tr"), "EN": self.files.model("en", 16000)}, "tr")

        self.assertEqual(voices.languages(), ["en", "tr"])
        self.assertEqual(voices.forLanguage("en").sampleRate, 16000)
        self.assertEqual(voices.forLanguage("tr").sampleRate, 22050)

    def test_falls_back_to_the_default_for_an_empty_or_unknown_language(self):
        voices = Voices({"tr": self.files.model("tr"), "en": self.files.model("en")}, "tr")

        self.assertEqual(voices.forLanguage(None).language, "tr")
        self.assertEqual(voices.forLanguage("de").language, "tr")
        self.assertEqual(voices.forLanguage(" EN ").language, "en")

    def test_skips_voices_with_missing_files(self):
        voices = Voices({
            "tr": self.files.model("tr"),
            "en": os.path.join(self.files.directory.name, "missing.onnx"),
            "de": self.files.model("de", config=False),
        }, "tr")

        self.assertEqual(voices.languages(), ["tr"])

    def test_skips_a_voice_whose_config_has_no_sample_rate(self):
        path = self.files.model("fr")
        with open(path + ".json", "w") as f:
            f.write("{}")

        self.assertEqual(Voices({"fr": path}, "fr").languages(), [])

    def test_uses_another_voice_when_the_default_one_is_missing(self):
        voices = Voices({"en": self.files.model("en")}, "tr")

        self.assertEqual(voices.defaultLanguage, "en")
        self.assertEqual(voices.forLanguage(None).language, "en")

    def test_has_no_voice_without_any_installed(self):
        self.assertIsNone(Voices({}, "tr").forLanguage("tr"))


class FakeAudioManager:
    def lowerVolume(self, token):
        pass

    def restoreVolume(self, token):
        pass


class FakeProcess:
    async def communicate(self):
        return b"", b""


class MultilingualSpeechTest(unittest.TestCase):
    def setUp(self):
        self.files = VoiceFiles(self)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.commands = []
        patcher = mock.patch("asyncio.create_subprocess_shell", side_effect=self._recordCommand)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.speaker.task.cancel()
        self.loop.run_until_complete(asyncio.sleep(0))
        self.loop.close()
        asyncio.set_event_loop(None)

    async def _recordCommand(self, command, **kwargs):
        self.commands.append(command)
        return FakeProcess()

    def speakerWith(self, ttsCommand, voices):
        config = configparser.ConfigParser(interpolation=None)
        config.read_dict({"AUDIO": {"TTSCommand": ttsCommand, "DefaultLanguage": "tr"}, "VOICES": voices})
        self.speaker = TTSSpeaker(config, alsa=None, audioManager=FakeAudioManager())
        return self.speaker

    def say(self, *args):
        self.speaker.sayText(*args)
        self.loop.run_until_complete(asyncio.sleep(0.01))

    def test_uses_the_voice_and_sample_rate_of_the_requested_language(self):
        english = self.files.model("en_US voice", 16000)
        self.speakerWith("piper {model} {rate} {text}", {"tr": self.files.model("tr"), "en": english})

        self.say("Hello there", "en")

        self.assertEqual(self.commands, ["piper '{}' 16000 'Hello there'".format(english)])

    def test_uses_the_default_voice_without_a_language(self):
        turkish = self.files.model("tr")
        self.speakerWith("piper {model} {rate} {text}", {"tr": turkish})

        self.say("Merhaba")

        self.assertEqual(self.commands, ["piper {} 22050 Merhaba".format(turkish)])

    def test_stays_silent_without_any_voice(self):
        self.speakerWith("piper {model} {rate} {text}", {})

        self.say("Merhaba")

        self.assertEqual(self.commands, [])

    def test_keeps_supporting_a_single_voice_command(self):
        self.speakerWith("echo {} | piper --model /opt/voice.onnx", {})

        self.say("Carbot'un pili az", "en")

        self.assertEqual(self.commands, ["echo 'Carbot'\"'\"'un pili az' | piper --model /opt/voice.onnx"])


if __name__ == "__main__":
    unittest.main()
