from dataclasses import dataclass
from typing import Optional

from detection import Detection

SEARCHING = "searching"
TRACKING = "tracking"
LOST = "lost"


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass(frozen=True)
class FollowSettings:
    # Desired target radius as a fraction of the frame height; the rover stops when the target looks this big.
    targetSize: float = 0.12
    # Horizontal error (-1..1) below which the rover does not turn.
    centerDeadband: float = 0.08
    # Relative size error below which the rover does not drive.
    sizeDeadband: float = 0.15
    turnKp: float = 0.9
    turnKd: float = 0.05
    maxTurn: float = 0.7
    forwardKp: float = 1.2
    maxForward: float = 0.7
    maxReverse: float = 0.3
    # With the target this far off-centre (-1..1) the rover only turns; between centre and here forward speed fades.
    turnBeforeDrive: float = 0.5
    # Tilt speed in degrees per second at full vertical error; the sign maps "target is lower" to the servo direction.
    tiltSpeed: float = 60.0
    tiltDirection: float = 1.0
    tiltDeadband: float = 0.1
    # Blend of the new detection into the smoothed position (1 = no smoothing).
    smoothing: float = 0.6
    # Seconds without a detection before the target counts as lost. The rover stands still while it waits.
    lostTimeout: float = 0.5
    # Turn speed while searching for a lost target towards the side it was last seen on (0 disables searching).
    searchTurn: float = 0.0
    searchDuration: float = 3.0

    @staticmethod
    def fromConfig(followConfig):
        defaults = FollowSettings()

        def read(key, default):
            return float(followConfig.get(key, default))

        return FollowSettings(
            targetSize=read("TargetSize", defaults.targetSize),
            centerDeadband=read("CenterDeadband", defaults.centerDeadband),
            sizeDeadband=read("SizeDeadband", defaults.sizeDeadband),
            turnKp=read("TurnKp", defaults.turnKp),
            turnKd=read("TurnKd", defaults.turnKd),
            maxTurn=read("MaxTurn", defaults.maxTurn),
            forwardKp=read("ForwardKp", defaults.forwardKp),
            maxForward=read("MaxForward", defaults.maxForward),
            maxReverse=read("MaxReverse", defaults.maxReverse),
            turnBeforeDrive=read("TurnBeforeDrive", defaults.turnBeforeDrive),
            tiltSpeed=read("TiltSpeed", defaults.tiltSpeed),
            tiltDirection=read("TiltDirection", defaults.tiltDirection),
            tiltDeadband=read("TiltDeadband", defaults.tiltDeadband),
            smoothing=read("Smoothing", defaults.smoothing),
            lostTimeout=read("LostTimeout", defaults.lostTimeout),
            searchTurn=read("SearchTurn", defaults.searchTurn),
            searchDuration=read("SearchDuration", defaults.searchDuration),
        )


@dataclass(frozen=True)
class FollowCommand:
    # Fractions of the motor limit: forward > 0 drives forward, turn > 0 turns clockwise (right).
    forward: float
    turn: float
    # Degrees to add to the tilt servo angle this step.
    tiltDelta: float
    state: str
    target: Optional[Detection]


class FollowController:
    """Turns target detections into drive commands: turn the body to centre the target horizontally, tilt the camera
    to centre it vertically, and drive to keep its apparent size at targetSize. Holds no hardware, so it can be tested
    with plain values."""

    def __init__(self, settings: FollowSettings):
        self.settings = settings
        self.reset()

    def reset(self):
        self.state = SEARCHING
        self.smoothed = None
        self.lastSeenAt = None
        self.lastUpdateAt = None
        self.lastSide = 0.0
        self.previousError = None

    def update(self, detection: Optional[Detection], now: float) -> FollowCommand:
        dt = 0.0 if self.lastUpdateAt is None else max(0.0, now - self.lastUpdateAt)
        self.lastUpdateAt = now

        if detection is None:
            return self._withoutTarget(now)

        self._smooth(detection)
        self.lastSeenAt = now
        self.state = TRACKING

        horizontalError = (self.smoothed.x - 0.5) * 2
        verticalError = (self.smoothed.y - 0.5) * 2
        sizeError = (self.settings.targetSize - self.smoothed.radius) / self.settings.targetSize
        self.lastSide = horizontalError

        return FollowCommand(
            forward=self._forward(sizeError, horizontalError),
            turn=self._turn(horizontalError, dt),
            tiltDelta=self._tiltDelta(verticalError, dt),
            state=self.state,
            target=self.smoothed,
        )

    def _smooth(self, detection):
        if self.smoothed is None or self.state != TRACKING:
            self.smoothed = detection
            self.previousError = None
            return

        blend = self.settings.smoothing
        self.smoothed = Detection(
            x=self.smoothed.x + blend * (detection.x - self.smoothed.x),
            y=self.smoothed.y + blend * (detection.y - self.smoothed.y),
            radius=self.smoothed.radius + blend * (detection.radius - self.smoothed.radius),
        )

    def _turn(self, error, dt):
        derivative = 0.0
        if self.previousError is not None and dt > 0:
            derivative = (error - self.previousError) / dt
        self.previousError = error

        if abs(error) < self.settings.centerDeadband:
            return 0.0

        turn = self.settings.turnKp * error + self.settings.turnKd * derivative
        return clamp(turn, -self.settings.maxTurn, self.settings.maxTurn)

    def _forward(self, sizeError, horizontalError):
        if abs(sizeError) < self.settings.sizeDeadband:
            return 0.0

        forward = clamp(self.settings.forwardKp * sizeError, -self.settings.maxReverse, self.settings.maxForward)

        # Face the target before driving at it, so the rover does not run past it in a wide arc.
        alignment = 1.0 - abs(horizontalError) / self.settings.turnBeforeDrive
        return forward * clamp(alignment, 0.0, 1.0)

    def _tiltDelta(self, error, dt):
        if abs(error) < self.settings.tiltDeadband:
            return 0.0

        return self.settings.tiltDirection * self.settings.tiltSpeed * error * dt

    def _withoutTarget(self, now):
        if self.lastSeenAt is None:
            return self._stopped(SEARCHING)

        missingFor = now - self.lastSeenAt
        if missingFor < self.settings.lostTimeout:
            # A dropped frame or two: hold still rather than act on a stale position.
            return self._stopped(self.state, self.smoothed)

        searchingFor = missingFor - self.settings.lostTimeout
        if self.settings.searchTurn > 0 and searchingFor < self.settings.searchDuration:
            self.state = SEARCHING
            direction = 1.0 if self.lastSide >= 0 else -1.0
            return FollowCommand(0.0, direction * self.settings.searchTurn, 0.0, self.state, None)

        self.state = LOST
        return self._stopped(LOST)

    def _stopped(self, state, target=None):
        self.state = state
        return FollowCommand(0.0, 0.0, 0.0, state, target)
