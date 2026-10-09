import asyncio
import time

from followcontroller import FollowController, FollowSettings, SEARCHING


class FollowMode:
    """Runs the follow loop while enabled: grab a camera frame, detect the target, and drive the motors and tilt servo
    from the FollowController's commands. It stops the rover and switches itself off when the browser stops sending
    heartbeats, when the battery runs low, or when anything in the loop fails."""

    def __init__(self, followConfig, camera, detector, motorController, servoController, heartbeat, powerPlant,
                 clock=time.monotonic):
        self.camera = camera
        self.detector = detector
        self.motorController = motorController
        self.servoController = servoController
        self.heartbeat = heartbeat
        self.powerPlant = powerPlant
        self.clock = clock

        self.controller = FollowController(FollowSettings.fromConfig(followConfig))
        self.period = 1.0 / float(followConfig.get("LoopHz", 15))
        self.minPower = float(followConfig.get("MinPower", 0.0))
        # 0 disables the check: the battery reading falls back to 0% when the voltage cache file is missing.
        self.minBatteryPercent = float(followConfig.get("MinBatteryPercent", 0))

        self.task = None
        self.lastCommand = None
        self.stopReason = None

    def isEnabled(self):
        return self.task is not None and not self.task.done()

    def enable(self):
        if self.isEnabled():
            return
        self.controller.reset()
        self.lastCommand = None
        self.stopReason = None
        self.task = asyncio.get_event_loop().create_task(self._loop())

    def disable(self, reason="turned off"):
        if self.task is not None and not self.task.done():
            self.task.cancel()
        self.task = None
        self.stopReason = reason
        self.motorController.drive(0.0, 0.0)

    def status(self):
        command = self.lastCommand
        target = None
        if command is not None and command.target is not None:
            target = {"x": command.target.x, "y": command.target.y, "radius": command.target.radius}

        return {
            "enabled": self.isEnabled(),
            "state": command.state if command is not None else SEARCHING,
            "target": target if self.isEnabled() else None,
            "stopReason": self.stopReason,
        }

    async def _loop(self):
        loop = asyncio.get_event_loop()
        try:
            while True:
                startedAt = self.clock()

                reason = self._reasonToStop()
                if reason is not None:
                    self._stopFromLoop(reason)
                    return

                detection = await loop.run_in_executor(None, self._captureAndDetect)
                command = self.controller.update(detection, self.clock())
                self.lastCommand = command

                self.motorController.drive(command.forward, command.turn, self.minPower)
                self.servoController.nudgeAngle(command.tiltDelta)

                elapsed = self.clock() - startedAt
                await asyncio.sleep(max(0.0, self.period - elapsed))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print("Follow mode stopped after an error: {}".format(e))
            self._stopFromLoop("error: {}".format(e))

    def _reasonToStop(self):
        if not self.heartbeat.isAlive():
            return "browser disconnected"

        if self.minBatteryPercent > 0:
            batteryPercent, _charging = self.powerPlant.getBatteryInfo()
            if batteryPercent < self.minBatteryPercent:
                return "battery low"

        return None

    def _captureAndDetect(self):
        return self.detector.detect(self.camera.captureFrame())

    def _stopFromLoop(self, reason):
        # The loop is ending on its own, so there is no task to cancel; clear it so isEnabled() reports off.
        self.task = None
        self.stopReason = reason
        self.motorController.drive(0.0, 0.0)
