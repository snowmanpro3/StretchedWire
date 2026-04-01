from PyQt6.QtCore import QThread, pyqtSignal
import acsc_modified as acsc
import time
import numpy as np
from scipy.signal import savgol_filter


class SingleAxisWorker(QThread):
    """Поток для опроса одной оси с максимальной частотой"""
    update_signal = pyqtSignal(int, float, bool, bool)  # axis_id, position, moving, in_position
    error_signal = pyqtSignal(int, str)  # axis_id, error_message
    progress_signal = pyqtSignal(str)  # To send informational messages (like dual_print)

    def __init__(self, stand, axis_id):
        super().__init__()
        self.stand = stand      # Ссылка на контроллер ACS
        self.axis_id = axis_id  # ID оси (0, 1, 2, 3)
        self.running = False    # Флаг работы потока

    def run(self):
        """Основной цикл потока
        Код внутри этого метода выполняется в отдельном потоке, когда вызывается worker.start()
        """
        self.running = True
        while self.running:
            try:
                # Получаем данные оси
                pos = acsc.getFPosition(self.stand.hc, self.axis_id)
                axis_state = acsc.getAxisState(self.stand.hc, self.axis_id)
                mot_state = acsc.getMotorState(self.stand.hc, self.axis_id)
                
                # Отправляем в главный поток информацию об оси в текущей итерации
                self.update_signal.emit(
                    self.axis_id,
                    pos,
                    axis_state['moving'],
                    mot_state['in position']
                )
            except Exception as e:
                self.error_signal.emit(self.axis_id, str(e))
            
            self.msleep(100)  # Пауза 10 мс (можно уменьшить для более частого опроса)
            #! Здесь определяется частота обновления позиций

    def stop(self):
        """Корректная остановка потока"""
        self.running = False
        self.wait(500)  # Ожидаем завершения (таймаут 500 мс)


class FFIMeasurementWorker(QThread):
    log_ready = pyqtSignal(dict)
    error = pyqtSignal(str)
    pos_new = pyqtSignal(float)
    progress_signal = pyqtSignal(str)  # To send informational messages (like dual_print)

    def __init__(self, stand, axes, keithley, distance, speed, mode):
        super().__init__()
        self.stand = stand
        self.ffi_axes = axes
        self.keithley = keithley
        self.distance = distance
        self.speed = speed
        self.mode = mode
        self.running = True

    def run(self):
        distances = [-(self.distance/2), -(self.distance/2)]
        try:
            acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(self.ffi_axes), tuple(distances), acsc.SYNCHRONOUS)
            acsc.waitMotionEnd(self.stand.hc, self.ffi_axes[0], 20000)
        except Exception as e:
            self.progress_signal.emit(f"Ошибка при запуске синхронного движения: {e}")
            print(f"Ошибка при запуске синхронного движения: {e}")
        else:
            self.progress_signal.emit(f"Функция acsc.toPointM выполнена без ошибок, нить выведена на старт")
            print(f"Функция acsc.toPointM выполнена без ошибок, нить выведена на старт")
        time.sleep(0.2) #! Чтобы контроллер успел увидеть остановку оси???
        try:    
            distances = [self.distance, self.distance]
            acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(self.ffi_axes), tuple(distances), acsc.SYNCHRONOUS)
            time.sleep(0.2)
            #*acsc.toPointM сама добавляет -1 в конец списка осей
        except Exception as e:
            self.progress_signal.emit(f"Ошибка при запуске основного синхронного движения: {e}")
            print(f"Ошибка при запуске основного синхронного движения: {e}")
        else:
            self.progress_signal.emit(f"Измерение FFI успешно запущено, идёт измерение...")
            print(f"Измерение FFI успешно запущено, идёт измерение...")
        try:
            master = self.ffi_axes[0]
            log = {
                'time': [],
                'x_pos': [],
                'y_pos': [],
                'eds': [],
            }
            start_time = time.time()
            while self.running:
                eds = self.keithley.get_voltage()
                pos = acsc.getFPosition(self.stand.hc, master)
                log['eds'].append(eds)
                log['time'].append(time.time() - start_time)
                if self.mode == 'X':
                    log['x_pos'].append(pos)
                    log['y_pos'].append(0.0)
                elif self.mode == 'Y':
                    log['y_pos'].append(pos)
                    log['x_pos'].append(0.0)

                mot_state = acsc.getMotorState(self.stand.hc, master)
                if mot_state['in position']:
                    break
                time.sleep(0.01)
            self.log_ready.emit(log)
        except Exception as e:
            self.error.emit(str(e))


