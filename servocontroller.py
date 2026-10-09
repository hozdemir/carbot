import asyncio
import time
from fusion_hat.servo import Servo


class ServoController:
    def __init__(self, config, audioManager):
        servoConfig = config["SERVO"]

        # Fusion HAT Servo
        self.servo = Servo(
            servoConfig["PWMPin"],
            offset=float(servoConfig.get("Offset", 0.0)),
            min=float(servoConfig.get("Min", -60)),
            max=float(servoConfig.get("Max", 60)),
        )

        # Angle values (degrees)
        self.neutral = float(servoConfig.get("Neutral", 0))
        self.min = float(servoConfig.get("Min", -60))
        self.max = float(servoConfig.get("Max", 60))

        # Audio
        self.audioManager = audioManager
        self.audioToken = "927dff95-b82b-433c-885c-6ac9ac13d8b0"

        # Motion control
        self.degPerSec = float(servoConfig.get("DegPerSec", 90.0))  # deg / sec
        self.direction = 0  # 1: forward, -1: backward, 0: stop
        self.currentAngle = self.neutral

        # Async control
        self.timingLock = asyncio.Condition()
        self.task = None

        self.startLoop()

    # ──────────────────────────────
    # Public API
    # ──────────────────────────────

    async def forward(self):
        async with self.timingLock:
            self.direction = 1
            self.timingLock.notify()

    async def backward(self):
        async with self.timingLock:
            self.direction = -1
            self.timingLock.notify()

    async def lookStop(self):
        async with self.timingLock:
            self.direction = 0
            self.timingLock.notify()

    def setAngle(self, angle: float):
        """Immediately move servo to given angle and stop motion."""
        angle = max(self.min, min(self.max, angle))
        self.direction = 0
        self.currentAngle = angle
        self.servo.angle(angle)

    def nudgeAngle(self, delta: float):
        """Move the servo by delta degrees, unless the user is moving it with the look keys."""
        if self.direction != 0 or delta == 0:
            return
        self.currentAngle = max(self.min, min(self.max, self.currentAngle + delta))
        self.servo.angle(self.currentAngle)

    # Backward compatibility
    def changeServo(self, value: float):
        """
        Legacy wrapper.
        value is now ANGLE (deg), not PWM.
        """
        self.setAngle(value)

    def stop(self):
        self.stopServo()

    # ──────────────────────────────
    # Internal loop
    # ──────────────────────────────

    def startLoop(self):
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(self._timingLoop())

    async def _timingLoop(self):
        print("Servo starting...")
        try:
            self.currentAngle = self.neutral
            self.servo.angle(self.currentAngle)
            lastTime = None

            while True:
                async with self.timingLock:
                    if not self._shouldMove(self.currentAngle):
                        self.audioManager.restoreVolume(self.audioToken)
                        lastTime = None
                        await self.timingLock.wait()

                self.audioManager.lowerVolume(self.audioToken)

                now = time.time()
                delta = 0.0 if lastTime is None else (now - lastTime) * self.degPerSec
                lastTime = now

                if self.direction == 1:
                    self.currentAngle = max(self.currentAngle - delta, self.min)
                elif self.direction == -1:
                    self.currentAngle = min(self.currentAngle + delta, self.max)

                self.servo.angle(self.currentAngle)
                await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            self.stopServo()
            print("Servo stopped")

        except Exception as e:
            print("Unexpected exception in ServoController:", e)

    # ──────────────────────────────
    # Helpers
    # ──────────────────────────────

    def _shouldMove(self, angle: float) -> bool:
        if self.direction == 0:
            return False
        if self.direction == 1 and angle <= self.min:
            return False
        if self.direction == -1 and angle >= self.max:
            return False
        return True

    def stopServo(self):
        self.servo.angle(self.neutral)