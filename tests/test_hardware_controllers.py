import asyncio
import configparser
import unittest

from tests.hardware_stubs import FakeAudioManager, installFusionHatStubs

installFusionHatStubs()

from events import Events  # noqa: E402
from motorcontroller import MotorController  # noqa: E402
from servocontroller import ServoController  # noqa: E402


def roverConfig(trim="0"):
    config = configparser.ConfigParser()
    config.read_dict({
        "DRIVER": {
            "Trim": trim,
            "Straightaway": "1",
            "StraightawaySlow": "0.2",
            "HalfTurnUndersteer": "0.2",
            "HalfTurnSlowFactor": "0.4",
            "TankTurnSpeed": "0.7",
            "TankTurnSpeedSlow": "0.35",
        },
        "SERVO": {"PWMPin": "P0", "Min": "-70", "Max": "90", "Neutral": "0"},
    })
    return config


class MotorControllerDriveTest(unittest.TestCase):
    def setUp(self):
        self.motionEvents = []
        Events.motionOn.append(self._onMotionOn)
        Events.motionOff.append(self._onMotionOff)
        self.motors = MotorController(roverConfig(), FakeAudioManager())

    def tearDown(self):
        Events.motionOn.remove(self._onMotionOn)
        Events.motionOff.remove(self._onMotionOff)

    def _onMotionOn(self):
        self.motionEvents.append("on")

    def _onMotionOff(self):
        self.motionEvents.append("off")

    def powers(self):
        return self.motors.leftMotor.lastPower, self.motors.rightMotor.lastPower

    def test_driving_forward_uses_the_same_sign_as_the_n_bearing(self):
        self.motors.setBearing("n", False)
        bearingPowers = self.powers()

        self.motors.drive(1.0, 0.0)

        self.assertEqual(self.powers(), bearingPowers)
        self.assertLess(self.powers()[0], 0)

    def test_turning_right_matches_the_e_bearing_direction(self):
        self.motors.drive(0.0, 1.0)

        left, right = self.powers()
        self.assertLess(left, 0)
        self.assertGreater(right, 0)

    def test_powers_are_fractions_of_max_speed(self):
        self.motors.drive(0.5, 0.0)

        self.assertEqual(self.powers(), (-self.motors.MAX_SPEED // 2, -self.motors.MAX_SPEED // 2))

    def test_wheel_commands_are_clamped(self):
        self.motors.drive(1.0, 1.0)

        self.assertEqual(self.powers(), (-self.motors.MAX_SPEED, 0))

    def test_moving_wheels_get_at_least_the_minimum_power(self):
        self.motors.drive(0.05, 0.0, minPower=0.5)

        left, right = self.powers()
        self.assertLessEqual(left, -self.motors.MAX_SPEED * 0.5)
        self.assertEqual(left, right)

    def test_minimum_power_does_not_move_a_stopped_wheel(self):
        self.motors.drive(0.5, 0.5, minPower=0.5)

        self.assertEqual(self.powers()[1], 0)

    def test_zero_command_stops_and_reports_motion_off(self):
        self.motors.drive(0.5, 0.0)
        self.motors.drive(0.0, 0.0)

        self.assertEqual(self.powers(), (0, 0))
        self.assertEqual(self.motionEvents, ["on", "off"])

    def test_trim_reduces_one_side(self):
        motors = MotorController(roverConfig(trim="0.5"), FakeAudioManager())

        motors.drive(1.0, 0.0)

        self.assertEqual(motors.leftMotor.lastPower, -motors.MAX_SPEED)
        self.assertEqual(motors.rightMotor.lastPower, -motors.MAX_SPEED // 2)


class ServoControllerNudgeTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.servo = ServoController(roverConfig(), FakeAudioManager())
        # Let the timing loop move the servo to neutral and wait for look commands.
        self.loop.run_until_complete(asyncio.sleep(0))

    def tearDown(self):
        self.servo.task.cancel()
        self.loop.run_until_complete(asyncio.sleep(0))
        self.loop.close()
        asyncio.set_event_loop(None)

    def test_nudges_the_servo_from_its_current_angle(self):
        self.servo.nudgeAngle(10)
        self.servo.nudgeAngle(5)

        self.assertEqual(self.servo.servo.angles[-1], 15)

    def test_nudge_is_clamped_to_the_servo_limits(self):
        self.servo.nudgeAngle(500)

        self.assertEqual(self.servo.servo.angles[-1], 90)

    def test_does_not_nudge_while_the_user_is_moving_the_camera(self):
        self.servo.direction = 1
        movesBefore = len(self.servo.servo.angles)

        self.servo.nudgeAngle(10)

        self.assertEqual(len(self.servo.servo.angles), movesBefore)

    def test_look_keys_continue_from_the_nudged_angle(self):
        self.servo.nudgeAngle(20)

        self.loop.run_until_complete(self.servo.backward())
        self.loop.run_until_complete(asyncio.sleep(0.12))
        self.loop.run_until_complete(self.servo.lookStop())

        self.assertGreater(self.servo.currentAngle, 20)


if __name__ == "__main__":
    unittest.main()