class SFIMeasurementWorker(QThread):
    log_ready = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress_signal = pyqtSignal(str)  # To send informational messages (like dual_print)

    def __init__(self, stand, axes, keithley, distance, speed, mode):
        super().__init__()
        self.stand = stand
        self.sfi_axes = axes
        self.keithley = keithley
        self.distance = distance
        self.speed = speed
        self.mode = mode
        self.running = True

    def run(self):
        distances = [-(self.distance/2), (self.distance/2)]
        try:
            acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(self.sfi_axes), tuple(distances), acsc.SYNCHRONOUS)
            acsc.waitMotionEnd(self.stand.hc, self.sfi_axes[0], 20000)
        except Exception as e:
            self.progress_signal.emit(f"Ошибка при запуске синхронного движения: {e}")
            print(f"Ошибка при запуске синхронного движения: {e}")
        else:
            self.progress_signal.emit(f"Функция acsc.toPointM выполнена без ошибок, нить выведена на старт")
            print(f"Функция acsc.toPointM выполнена без ошибок, нить выведена на старт")
        time.sleep(0.2) #! Чтобы контроллер успел увидеть остановку оси???

        try:    
            distances = [self.distance, -self.distance]
            acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(self.sfi_axes), tuple(distances), acsc.SYNCHRONOUS)
            #*acsc.toPointM сама добавляет -1 в конец списка осей
        except Exception as e:
            self.progress_signal.emit(f"Ошибка при запуске основного синхронного движения: {e}")
            print(f"Ошибка при запуске основного синхронного движения: {e}")
        else:
            self.progress_signal.emit(f"Измерение FFI успешно запущено, идёт измерение...")
            print(f"Измерение SFI успешно запущено, идёт измерение...")

        try:
            master = self.sfi_axes[0]
            slave = self.sfi_axes[1]
            log = {
                'time': [],
                'x_pos_0': [],
                'x_pos_1': [],
                'y_pos_0': [],
                'y_pos_1': [],
                'eds': [],
            }
            start_time = time.time()
            while self.running:
                eds = self.keithley.get_voltage()
                pos_m = acsc.getFPosition(self.stand.hc, master)
                pos_s = acsc.getFPosition(self.stand.hc, slave)
                log['time'].append(time.time() - start_time)
                log['eds'].append(eds)
                if self.mode == 'X':
                    log['x_pos_0'].append(pos_m)
                    log['x_pos_1'].append(pos_s)
                    log['y_pos_0'].append(0.0)
                    log['y_pos_1'].append(0.0)
                else:
                    log['y_pos_0'].append(pos_m)
                    log['y_pos_1'].append(pos_s)
                    log['x_pos_0'].append(0.0)
                    log['x_pos_1'].append(0.0)

                state = acsc.getMotorState(self.stand.hc, master)
                if state['in position']:
                    break
                time.sleep(0.01)
            self.log_ready.emit(log)
        except Exception as e:
            self.error.emit(str(e))


