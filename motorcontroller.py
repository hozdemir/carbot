from events import Events
from fusion_hat.pwm import PWM
from fusion_hat.pin import Pin
from fusion_hat.motor import Motor
import time

class MotorController:
    validBearings = ["n", "ne", "e", "se", "s", "sw", "w", "nw", "0"]

    def __init__(self, config, audioManager):
        driverConfig = config["DRIVER"]
        self.trim = float(driverConfig["Trim"])

        self.leftMotor = Motor('M1', is_reversed=True)  # Sol motor
        self.rightMotor = Motor('M2')  # Sağ motor

        self.leftTrim = 1 if self.trim >= 0 else 1 + self.trim
        self.rightTrim = 1 if self.trim <= 0 else 1 - self.trim

        # Hız oranları
        self.straightaway = float(driverConfig["Straightaway"])
        self.straightawaySlow = float(driverConfig["StraightawaySlow"])
        self.halfTurnUndersteer = float(driverConfig["HalfTurnUndersteer"])
        self.halfTurnSlowFactor = float(driverConfig["HalfTurnSlowFactor"])
        self.tankTurnSpeed = float(driverConfig["TankTurnSpeed"])
        self.tankTurnSpeedSlow = float(driverConfig["TankTurnSpeedSlow"])

        self.audioManager = audioManager
        self.audioToken = 'fe7a1846-a0bb-4a44-aa3e-5b080089d37a'

        self.MAX_SPEED = 20  # Gaz limiti %10

    def stopMotors(self):
        self.leftMotor.power(0)
        self.rightMotor.power(0)

    def setMotorSpeed(self, motor, speed, trim):
        speed = int(speed * trim)

        # Speed'i sınırla
        if speed > self.MAX_SPEED:
            speed = self.MAX_SPEED
        elif speed < -self.MAX_SPEED:
            speed = -self.MAX_SPEED

        motor.power(speed)

    def getTargetMotorDCs(self, targetBearing, slow):
        if targetBearing == "0":
            leftDC = 0
            rightDC = 0

        elif targetBearing == "n":
            leftDC = -100 * (self.straightawaySlow if slow else self.straightaway)
            rightDC = -100 * (self.straightawaySlow if slow else self.straightaway)

        elif targetBearing == "s":
            leftDC = 100 * (self.straightawaySlow if slow else self.straightaway)
            rightDC = 100 * (self.straightawaySlow if slow else self.straightaway)

        elif targetBearing == "ne":
            if not slow:
                leftDC = -100 * self.halfTurnUndersteer  # sol yavaş
                rightDC = -100                           # sağ hızlı
            else:
                leftDC = -100 * self.halfTurnUndersteer * self.halfTurnSlowFactor
                rightDC = -100 * self.halfTurnSlowFactor

        elif targetBearing == "nw":
            if not slow:
                leftDC = -100                           # sol hızlı
                rightDC = -100 * self.halfTurnUndersteer  # sağ yavaş
            else:
                leftDC = -100 * self.halfTurnSlowFactor
                rightDC = -100 * self.halfTurnUndersteer * self.halfTurnSlowFactor

        elif targetBearing == "se":
            if not slow:
                leftDC = 100 * self.halfTurnUndersteer  # sol yavaş
                rightDC = 100                           # sağ hızlı
            else:
                leftDC = 100 * self.halfTurnUndersteer * self.halfTurnSlowFactor
                rightDC = 100 * self.halfTurnSlowFactor

        elif targetBearing == "sw":
            if not slow:
                leftDC = 100                           # sol hızlı
                rightDC = 100 * self.halfTurnUndersteer  # sağ yavaş
            else:
                leftDC = 100 * self.halfTurnSlowFactor
                rightDC = 100 * self.halfTurnUndersteer * self.halfTurnSlowFactor

        elif targetBearing == "e":
            # Yerinde SAĞA dönüş (saat yönü)
            leftDC = -100 * (self.tankTurnSpeedSlow if slow else self.tankTurnSpeed)
            rightDC = -leftDC

        elif targetBearing == "w":
            # Yerinde SOLA dönüş (saat yönü tersi)
            rightDC = -100 * (self.tankTurnSpeedSlow if slow else self.tankTurnSpeed)
            leftDC = -rightDC

        else:
            raise Exception("Bad bearing: " + targetBearing)

        return int(leftDC), int(rightDC)

    def drive(self, forward, turn, minPower=0.0):
        """Continuous drive used by follow mode. forward and turn are fractions (-1..1) of MAX_SPEED: forward > 0
        drives forward, turn > 0 turns clockwise. A moving wheel gets at least minPower (a fraction of MAX_SPEED) so
        small corrections still overcome friction."""
        leftWheel = max(-1.0, min(1.0, forward + turn))
        rightWheel = max(-1.0, min(1.0, forward - turn))

        if leftWheel == 0 and rightWheel == 0:
            self.stopMotors()
            self.audioManager.restoreVolume(self.audioToken)
            Events.getInstance().fireMotionOff()
            return

        # Negative power drives forward on this chassis, the same as the "n" bearing.
        self.setMotorSpeed(self.leftMotor, -self._wheelPower(leftWheel, minPower), self.leftTrim)
        self.setMotorSpeed(self.rightMotor, -self._wheelPower(rightWheel, minPower), self.rightTrim)
        self.audioManager.lowerVolume(self.audioToken)
        Events.getInstance().fireMotionOn()

    def _wheelPower(self, fraction, minPower):
        if fraction == 0:
            return 0.0
        magnitude = minPower + (1.0 - minPower) * abs(fraction)
        return magnitude * self.MAX_SPEED * (1 if fraction > 0 else -1)

    def setBearing(self, bearing, slow):
        if bearing not in self.validBearings:
            raise ValueError("Invalid bearing: {}".format(bearing))

        leftDC, rightDC = self.getTargetMotorDCs(bearing, slow)

        if leftDC != 0 or rightDC != 0:
            self.setMotorSpeed(self.leftMotor, leftDC, self.leftTrim)
            self.setMotorSpeed(self.rightMotor, rightDC, self.rightTrim)
            self.audioManager.lowerVolume(self.audioToken)
            Events.getInstance().fireMotionOn()
        else:
            self.stopMotors()
            self.audioManager.restoreVolume(self.audioToken)
            Events.getInstance().fireMotionOff()