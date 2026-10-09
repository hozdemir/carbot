import os

class PowerPlant:
    def __init__(self, cache_path="/home/pi/.battery_voltage_cache"):
        self.cache_path = cache_path
        self.lastIsError = False

    def getBatteryInfo(self):
        try:
            with open(self.cache_path, "r") as f:
                voltage = float(f.read().strip())  # Örn: 7.53

            # Şarj olma durumu — 7.4V üstü şarj oluyor diyelim
            charging = False #voltage > 7.4

            # Yüzde hesaplama — lineer (örnek)
            percent = int((voltage - 6.0) * 100 / (8.4 - 6.0))
            percent = min(max(percent, 0), 100)

            if self.lastIsError:
                print("⚡️ Pil durumu geri geldi.")
                self.lastIsError = False

            return [percent, charging]

        except Exception as e:
            if not self.lastIsError:
                print(f"❌ Pil bilgisi alınamadı: {e}")
                self.lastIsError = True
            return [0, False]