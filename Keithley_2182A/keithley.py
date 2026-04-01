import pyvisa
import threading
import time
import re
from typing import List

FLOAT_RE = re.compile(r'[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?')

class Keithley2182A:
    def __init__(self, resource: str = "GPIB0::7::INSTR", mode: str = "meas"):
        assert mode in ("fetch", "meas"), "mode должен быть 'fetch' или 'meas'"
        self.mode = mode
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource)
        self.inst.timeout = 2000  # мс

        # ----------- Инициализация -----------
        self.inst.write("*RST")
        time.sleep(0.2)
        self.inst.write("*CLS")

        self.inst.write(f":SENS:CHAN 2")
        self.inst.write(":SYST:AZER OFF")
        self.inst.write(":SENS:FUNC 'VOLT:DC'")
        # self.inst.write(":SENS:VOLT:CHAN2:LPAS:STAT ON")
        # self.inst.write(":SENS:VOLT:CHAN2:DFIL:WIND 0.01")
        self.inst.write(":VOLT:NPLC 1")
        self.inst.write(":FORM:ELEM READ")

        # ВНУТРЕННИЙ триггер + непрерывные измерения
        self.inst.write(":TRIG:SOUR IMM")
        self.inst.write(":TRIG:COUNT INF")
        self.inst.write(":INIT:CONT ON")
        self.inst.write(":INIT")

    def get_voltage(self) -> float:
        """
        Получает значение ЭДС в вольтах.
        - В режиме 'fetch': читает последнее доступное измерение
        - В режиме 'meas': запускает новое измерение и ждёт результат
        """
        try:
            return float(self.inst.query(":FETCH?").strip())
        except Exception as e:
            print(f"[!] Ошибка при получении ЭДС: {e}")
            return float("nan")
        

    def get_voltage(self) -> float:  #! почему две одинаковые функции
        """
        Получает значение ЭДС:
        - В режиме 'fetch' — читает последнее готовое измерение
        - В режиме 'meas'  — ЧТО ДЕЛАТЬ НЕЛЬЗЯ: запускать новое измерение
        **НО** так как мы используем internal trigger, мы ВСЕГДА читаем FETC?
        """
        try:
            raw = self.inst.query(":FETC?")
            m = FLOAT_RE.search(raw)
            return float(m.group()) if m else float("nan") #! group() вернет строку с числом
        except Exception as e:
            print(f"[!] Ошибка при получении ЭДС: {e}")
            return float("nan")

    def close(self):
        """Закрывает соединение с вольтметром (исправлено)"""
        try:
            self.inst.close()
        except:
            pass
        try:
            self.rm.close()
        except:
            pass



    '''Дальнейшие функции только для тестов/диагностики. Запускать только из этого файла'''


    def keithley2182A():
        try:
            rm = pyvisa.ResourceManager()
            print(rm.list_resources())

            keithley = rm.open_resource("GPIB0::7::INSTR")
            keithley.timeout = 3000

            response = keithley.query("*IDN?")
            voltage = keithley.query(":READ?")
            print(f"Текущее напряжение: {voltage} В")
            keithley.close()

            if "KEITHLEY INSTRUMENTS INC.,MODEL 2182A" in response:
                print(f"Успешное подключение! Ответ прибора:\n{response}")
                return True
            else:
                print(f"Подключено неизвестное устройство. Ответ:\n{response}")
                return False

        except pyvisa.errors.VisaIOError as e:
            print(f"Ошибка подключения: {e}")
            return False
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
            return False
    # ------------------------------------------------------------------------------------


if __name__ == '__main__':
    nano = Keithley2182A(resource="GPIB0::7::INSTR", mode='meas')

    start_time = time.time()
    poll_interval = 0.01
    pos_log = []
    N = 0

    while N < 150:
        eds = nano.get_voltage()
        print(N, eds, time.time() - start_time)
        N += 1
        time.sleep(poll_interval)



