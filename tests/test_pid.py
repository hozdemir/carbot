import unittest

from PID import INTEGRAL_MAX, INTEGRAL_MIN, PositionalPID


def step(pid, measurement, setpoint, inertia=0.01, sample=0.1):
    pid.SystemOutput = measurement
    pid.SetStepSignal(setpoint)
    pid.SetInertiaTime(inertia, sample)
    return pid.SystemOutput


class PositionalPIDTest(unittest.TestCase):
    def test_proportional_only_output_is_gain_times_error_without_smoothing(self):
        pid = PositionalPID(2.0, 0, 0)

        self.assertAlmostEqual(step(pid, measurement=100, setpoint=150, inertia=0), 100.0)

    def test_output_is_zero_when_the_target_is_centred(self):
        pid = PositionalPID(1.1, 0.2, 0.8)

        self.assertAlmostEqual(step(pid, measurement=150, setpoint=150), 0.0)

    def test_integral_uses_the_error_accumulated_before_the_step(self):
        pid = PositionalPID(0, 1.0, 0)

        self.assertAlmostEqual(step(pid, 140, 150, inertia=0), 0.0)
        self.assertAlmostEqual(step(pid, 140, 150, inertia=0), 10.0)
        self.assertAlmostEqual(step(pid, 140, 150, inertia=0), 20.0)

    def test_derivative_reacts_to_the_change_in_error(self):
        pid = PositionalPID(0, 0, 1.0)

        self.assertAlmostEqual(step(pid, 140, 150, inertia=0), 10.0)
        self.assertAlmostEqual(step(pid, 130, 150, inertia=0), 10.0)
        self.assertAlmostEqual(step(pid, 130, 150, inertia=0), 0.0)

    def test_integral_is_clamped_to_its_limits(self):
        high = PositionalPID(0, 1.0, 0)
        low = PositionalPID(0, 1.0, 0)

        for _ in range(100):
            step(high, 0, 1000, inertia=0)
            step(low, 1000, 0, inertia=0)

        self.assertAlmostEqual(step(high, 0, 1000, inertia=0), INTEGRAL_MAX)
        self.assertAlmostEqual(step(low, 1000, 0, inertia=0), INTEGRAL_MIN)

    def test_filter_blends_the_previous_output_with_the_new_one(self):
        pid = PositionalPID(1.0, 0, 0)

        first = step(pid, 100, 150, inertia=0.1, sample=0.1)
        second = step(pid, 100, 150, inertia=0.1, sample=0.1)

        self.assertAlmostEqual(first, 25.0)
        self.assertAlmostEqual(second, 37.5)

    def test_filter_state_is_independent_of_the_measurement_written_before_each_step(self):
        pid = PositionalPID(1.0, 0, 0)

        step(pid, 100, 150, inertia=0.1, sample=0.1)
        pid.SystemOutput = 9999
        pid.SetStepSignal(150)
        pid.SystemOutput = 100
        pid.SetInertiaTime(0.1, 0.1)

        self.assertAlmostEqual(pid.SystemOutput, (0.1 * 25.0 + 0.1 * (150 - 9999)) / 0.2)


if __name__ == "__main__":
    unittest.main()
