import asyncio
import os
import random
import time

import ledanimations
from lightscontroller import LED_COUNT

# About 30 frames a second.
FRAME_INTERVAL = 0.03


class StartupSequenceController:
    def __init__(self, config, servoController, lightsController, tts):
        audioConfig = config["AUDIO"]
        servoConfig = config["SERVO"]
        self.greeting = audioConfig["Greeting"]
        self.startupSound = startupSoundPath(audioConfig.get("StartupSound", ""))
        self.neutral = int(servoConfig["Neutral"])
        self.min = int(servoConfig["Min"])
        self.max = int(servoConfig["Max"])
        self.servoController = servoController
        self.lightsController = lightsController
        self.tts = tts
        self.startLoop()


    def startLoop(self):
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(self.doSequence())

    async def doSequence(self):
        self.lightsController.lightsOff()
        await asyncio.sleep(2)

        # Queued with the greeting, so the chime plays during the animation and the greeting follows it.
        if self.startupSound:
            self.tts.playSound(self.startupSound)

        # The light show runs alongside the servo moves below.
        lightShow = asyncio.get_event_loop().create_task(self.playLightShow())

        servoInterval = 0.25
        self.servoController.changeServo(self.neutral)
        await asyncio.sleep(servoInterval)
        self.servoController.changeServo(self.min)
        await asyncio.sleep(servoInterval)
        self.servoController.changeServo(self.max)
        await asyncio.sleep(servoInterval)

        transitionTime = float(1)
        startTime = time.time()
        targetTime = startTime + transitionTime
        servoTravel = self.max - self.neutral

        while time.time() < targetTime:
            timeFraction = (time.time() - startTime) / transitionTime
            servoPosition = self.max - servoTravel * timeFraction
            self.servoController.changeServo(servoPosition)
            await asyncio.sleep(0.05)

        self.servoController.changeServo(self.neutral)

        if self.greeting:
            self.tts.sayText(self.greeting)

        await lightShow
        self.servoController.stopServo()

    async def playLightShow(self):
        """A rainbow dot sweeping back and forth, a colourful twinkle, two white flashes, then a rainbow that fades
        out. About 2.5 seconds, in the configured brightness."""
        lights = self.lightsController.lights
        self.lightsController.restoreBrightness()
        rng = random.Random()

        async def play(frameAt, duration):
            startedAt = time.time()
            while True:
                progress = (time.time() - startedAt) / duration
                if progress >= 1:
                    return
                self.showFrame(frameAt(progress))
                await asyncio.sleep(FRAME_INTERVAL)

        try:
            await play(lambda progress: ledanimations.cometFrame(progress, LED_COUNT), 0.9)

            sparkle = [0] * LED_COUNT

            def nextSparkle(progress):
                nonlocal sparkle
                sparkle = ledanimations.sparkleFrame(sparkle, rng)
                return sparkle

            await play(nextSparkle, 0.6)

            for _ in range(2):
                self.showFrame(ledanimations.solidFrame(ledanimations.WHITE, LED_COUNT))
                await asyncio.sleep(0.08)
                lights.clear_strip()
                await asyncio.sleep(0.08)

            await play(lambda progress: ledanimations.rainbowFrame(progress * 0.5, LED_COUNT), 0.3)
            await play(lambda progress: ledanimations.rainbowFrame(0.5 + progress * 0.25, LED_COUNT, value=1 - progress),
                       0.5)
        finally:
            lights.clear_strip()
            self.lightsController.restoreBrightness()

    def showFrame(self, frame):
        lights = self.lightsController.lights
        for index, color in enumerate(frame):
            lights.set_pixel_rgb(index, color)
        lights.show()


def startupSoundPath(configured):
    """Resolves StartupSound relative to the repository; returns None when it is unset or the file is missing."""
    if not configured:
        return None
    path = configured if os.path.isabs(configured) else os.path.join(os.path.dirname(os.path.abspath(__file__)), configured)
    if not os.path.isfile(path):
        print("Startup sound '{}' not found, booting without it".format(path))
        return None
    return path