class CircularMotionWorker(QThread):
    progress_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    log_ready = pyqtSignal(dict)
    pos_new = pyqtSignal(float)

    def __init__(self, stand, keithley, speed, radius, rotation, N):
        super().__init__()
        self.stand = stand
        self.keithley = keithley
        self.speed = speed
        self.radius = radius
        self.rotation = rotation
        self.N = N #!!! Количество оборотов. Учесть в задании сегментов
        self.running = True
        self.masters = [0, 1]
        self.all_axes = [0, 1, 2, 3]

    def run(self):
        print(f"N: {self.N}, тип: {type(self.N)}")
        #* ПРЕДПОЛАГАЕТСЯ ЧТО НИТЬ НАХОДИТСЯ В ЦЕНТРЕ, Т.Е. НА МАГНИТНОЙ ОСИ
        try:
            #! Создаём две пары мастер слейв. Далее управляем только осями 0 и 1. 2 и 3 отражают их движение"
            program_0 = f"""
            MFLAGS(2).#DEFCON = 0
            CONNECT RPOS(2) = APOS(0)
            DEPENDS 2, 0
            MFLAGS(3).#DEFCON = 0
            CONNECT RPOS(3) = APOS(1)
            DEPENDS 3, 1
            GROUP (0,1,2,3)
            """

            acsc.cleanBuffer(self.stand.hc, 0)
            acsc.loadBuffer(self.stand.hc, 0, program_0)
            acsc.compileBuffer(self.stand.hc, 0)
            acsc.runBuffer(self.stand.hc, 0)

        except Exception as e:
            self.progress_signal.emit(f"Ошибка при создании master-slave пар: {e}")
            print(f"Ошибка при создании master-slave пар: {e}")
        else:
            self.progress_signal.emit(f"master-slave пары успешно созданы")
            print(f"master-slave пары успешно созданы")

        try:
            acsc.toPoint(self.stand.hc, acsc.AMF_RELATIVE, 1, -self.radius, acsc.SYNCHRONOUS)
            acsc.waitMotionEnd(self.stand.hc, 1, 20000)
        except Exception as e:
            self.progress_signal.emit(f"Ошибка при запуске выводе нити на старт (acsc.toPoint): {e}")
            print(f"Ошибка при запуске выводе нити на старт (toPoint): {e}")
        else:
            self.progress_signal.emit(f"Функция acsc.toPoint выполнена без ошибок, нить выведена на старт")
            print(f"Функция acsc.toPoint выполнена без ошибок, нить выведена на старт")


        try:
            program_1 = f"""
            MSEG (0,1),{0},{-self.radius} 
            """


            acsc.cleanBuffer(self.stand.hc, 1)
            acsc.loadBuffer(self.stand.hc, 1, program_1)

            program_2 = f"""
            ARC1 (0,1), {0},{0},{0},{self.radius},{self.rotation} ! Add arc segment with center(1,0), final point (1,-1, clockwise rotation.
            ARC1 (0,1), {0},{0},{0},{-self.radius},{self.rotation}
            """
            
            for _ in range(self.N - 1):
                acsc.appendBuffer(self.stand.hc, 1, program_2)

            program_3 = f"""
            ARC1 (0,1), {0},{0},{0},{self.radius},{self.rotation} ! Add arc segment with center(1,0), final point (1,-1, clockwise rotation.
            ARC1 (0,1), {0},{0},{0},{-self.radius},{self.rotation}
            ENDS (0,1)
            SPLITALL
            STOP
            """

            acsc.appendBuffer(self.stand.hc, 1, program_3)
            acsc.compileBuffer(self.stand.hc, 1)
            acsc.runBuffer(self.stand.hc, 1)

        except Exception as e:
            self.progress_signal.emit(f"Ошибка при запуске движения по окружности: {e}")
            print(f"шибка при запуске движения по окружности: {e}")
        else:
            self.progress_signal.emit(f"Гармонический анализ успешно запущен, идёт измерение...")
            print(f"Гармонический анализ успешно запущен, идёт измерение...")

        
        try:
            # master = self.ffi_axes[0]
            log = {
                'time': [],
                'x_pos': [],
                'y_pos': [],
                'eds': [],
            }
            start_time = time.time()
            while self.running:
                eds = self.keithley.get_voltage()
                x_pos = acsc.getFPosition(self.stand.hc, self.masters[1])
                y_pos = acsc.getFPosition(self.stand.hc, self.masters[0])
                log['eds'].append(eds)
                log['time'].append(time.time() - start_time)
                log['x_pos'].append(x_pos)
                log['y_pos'].append(y_pos)

                mot_state = acsc.getMotorState(self.stand.hc, self.masters[0])
                if mot_state['in position']:
                    break
                time.sleep(0.01)
            self.log_ready.emit(log)
        except Exception as e:
            self.error.emit(str(e))

        try:
            acsc.toPoint(self.stand.hc, acsc.AMF_RELATIVE, 1, self.radius, acsc.SYNCHRONOUS)
            acsc.waitMotionEnd(self.stand.hc, 1, 20000)
        except Exception as e:
            self.progress_signal.emit(f"Ошибка при возвращении нити в центр (acsc.toPoint): {e}")
            print(f"Ошибка при возвращении нити в центр (toPoint): {e}")
        else:
            self.progress_signal.emit(f"Функция acsc.toPoint выполнена без ошибок, нить возвращена в центр")
            print(f"Функция acsc.toPoint выполнена без ошибок, нить возвращена в центр")

    def stop(self):
        self.running = False
        self.progress_signal.emit("Получен сигнал остановки...")


