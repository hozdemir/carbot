import os

DEFAULT_SUPPLY_PATH = "/sys/class/power_supply/fusion-hat"
DEFAULT_CACHE_PATH = "/home/pi/.battery_voltage_cache"

# Two-cell Li-ion range used when only a voltage is available.
EMPTY_VOLTAGE = 6.0
FULL_VOLTAGE = 8.4


class PowerPlant:
    """Reports the battery level and whether it is charging.

    The Fusion HAT driver registers the battery as a power supply, which gives the level and the charging state. When
    that is missing the voltage is read from a cache file instead, and charging cannot be told."""

    def __init__(self, powerConfig=None):
        powerConfig = powerConfig if powerConfig is not None else {}
        self.supplyPath = powerConfig.get("SupplyPath", DEFAULT_SUPPLY_PATH)
        self.cachePath = powerConfig.get("VoltageCachePath", DEFAULT_CACHE_PATH)
        self.lastIsError = False

    def getBatteryInfo(self):
        """Returns [percent, charging]; [0, False] when the battery cannot be read."""
        try:
            if os.path.isdir(self.supplyPath):
                info = self._readPowerSupply()
            else:
                info = [percentFromVoltage(self._readCachedVoltage()), False]

            if self.lastIsError:
                print("Battery readings restored")
                self.lastIsError = False
            return info

        except Exception as e:
            if not self.lastIsError:
                print("Could not read the battery: {}".format(e))
                self.lastIsError = True
            return [0, False]

    def _readPowerSupply(self):
        # The driver reports "Full" whenever the level is 98% or more and it is not charging, even off the charger,
        # so only "Charging" means the charger is connected.
        charging = self._read("status") == "Charging"

        capacity = self._read("capacity")
        if capacity is not None:
            return [clampPercent(int(capacity)), charging]

        microvolts = self._read("voltage_now")
        return [percentFromVoltage(int(microvolts) / 1000000), charging]

    def _read(self, name):
        path = os.path.join(self.supplyPath, name)
        if not os.path.isfile(path):
            return None
        with open(path, "r") as f:
            return f.read().strip()

    def _readCachedVoltage(self):
        with open(self.cachePath, "r") as f:
            return float(f.read().strip())


def percentFromVoltage(voltage):
    return clampPercent(int((voltage - EMPTY_VOLTAGE) * 100 / (FULL_VOLTAGE - EMPTY_VOLTAGE)))


def clampPercent(percent):
    return min(max(percent, 0), 100)
