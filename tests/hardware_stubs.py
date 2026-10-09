"""Stand-ins for the Fusion HAT library so hardware-facing classes can be tested off the Pi."""
import sys
import types


class FakeMotor:
    def __init__(self, name, is_reversed=False):
        self.name = name
        self.powers = []

    def power(self, value):
        self.powers.append(value)

    @property
    def lastPower(self):
        return self.powers[-1] if self.powers else None


class FakeServo:
    def __init__(self, pin, offset=0.0, min=-90, max=90):
        self.angles = []

    def angle(self, value):
        self.angles.append(value)


def installFusionHatStubs():
    if "fusion_hat" in sys.modules:
        return

    package = types.ModuleType("fusion_hat")
    modules = {
        "fusion_hat.motor": {"Motor": FakeMotor},
        "fusion_hat.servo": {"Servo": FakeServo},
        "fusion_hat.pwm": {"PWM": object},
        "fusion_hat.pin": {"Pin": object},
    }
    sys.modules["fusion_hat"] = package
    for name, attributes in modules.items():
        module = types.ModuleType(name)
        for attribute, value in attributes.items():
            setattr(module, attribute, value)
        sys.modules[name] = module
        setattr(package, name.split(".")[1], module)


class FakeAudioManager:
    def lowerVolume(self, token):
        pass

    def restoreVolume(self, token):
        pass