class FindMagneticAxisWorker(QThread):
    # Signals to communicate with the main GUI thread
    progress_signal = pyqtSignal(str)  # To send informational messages (like dual_print)
    error_signal = pyqtSignal(str)    # To send error messages (like show_error)
    finished_signal = pyqtSignal(dict) # To send the final axis positions upon completion

    def __init__(self, stand, keithley, distance, speed, convergence_threshold, max_iterations, N=3):
        super().__init__()
        self.stand = stand
        self.keithley = keithley
        self.distance = distance
        self.speed = speed
        self.convergence_threshold = convergence_threshold
        self.max_iterations = max_iterations
        self.running = True
        self.L_wire = 2.0 # Длина нити для SFI, можно передавать как параметр
        self.N = N  # Количество проездов для усреднения одного замера

    def _perform_scan_and_find_center(self, scan_type, mode, axes_pair):
        master = axes_pair[0]
        slave = axes_pair[1]
        try:
            for axis_id in axes_pair:
                acsc.enable(self.stand.hc, axis_id)
                acsc.setVelocity(self.stand.hc, axis_id, self.speed)

            all_scan_integrals = []
            all_scan_positions = []

            #! Цикл проездов для усреднения

            for i in range(self.N):
                if not self.running: return None
                self.progress_signal.emit(f"Проезд {i + 1}/{self.N} для {scan_type}-{mode}...")

                start_offset_distance = -self.distance / 2.0
                scan_distance = self.distance
                
                initial_moves = np.array([0.0, 0.0])
                scan_moves = np.array([0.0, 0.0])

                if scan_type == "FFI":
                    initial_moves[:] = [start_offset_distance, start_offset_distance]
                    scan_moves[:] = [scan_distance, scan_distance]
                elif scan_type == "SFI":
                    initial_moves[:] = [start_offset_distance, -start_offset_distance]
                    scan_moves[:] = [scan_distance, -scan_distance]

                # Перемещение на старт сканирования
                acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(axes_pair), tuple(initial_moves), acsc.SYNCHRONOUS)
                acsc.waitMotionEnd(self.stand.hc, master, 30000)
                time.sleep(0.2)

                #! СБОР ДАННЫХ ДЛЯ ОДНОГО ПРОЕЗДА
                single_log = {'pos': [], 'eds': []}
                acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(axes_pair), tuple(scan_moves), acsc.SYNCHRONOUS)
                
                max_log_duration = (self.distance / self.speed) * 1.5 + 5
                log_end_time = time.time() + max_log_duration

                while time.time() < log_end_time and self.running:

                    pos_m = acsc.getFPosition(self.stand.hc, master)
                    eds_v = self.keithley.get_voltage()
                    single_log['pos_m'].append(pos_m)
                    single_log['eds'].append(eds_v)
                    if scan_type == "SFI": # Для SFI также сохраняем позицию ведомой оси
                        pos_s = acsc.getFPosition(self.stand.hc, slave)
                        single_log['pos_s'].append(pos_s)
                    
                    mot_state = acsc.getMotorState(self.stand.hc, master)
                    if mot_state['in position']: break
                    time.sleep(0.01)

                #! Возврат в исходную точку перед следующим проездом
                return_moves = -(initial_moves + scan_moves) # Векторное сложение через np.array
                acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(axes_pair), tuple(return_moves), acsc.SYNCHRONOUS)
                acsc.waitMotionEnd(self.stand.hc, master, 30000)

                # Обработка данных одного проезда
                pos_arr = np.array(single_log['pos'])
                eds_arr = np.array(single_log['eds'])
                
                if len(pos_arr) < 25: #! Пропускаем проезд с недостаточным количеством точек
                    self.progress_signal.emit("Меньше 25 точек в проезде, пропускаем его...")
                    continue #! Не заканчиваем цикл, а переходим к следующему проезду

                if scan_type == "FFI":
                    integral_values = eds_arr / self.speed
                else: # SFI
                    integral_values = (eds_arr * self.L_wire) / (2.0 * self.speed)
                
                all_scan_positions.append(pos_arr)
                all_scan_integrals.append(integral_values)
        
            if not all_scan_integrals: #! Если не выполнился цикл for i in range(self.N):
                self.error_signal.emit(f"Не удалось собрать данные ни для одного проезда.")
                return None

            self.progress_signal.emit("Усреднение результатов всех проездов...")
            min_pos = min([p.min() for p in all_scan_positions])
            max_pos = max([p.max() for p in all_scan_positions]) #! Получаем max и min координаты за все проезды
            common_pos_grid = np.linspace(min_pos, max_pos, num=200)

            interpolated_integrals = [np.interp(common_pos_grid, pos, integ) for pos, integ in zip(all_scan_positions, all_scan_integrals)]
            
            averaged_integrals = np.mean(np.array(interpolated_integrals), axis=0)

            if len(averaged_integrals) > 11:
                smoothed_integrals = savgol_filter(averaged_integrals, window_length=11, polyorder=2)
            else:
                smoothed_integrals = averaged_integrals

            sign = np.sign(smoothed_integrals)
            zero_crossings = np.where(np.diff(sign))[0]
            
            center_coord_abs = None
            if len(zero_crossings) > 0:
                idx1 = zero_crossings[0]
                idx2 = idx1 + 1
                y1, y2 = smoothed_integrals[idx1], smoothed_integrals[idx2]
                x1, x2 = common_pos_grid[idx1], common_pos_grid[idx2]
                center_coord_abs = x1 - y1 * (x2 - x1) / (y2 - y1)
            else:
                self.progress_signal.emit(f"Предупреждение: Пересечение нуля не найдено. Поиск по минимуму модуля.")
                min_idx = np.argmin(np.abs(smoothed_integrals))
                center_coord_abs = common_pos_grid[min_idx]
            
            self.progress_signal.emit(f"{scan_type} {mode}: Новый центр по усредненным данным: {center_coord_abs:.4f}")

            acsc.toPointM(self.stand.hc, 0, tuple(axes_pair), (center_coord_abs, center_coord_abs), acsc.SYNCHRONOUS)
            acsc.waitMotionEnd(self.stand.hc, master, 30000)
            
            return center_coord_abs

        except Exception as e:
            import traceback
            self.error_signal.emit(f"Критическая ошибка в _perform_scan... ({scan_type} {mode}): {e}\n{traceback.format_exc()}")
            return None

    def run(self):
        self.progress_signal.emit(f"Запуск поиска магнитной оси: Дистанция={self.distance} мм, Скорость={self.speed} мм/с")

        initial_positions = {i: acsc.getFPosition(self.stand.hc, i) for i in range(4)}
        self.progress_signal.emit(f"Начальные позиции (0,1,2,3): ({initial_positions[0]:.4f}, {initial_positions[1]:.4f}, {initial_positions[2]:.4f}, {initial_positions[3]:.4f})")

        last_positions = initial_positions
        
        for i in range(self.max_iterations):
            if not self.running: break
            self.progress_signal.emit(f"\n--- Итерация {i + 1} / {self.max_iterations} ---")

            # 1. FFI по X (оси 1, 3)
            self.progress_signal.emit("Шаг 1: FFI по X...")
            if self._perform_scan_and_center_worker('FFI', 'X', [1, 3]) is None: break
            
            # 2. FFI по Y (оси 0, 2)
            if not self.running: break
            self.progress_signal.emit("Шаг 2: FFI по Y...")
            if self._perform_scan_and_center_worker('FFI', 'Y', [0, 2]) is None: break

            # 3. SFI по X (оси 1, 3)
            if not self.running: break
            self.progress_signal.emit("Шаг 3: SFI по X...")
            if self._perform_scan_and_center_worker('SFI', 'X', [1, 3]) is None: break

            # 4. SFI по Y (оси 0, 2)
            if not self.running: break
            self.progress_signal.emit("Шаг 4: SFI по Y...")
            if self._perform_scan_and_center_worker('SFI', 'Y', [0, 2]) is None: break

            current_positions = {i: acsc.getFPosition(self.stand.hc, i) for i in range(4)}
            deltas = {axis: abs(current_positions[axis] - last_positions[axis]) for axis in range(4)}
            self.progress_signal.emit(f"Изменения за итерацию (Δ0,Δ1,Δ2,Δ3): ({deltas[0]:.4f}, {deltas[1]:.4f}, {deltas[2]:.4f}, {deltas[3]:.4f})")

            if all(d < self.convergence_threshold for d in deltas.values()):
                self.progress_signal.emit(f"Схождение достигнуто на итерации {i + 1}. Магнитная ось найдена.")
                break
            
            last_positions = current_positions
        else:
             self.progress_signal.emit(f"Достигнуто максимальное количество итераций ({self.max_iterations}) без схождения.")

        final_positions = {f"axis_{i}": acsc.getFPosition(self.stand.hc, i) for i in range(4)}
        self.progress_signal.emit("\n--- Поиск завершен ---")
        self.progress_signal.emit(f"Финальные координаты концов нити (0,1,2,3):")
        self.progress_signal.emit(f"  Ось 0 (Y1): {final_positions['axis_0']:.4f} мм")
        self.progress_signal.emit(f"  Ось 1 (X1): {final_positions['axis_1']:.4f} мм")
        self.progress_signal.emit(f"  Ось 2 (Y2): {final_positions['axis_2']:.4f} мм")
        self.progress_signal.emit(f"  Ось 3 (X2): {final_positions['axis_3']:.4f} мм")
        
        self.finished_signal.emit(final_positions)

    def stop(self):
        self.running = False
        self.progress_signal.emit("Получен сигнал остановки...")




