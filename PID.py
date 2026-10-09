"""Positional PID controller with a first-order output filter, used by the colour-tracking autopilot (main.py).

Usage per control step:

    pid.SystemOutput = measurement   # where the target currently is
    pid.SetStepSignal(setpoint)      # compute the raw PID output for this error
    pid.SetInertiaTime(T, Ts)        # smooth it; the result is left in pid.SystemOutput
"""

# The accumulated error is clamped so a target that stays off-centre for a long time cannot wind the integral up
# without bound. The limits are asymmetric because the autopilot was tuned with them.
INTEGRAL_MIN = -2500.0
INTEGRAL_MAX = 2000.0


class PositionalPID:
    def __init__(self, P, I, D):
        self.Kp = P
        self.Ki = I
        self.Kd = D

        # Read by SetStepSignal as the measurement, and written by SetInertiaTime as the filtered output.
        self.SystemOutput = 0.0

        self._rawOutput = 0.0
        self._filteredOutput = 0.0
        self._integral = 0.0
        self._previousError = 0.0

    def SetStepSignal(self, StepSignal):
        """Computes the raw PID output for the error between the setpoint and SystemOutput."""
        error = StepSignal - self.SystemOutput

        proportional = self.Kp * error
        integral = self.Ki * self._integral
        derivative = self.Kd * (error - self._previousError)
        self._rawOutput = proportional + integral + derivative

        # The integral term above uses the error accumulated before this step.
        self._integral = min(max(self._integral + error, INTEGRAL_MIN), INTEGRAL_MAX)
        self._previousError = error

    def SetInertiaTime(self, InertiaTime, SampleTime):
        """Low-pass filters the raw output with time constant InertiaTime over a SampleTime step."""
        self._filteredOutput = (InertiaTime * self._filteredOutput + SampleTime * self._rawOutput) / (
            InertiaTime + SampleTime
        )
        self.SystemOutput = self._filteredOutput
