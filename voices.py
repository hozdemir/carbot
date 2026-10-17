import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    language: str
    model: str
    sampleRate: int


class Voices:
    """The Piper voices in [VOICES] of rover.conf, by language code. Each voice's sample rate comes from the
    .onnx.json file Piper ships next to the model, so aplay always plays it at the right speed. Voices whose files are
    missing are left out with a warning, and unknown languages fall back to the default one."""

    def __init__(self, voicesConfig, defaultLanguage):
        self.voices = {}
        for language, model in voicesConfig.items():
            voice = loadVoice(language.strip().lower(), model.strip())
            if voice is not None:
                self.voices[voice.language] = voice

        self.defaultLanguage = defaultLanguage.strip().lower()
        if self.voices and self.defaultLanguage not in self.voices:
            fallback = sorted(self.voices)[0]
            print("Default language '{}' has no voice, using '{}'".format(self.defaultLanguage, fallback))
            self.defaultLanguage = fallback

    def languages(self):
        return sorted(self.voices)

    def forLanguage(self, language=None):
        """The voice for language, or the default voice when language is empty or has none. None without voices."""
        if language:
            voice = self.voices.get(language.strip().lower())
            if voice is not None:
                return voice
            print("No voice for language '{}', using '{}'".format(language, self.defaultLanguage))
        return self.voices.get(self.defaultLanguage)


def loadVoice(language, model):
    configPath = model + ".json"
    if not os.path.isfile(model) or not os.path.isfile(configPath):
        print("Voice '{}' skipped: {} or its .json is missing".format(language, model))
        return None
    try:
        with open(configPath, "r") as f:
            sampleRate = int(json.load(f)["audio"]["sample_rate"])
    except (ValueError, KeyError, TypeError) as e:
        print("Voice '{}' skipped: cannot read the sample rate from {}: {}".format(language, configPath, e))
        return None
    return Voice(language=language, model=model, sampleRate=sampleRate)
