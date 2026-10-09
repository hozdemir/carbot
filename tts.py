import asyncio
import shlex
from events import Events


class TTSSpeaker:
    """Plays speech and sound files one at a time, in the order they were queued, so they never talk over each
    other."""

    def __init__(self, config, alsa, audioManager):
        self.alsa = alsa
        self.audioManager = audioManager
        self.audioToken = "08843f08-92aa-49b0-840f-74c6b38092ff"
        audioConfig = config["AUDIO"]
        self.ttsCommand = audioConfig["TTSCommand"]
        self.soundCommand = audioConfig.get("SoundCommand", "aplay -q {}")
        self.workQueue = asyncio.Queue()
        self.startLoop()

    def startLoop(self):
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(self.queueLoop())

    async def queueLoop(self):
        print("Starting TTS...")
        try:
            while True:
                kind, value = await self.workQueue.get()
                if value:
                    if kind == "sound":
                        print("Playing '{}'".format(value))
                        command = self.soundCommand.format(shlex.quote(value))
                    else:
                        print("Saying '{}'".format(value))
                        command = self.ttsCommand.format(shlex.quote(value))
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

    def sayText(self, text):
        self.workQueue.put_nowait(("say", text))

    def playSound(self, path):
        self.workQueue.put_nowait(("sound", path))
