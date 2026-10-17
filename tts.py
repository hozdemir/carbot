import asyncio
import shlex
from events import Events
from voices import Voices


class TTSSpeaker:
    """Plays speech and sound files one at a time, in the order they were queued, so they never talk over each
    other. Speech uses the Piper voice for the requested language."""

    def __init__(self, config, alsa, audioManager):
        self.alsa = alsa
        self.audioManager = audioManager
        self.audioToken = "08843f08-92aa-49b0-840f-74c6b38092ff"
        audioConfig = config["AUDIO"]
        self.ttsCommand = audioConfig["TTSCommand"]
        self.soundCommand = audioConfig.get("SoundCommand", "aplay -q {}")
        self.voices = Voices(config["VOICES"] if config.has_section("VOICES") else {},
                             audioConfig.get("DefaultLanguage", "tr"))
        self.workQueue = asyncio.Queue()
        self.startLoop()

    def startLoop(self):
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(self.queueLoop())

    async def queueLoop(self):
        print("Starting TTS...")
        try:
            while True:
                kind, value, language = await self.workQueue.get()
                if value:
                    if kind == "sound":
                        print("Playing '{}'".format(value))
                        command = self.soundCommand.format(shlex.quote(value))
                    else:
                        command = self.speechCommand(value, language)
                        if command is None:
                            continue
                    self.audioManager.lowerVolume(self.audioToken)
                    process = await asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    print("TTS stdout:", stdout.decode())
                    print("TTS stderr:", stderr.decode())
                    self.audioManager.restoreVolume(self.audioToken)
        except asyncio.CancelledError:
            print("TTS stopped")

    def speechCommand(self, text, language):
        # A TTSCommand from before voices were configurable has the text as its only "{}" and one voice built in.
        if "{text}" not in self.ttsCommand:
            print("Saying '{}'".format(text))
            return self.ttsCommand.format(shlex.quote(text))

        voice = self.voices.forLanguage(language)
        if voice is None:
            print("Cannot say '{}': no voice in [VOICES] has its model files".format(text))
            return None

        print("Saying '{}' in '{}'".format(text, voice.language))
        return self.ttsCommand.format(text=shlex.quote(text), model=shlex.quote(voice.model), rate=voice.sampleRate)

    def sayText(self, text, language=None):
        self.workQueue.put_nowait(("say", text, language))

    def playSound(self, path):
        self.workQueue.put_nowait(("sound", path, None))
