import asyncio
import unittest

from detection import Detection
from followmode import FollowMode


class FakeCamera:
    def captureFrame(self):
        return "frame"


class FakeDetector:
    def __init__(self, detection=None, error=None):
        self.detection = detection
        self.error = error

    def detect(self, frame):
        if self.error is not None:
            raise self.error
        return self.detection


class FakeMotors:
    def __init__(self):
        self.commands = []

    def drive(self, forward, turn, minPower=0.0):
        self.commands.append((forward, turn))


class FakeServo:
    def __init__(self):
        self.nudges = []

    def nudgeAngle(self, delta):
        self.nudges.append(delta)


class FakeHeartbeat:
    def __init__(self):
        self.alive = True

    def isAlive(self):
        return self.alive


class FakePowerPlant:
    def __init__(self, percent=100):
        self.percent = percent

    def getBatteryInfo(self):
        return self.percent, False


class FollowModeTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.motors = FakeMotors()
        self.servo = FakeServo()
        self.heartbeat = FakeHeartbeat()

    def tearDown(self):
        # Let cancelled follow loops finish unwinding before the event loop closes.
        pending = asyncio.all_tasks(self.loop)
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.close()
        asyncio.set_event_loop(None)

    def followMode(self, detector, config=None, powerPlant=None):
        settings = {"LoopHz": "100", "Smoothing": "1"}
        settings.update(config or {})
        return FollowMode(settings, FakeCamera(), detector, self.motors, self.servo, self.heartbeat,
                          powerPlant or FakePowerPlant())

    def runFor(self, seconds):
        self.loop.run_until_complete(asyncio.sleep(seconds))

    def test_drives_towards_the_detected_target(self):
        mode = self.followMode(FakeDetector(Detection(x=0.9, y=0.5, radius=0.05)))

        mode.enable()
        self.runFor(0.05)
        mode.disable()

        forward, turn = self.motors.commands[0]
        self.assertGreater(turn, 0)
        self.assertEqual(self.motors.commands[-1], (0.0, 0.0))

    def test_reports_status_with_the_target_while_enabled(self):
        mode = self.followMode(FakeDetector(Detection(x=0.5, y=0.5, radius=0.12)))

        mode.enable()
        self.runFor(0.05)
        status = mode.status()
        mode.disable()

        self.assertTrue(status["enabled"])
        self.assertEqual(status["state"], "tracking")
        self.assertEqual(status["target"], {"x": 0.5, "y": 0.5, "radius": 0.12})
        self.assertFalse(mode.status()["enabled"])
        self.assertIsNone(mode.status()["target"])

    def test_stops_when_the_browser_stops_sending_heartbeats(self):
        mode = self.followMode(FakeDetector(Detection(x=0.9, y=0.5, radius=0.05)))

        mode.enable()
        self.runFor(0.03)
        self.heartbeat.alive = False
        self.runFor(0.05)

        self.assertFalse(mode.isEnabled())
        self.assertEqual(mode.status()["stopReason"], "browser disconnected")
        self.assertEqual(self.motors.commands[-1], (0.0, 0.0))

    def test_stops_when_the_battery_is_low(self):
        mode = self.followMode(FakeDetector(Detection(x=0.9, y=0.5, radius=0.05)),
                               config={"MinBatteryPercent": "20"}, powerPlant=FakePowerPlant(percent=10))

        mode.enable()
        self.runFor(0.05)

        self.assertFalse(mode.isEnabled())
        self.assertEqual(mode.status()["stopReason"], "battery low")
        self.assertEqual(self.motors.commands, [(0.0, 0.0)])

    def test_battery_check_is_off_by_default(self):
        mode = self.followMode(FakeDetector(None), powerPlant=FakePowerPlant(percent=0))

        mode.enable()
        self.runFor(0.03)
        enabled = mode.isEnabled()
        mode.disable()

        self.assertTrue(enabled)

    def test_stops_the_rover_when_detection_fails(self):
        mode = self.followMode(FakeDetector(error=RuntimeError("camera gone")))

        mode.enable()
        self.runFor(0.05)

        self.assertFalse(mode.isEnabled())
        self.assertEqual(mode.status()["stopReason"], "error: camera gone")
        self.assertEqual(self.motors.commands, [(0.0, 0.0)])

    def test_nudges_the_tilt_servo_towards_the_target(self):
        mode = self.followMode(FakeDetector(Detection(x=0.5, y=0.9, radius=0.12)))

        mode.enable()
        self.runFor(0.05)
        mode.disable()

        self.assertTrue(any(delta > 0 for delta in self.servo.nudges))

    def test_enabling_twice_keeps_a_single_loop(self):
        mode = self.followMode(FakeDetector(None))

        mode.enable()
        task = mode.task
        mode.enable()

        self.assertIs(mode.task, task)
        mode.disable()
        self.runFor(0.01)


if __name__ == "__main__":
    unittest.main()
