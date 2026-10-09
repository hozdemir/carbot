import os
import tempfile
import unittest

from powerplant import PowerPlant


class PowerPlantTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.supplyPath = os.path.join(self.directory.name, "fusion-hat")
        self.cachePath = os.path.join(self.directory.name, "voltage_cache")

    def powerPlant(self):
        return PowerPlant({"SupplyPath": self.supplyPath, "VoltageCachePath": self.cachePath})

    def writeSupply(self, **files):
        os.makedirs(self.supplyPath, exist_ok=True)
        for name, value in files.items():
            with open(os.path.join(self.supplyPath, name), "w") as f:
                f.write("{}\n".format(value))

    def test_reads_the_level_and_charging_state_from_the_driver(self):
        self.writeSupply(capacity=73, status="Charging", voltage_now=7704000)

        self.assertEqual(self.powerPlant().getBatteryInfo(), [73, True])

    def test_discharging_is_not_charging(self):
        self.writeSupply(capacity=40, status="Discharging")

        self.assertEqual(self.powerPlant().getBatteryInfo(), [40, False])

    def test_full_does_not_mean_on_the_charger(self):
        self.writeSupply(capacity=99, status="Full")

        self.assertEqual(self.powerPlant().getBatteryInfo(), [99, False])

    def test_falls_back_to_the_driver_voltage_without_a_capacity(self):
        self.writeSupply(status="Discharging", voltage_now=7200000)

        self.assertEqual(self.powerPlant().getBatteryInfo(), [50, False])

    def test_falls_back_to_the_voltage_cache_without_the_driver(self):
        with open(self.cachePath, "w") as f:
            f.write("8.4\n")

        self.assertEqual(self.powerPlant().getBatteryInfo(), [100, False])

    def test_reports_nothing_when_the_battery_cannot_be_read(self):
        self.assertEqual(self.powerPlant().getBatteryInfo(), [0, False])

    def test_clamps_the_level(self):
        self.writeSupply(capacity=130, status="Charging")

        self.assertEqual(self.powerPlant().getBatteryInfo(), [100, True])

    def test_works_without_config(self):
        self.assertIsInstance(PowerPlant().getBatteryInfo(), list)


if __name__ == "__main__":
    unittest.main()