class MagAxisWorker_like_CM(QThread):
    progress_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    log_ready = pyqtSignal(dict)
    pos_new = pyqtSignal(float)

    def __init__(self, stand, keithley, speed, radius, rotation, N, first_second_type):
        super().__init__()
        self.stand = stand
        self.keithley = keithley
        self.speed = speed
        self.radius = radius  #! Для поиска магнитной оси радиус должен рассчитаться из размеров апертуры и области поиска мб
        self.rotation = rotation
        self.N = N #!!! Количество оборотов. Учесть в задании сегментов
        self.running = True
        self.masters = [0, 1]
        self.all_axes = [0, 1, 2, 3]

    def run(self):
        print(f"N: {self.N}, тип: {type(self.N)}")
        #* ПРЕДПОЛАГАЕТСЯ ЧТО НИТЬ НАХОДИТСЯ В ЦЕНТРЕ, Т.Е. НА МАГНИТНОЙ ОСИ
        try:
            #! Создаём две пары мастер слейв. Далее управляем только осями 0 и 1. 2 и 3 повторяют их движение"
            program_0 = f"""
            MFLAGS(2).#DEFCON = 0
            CONNECT RPOS(2) = APOS(0)
            DEPENDS 2, 0
            MFLAGS(3).#DEFCON = 0
            CONNECT RPOS(3) = APOS(1)
            DEPENDS 3, 1
            GROUP (0,1,2,3)
            """

            acsc.cleanBuffer(self.stand.hc, 0)
            acsc.loadBuffer(self.stand.hc, 0, program_0)
            acsc.compileBuffer(self.stand.hc, 0)
            acsc.runBuffer(self.stand.hc, 0)

        except Exception as e:
            self.progress_signal.emit(f"Ошибка при создании master-slave пар: {e}")
            print(f"Ошибка при создании master-slave пар: {e}")
        else:
            self.progress_signal.emit(f"master-slave пары успешно созданы")
            print(f"master-slave пары успешно созданы")

        try:
            acsc.toPoint(self.stand.hc, acsc.AMF_RELATIVE, 1, -self.radius, acsc.SYNCHRONOUS)
            acsc.waitMotionEnd(self.stand.hc, 1, 20000)
        except Exception as e:
            self.progress_signal.emit(f"Ошибка при запуске выводе нити на старт (acsc.toPoint): {e}")
            print(f"Ошибка при запуске выводе нити на старт (toPoint): {e}")
        else:
            self.progress_signal.emit(f"Функция acsc.toPoint выполнена без ошибок, нить выведена на старт")
            print(f"Функция acsc.toPoint выполнена без ошибок, нить выведена на старт")


        try:
            program_1 = f"""
            MSEG (0,1),{0},{-self.radius} 
            """


            acsc.cleanBuffer(self.stand.hc, 1)
            acsc.loadBuffer(self.stand.hc, 1, program_1)

            program_2 = f"""
            ARC1 (0,1), {0},{0},{0},{self.radius},{self.rotation} ! Add arc segment with center(1,0), final point (1,-1, clockwise rotation.
            ARC1 (0,1), {0},{0},{0},{-self.radius},{self.rotation}
            """
            
            for _ in range(self.N - 1):
                acsc.appendBuffer(self.stand.hc, 1, program_2)

            program_3 = f"""
            ARC1 (0,1), {0},{0},{0},{self.radius},{self.rotation} ! Add arc segment with center(1,0), final point (1,-1, clockwise rotation.
            ARC1 (0,1), {0},{0},{0},{-self.radius},{self.rotation}
            ENDS (0,1)
            SPLITALL
            STOP
            """

            acsc.appendBuffer(self.stand.hc, 1, program_3)
            acsc.compileBuffer(self.stand.hc, 1)
            acsc.runBuffer(self.stand.hc, 1)

        except Exception as e:
            self.progress_signal.emit(f"Ошибка при запуске движения по окружности: {e}")
            print(f"шибка при запуске движения по окружности: {e}")
        else:
            self.progress_signal.emit(f"Гармонический анализ успешно запущен, идёт измерение...")
            print(f"Гармонический анализ успешно запущен, идёт измерение...")

        
        try:
            # master = self.ffi_axes[0]
            log = {
                'time': [],
                'x_pos': [],
                'y_pos': [],
                'eds': [],
            }
            start_time = time.time()
            while self.running:
                eds = self.keithley.get_voltage()
                x_pos = acsc.getFPosition(self.stand.hc, self.masters[1])
                y_pos = acsc.getFPosition(self.stand.hc, self.masters[0])
                log['eds'].append(eds)
                log['time'].append(time.time() - start_time)
                log['x_pos'].append(x_pos)
                log['y_pos'].append(y_pos)

                mot_state = acsc.getMotorState(self.stand.hc, self.masters[0])
                if mot_state['in position']:
                    break
                time.sleep(0.01)
            self.log_ready.emit(log)
        except Exception as e:
            self.error.emit(str(e))

        try:
            acsc.toPoint(self.stand.hc, acsc.AMF_RELATIVE, 1, self.radius, acsc.SYNCHRONOUS)
            acsc.waitMotionEnd(self.stand.hc, 1, 20000)
        except Exception as e:
            self.progress_signal.emit(f"Ошибка при возвращении нити в центр (acsc.toPoint): {e}")
            print(f"Ошибка при возвращении нити в центр (toPoint): {e}")
        else:
            self.progress_signal.emit(f"Функция acsc.toPoint выполнена без ошибок, нить возвращена в центр")
            print(f"Функция acsc.toPoint выполнена без ошибок, нить возвращена в центр")

    def stop(self):
        self.running = False
        self.progress_signal.emit("Получен сигнал остановки...")