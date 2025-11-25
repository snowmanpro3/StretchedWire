import pyvisa
import time
import re
from typing import List

FLOAT_RE = re.compile(r'[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?')


class Keithley2182A:
    def __init__(self, resource: str = "GPIB0::7::INSTR"):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource)
        self.inst.timeout = 20000

        # ---- Инициализация ----
        self._write("*RST")
        time.sleep(0.2)
        self._write("*CLS")

        self._write(":SYST:AZER OFF")
        self._write(":SENS:FUNC 'VOLT'")
        self._write(":VOLT:NPLC 0.01")
        self._write(":FORM:ELEM READ")

        # Внутренний триггер
        self._write(":TRIG:SOUR IMM")
        self._write(":TRIG:COUN INF")   # бесконечные измерения

        # Непрерывная инициализация измерений
        self._write(":INIT:CONT ON")
        self._write(":INIT")

    def _write(self, cmd: str):
        self.inst.write(cmd)
        err = self.inst.query(":SYST:ERR?").strip()
        if not err.startswith('0'):
            print(f"[!] ERROR after '{cmd}': {err}")

    def fetch_voltage(self) -> float:
        """Получить очередное измерение (не создаёт новый триггер)."""
        raw = self.inst.query(":FETC?")
        m = FLOAT_RE.search(raw)
        return float(m.group()) if m else float("nan")

    def close(self):
        try:
            self.inst.close()
        except:
            pass
        try:
            self.rm.close()
        except:
            pass


# ---------------------- ТЕСТ ЗА 20 ТОЧЕК ----------------------
if __name__ == "__main__":
    RESOURCE = "GPIB0::7::INSTR"
    N = 1100     # сколько измерений сделать

    dev = Keithley2182A(resource=RESOURCE)

    voltages = []
    timestamps = []

    print(f"Запускаю {N} измерений по внутреннему триггеру...\n")

    start = time.perf_counter()

    for i in range(N):
        t = time.perf_counter()

        v = dev.fetch_voltage()
        voltages.append(v)
        timestamps.append(t - start)

        print(f"{i+1:02d}: {v: .9f} V   at t = {timestamps[-1]:.6f} s")

    dev.close()

    # --- Печать результатов ---
    print("\n--- Итоги ---")
    print(f"Всего измерений: {len(voltages)}")

    if len(timestamps) > 1:
        periods = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
        avg_period = sum(periods) / len(periods)
        print(f"Средний период: {avg_period:.6f} s")
        print(f"Средняя частота: {1/avg_period:.3f} Hz")




            


