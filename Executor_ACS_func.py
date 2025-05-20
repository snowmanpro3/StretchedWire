# -*- coding: utf-8 -*-
"""
ACS Controller Executable Script
-----------------------------------
This script connects to the ACS controller and manages axis positions
"""

from __future__ import division, print_function
import acsc_modified as acsc
import newACS
from Calculation import Calculations as calc #!КАК ИМПОРТИРОВАТЬ
from Keithley_2182A.keithley import Keithley2182A as ktl
import time
from PyQt6 import QtGui
import io
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QPlainTextEdit
from PyQt6.QtGui import QTextCursor, QColor
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QThread, pyqtSlot
# Импортируем сгенерированный класс. Команда: pyuic6 GUI_for_controller_with_tabs2.ui -o GUI_for_controller_with_tabs2.py
from GUI_for_controller_with_tabs2 import Ui_MainWindow
import numpy as np
import csv
import matplotlib.pyplot as plt
import traceback


class SingleAxisWorker(QThread):
    """Поток для опроса одной оси с максимальной частотой"""
    update_signal = pyqtSignal(int, float, bool, bool)  # axis_id, position, moving, in_position
    error_signal = pyqtSignal(int, str)  # axis_id, error_message

    def __init__(self, stand, axis_id):
        super().__init__()
        self.stand = stand      # Ссылка на контроллер ACS
        self.axis_id = axis_id  # ID оси (0, 1, 2, 3)
        self.running = False    # Флаг работы потока

    def run(self):
        """Основной цикл потока"""
        self.running = True
        while self.running:
            try:
                # Получаем данные оси
                pos = self.stand.axes[self.axis_id].get_pos()
                axis_state = acsc.getAxisState(self.stand.hc, self.axis_id)
                mot_state = acsc.getMotorState(self.stand.hc, self.axis_id)
                
                # Отправляем в главный поток
                self.update_signal.emit(
                    self.axis_id,
                    pos,
                    axis_state['moving'],
                    mot_state['in position']
                )
            except Exception as e:
                self.error_signal.emit(self.axis_id, str(e))
            
            self.msleep(100)  # Пауза 10 мс (можно уменьшить для более частого опроса)

    def stop(self):
        """Корректная остановка потока"""
        self.running = False
        self.wait(500)  # Ожидаем завершения (таймаут 500 мс)


class ACSControllerGUI(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # Инициализация интерфейса
        self.stand = None
        self.axis_workers = {}  # Словарь: {axis_id: worker}
        
        # Настройка окна для вывода принтов
        #?? Блок настройки логгера
        self._setup_logger()
        
        # Тестовый вывод
        self.dual_print(self.Console, "Программа запущена!")


        # Создаём словари для 4 осей:
        '''Где есть getattr(self, f"чётотам{i}") - это функция, которая возвращает объект QLineEdit для ввода перемещения оси i.'''
        self.axes_data = {
            i: {
                "state": False,
                "speed_input": getattr(self, f"speed_input_{i}"),
                "acceleration_input": getattr(self, f"acceleration_input_{i}"),
                "deceleration_input": getattr(self, f"deceleration_input_{i}"),
                "kill_deceleration_input": getattr(self, f"kill_deceleration_input_{i}"),
                "jerk_input": getattr(self, f"jerk_input_{i}"),
                "axis_state_indicator": getattr(self, f"axis_state_indicator_{i}"),
                "pos_label": getattr(self, f"pos_label_{i}"),
                "is_moving_label": getattr(self, f"is_moving_label_{i}"),
                "is_acc_label": getattr(self, f"is_acc_label_{i}"),
                "is_in_pos_label": getattr(self, f"is_in_pos_label_{i}"),
                "is_in_pos_indicator": getattr(self, f"is_in_pos_indicator_{i}"),
                "choose_axis_button": getattr(self, f"choose_axis_{i}"),
                "enable_axis_button": getattr(self, f"enable_axis_button_{i}"),
                "start_axis_button": getattr(self, f"start_axis_{i}"),
                "move_distance": getattr(self, f"move_by_input_{i}"),
                "current_pos": 0.0,
                "axis_obj": None, #!Здесь хранятся ссылки на ось как объект из модуля newACS, к которым можно применять его методы
                "is_moving_indicator": getattr(self, f"is_moving_indicator_{i}")
            }
            for i in range(4)
        }

        self.connect_ui_elements()                               # Подключаем функции к элементам интерфейса
        self.selected_axes = []

        # self.pos_timer = QTimer(self)                            # Таймер для обновления current_pos
        # self.pos_timer.setInterval(250)                          # Обновление позиций каждые 250 мс
        # self.pos_timer.timeout.connect(self.update_positions)    # Вызываем функцию update_positions каждый период таймера

    def connect_ui_elements(self):                               # Кнопки общего действия: старт, стоп, ресет
        self.connect_button.clicked.connect(self.connect_to_controller)
        self.reset_button.clicked.connect(self.set_default_values)
        self.zeropos_button.clicked.connect(self.zeropos_axes)
        self.start_choosen_axis_button.clicked.connect(self.startM)
        self.stop_button.clicked.connect(self.stop_all_axes)
        self.stop_button_2.clicked.connect(self.stop_all_axes)
        self.start_mode_motion.clicked.connect(self.check_mode_then_start)
        self.stop_button_test.clicked.connect(self.stop_all_axes)
        self.start_mode_motion_test.clicked.connect(self.check_mode_then_start_test)
        

        for i in range(4):
            '''Перед connect стоит т.н. сигнал, а сам connect связывает сигнал с обработчиком'''
            data = self.axes_data[i]
            data["speed_input"].textChanged.connect(lambda text, ax=i: self.set_speed(ax, text))
            data["acceleration_input"].textChanged.connect(lambda text, ax=i: self.set_acceleration(ax, text))
            data["deceleration_input"].textChanged.connect(lambda text, ax=i: self.set_deceleration(ax, text))
            data["kill_deceleration_input"].textChanged.connect(lambda text, ax=i: self.set_kill_deceleration(ax, text))
            data["jerk_input"].textChanged.connect(lambda text, ax=i: self.set_jerk(ax, text))
            data["move_distance"].textChanged.connect(lambda text, ax=i: self.set_move_distance(ax, text))
            data["enable_axis_button"].clicked.connect(lambda checked, ax=i: self.toggle_axis(ax))
            data["start_axis_button"].clicked.connect(lambda checked, ax=i: self.start(ax))
            data["choose_axis_button"].stateChanged.connect(lambda state, ax=i: self.update_selected_axes(ax, state))

    def set_default_values(self): # Выставляет дефолтные параметры движения осей в общем окне
        for i in range(4):
            axis = self.axes_data[i]
            axis["speed_input"].setText("0.2")
            axis["acceleration_input"].setText("100")
            axis["deceleration_input"].setText("100")
            axis["kill_deceleration_input"].setText("166.67")
            axis["jerk_input"].setText("133.33")
    
    def dual_print(self, log_window, message):
        """
        Основной метод вывода:
        - message: текст сообщения
        - print(): вывод в консоль
        - appendPlainText(): вывод в GUI
        - _auto_scroll(): прокрутка вниз
        """
        print(message)  # Консольный вывод
        self.Console.appendPlainText(message)  # GUI-вывод
        self._auto_scroll()  # Автопрокрутка

    def _setup_logger(self):
        """Приватный метод для настройки логгера"""
        # 1. Делаем лог только для чтения
        self.Console.setReadOnly(True)
        
        # 2. Отключаем перенос строк (удобно для логов)
        self.Console.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        # 3. Опционально: задаем шрифт с фиксированной шириной
        font = self.Console.font()
        font.setFamily("Courier New")  # Моноширинный шрифт
        self.Console.setFont(font)

    def _auto_scroll(self):
        """Приватный метод для автопрокрутки"""
        cursor = self.Console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.Console.setTextCursor(cursor)

    def clear_logs(self):
        """Очистка лога"""
        self.Console.clear()


    def zeropos_axes(self):
        self.axes_data[0]["axis_obj"].set_pos(0)
        self.axes_data[1]["axis_obj"].set_pos(0)
        self.axes_data[2]["axis_obj"].set_pos(0)
        self.axes_data[3]["axis_obj"].set_pos(0)
        pass

    def connect_to_controller(self):
        """Подключается к контроллеру. Инициализирует оси как объекты в ключе 'axis_obj """
        self.stand = newACS.newAcsController(newACS.acs_ip, newACS.acs_port, contype='Ethernet', n_axes=4)
        if self.stand.connect() == -1:
            self.show_error("Ошибка подключения к контроллеру")
            self.label.setStyleSheet('background-color: red')
            self.stand = None
        else:
            self.label.setStyleSheet('background-color: green')
            # self.set_default_values() # Устанавливаем дефолтные значения при успешном подключении
            for i in range(4):        # После успешного подключения обновляем ссылки на оси в словарях
                self.axes_data[i]["axis_obj"] = self.stand.axes[i]
                

    def toggle_axis(self, axis):
        """Включает/выключает ось. Присваивает ключу 'state' значение True или False"""
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return
        
        data = self.axes_data[axis] #! Короткая ссылка
        if data["state"]:
            data['axis_obj'].disable()
            data["axis_state_indicator"].setStyleSheet('background-color: red')
            data["state"] = False
        else:
            data['axis_obj'].enable()
            data["axis_state_indicator"].setStyleSheet('background-color: green')
            data["state"] = True

    def update_selected_axes(self, axis, state):
        """Обновляет список выбранных осей."""
        state = Qt.CheckState(state) # Эта строка преобразует число в понятное для Qt значение (мб 'checked')
        if state == Qt.CheckState.Checked:  # Если галочка поставлена
            if axis not in self.selected_axes:
                self.selected_axes.append(axis)
                self.selected_axes = sorted(self.selected_axes)
                print('Добавили в список')
        if state == Qt.CheckState.Unchecked:  # Если галочка снята
            if axis in self.selected_axes:
                self.selected_axes.remove(axis)
                print('Удалили из списка')
        print(f'Список выбранных осей: {self.selected_axes}')

    def set_speed(self, axis, text):
        if not self.stand:
            # self.show_error("Контроллер не подключён!")
            return
        
        data = self.axes_data[axis]
        try:
            speed = float(text)
            data['axis_obj'].set_speed(speed) # Передаём значение в контроллер
            data["speed"] = speed # Сохраняем скорость в словаре для оси `axis`
        except ValueError:
            self.show_error("Некорректный ввод скорости")

    def set_acceleration(self, axis, text):
        if not self.stand:
            # self.show_error("Контроллер не подключён!")
            return
        
        data = self.axes_data[axis]
        try:
            acceleration = float(text)
            data['axis_obj'].set_acceleration(acceleration) # Это другая set_acceleration из модуля newACS
            data["acceleration"] = acceleration  # Сохраняем ускорение в словаре для оси `axis`
        except ValueError:
            self.show_error("Некорректный ввод скорости")

    def set_deceleration (self, axis, text):
        if not self.stand:
            # self.show_error("Контроллер не подключён!")
            return
        
        data = self.axes_data[axis]
        try:
            deceleration = float(text)
            data['axis_obj'].set_deceleration(deceleration) # Передаём значение в контроллер
            data["deceleration"] = deceleration  # Сохраняем замедление в словаре для оси `axis`
        except ValueError:
            self.show_error("Некорректный ввод скорости")

    def set_kill_deceleration (self, axis, text):
        if not self.stand:
            # self.show_error("Контроллер не подключён!")
            return

        data = self.axes_data[axis]
        try:
            kill_deceleration = float(text)
            data['axis_obj'].set_kill_deceleration(kill_deceleration) # Передаём значение в контроллер
            data["kill_deceleration"] = kill_deceleration  # Сохраняем замедление в словаре для оси `axis`
        except ValueError:
            self.show_error("Некорректный ввод скорости")

    def set_jerk(self, axis, text):
        if not self.stand:
            # self.show_error("Контроллер не подключён!")
            return

        data = self.axes_data[axis]
        try:
            jerk = float(text)
            data['axis_obj'].set_jerk(jerk) # Передаём значение в контроллер
            data["jerk"] = jerk  # Сохраняем рывок в словаре для оси `axis`
        except ValueError:
            self.show_error("Некорректный ввод скорости")

    def set_move_distance(self, axis, text):
        if not self.stand:
            # self.show_error("Контроллер не подключён!")
            return

        data = self.axes_data[axis]
        try:
            distance = float(text)
            data["move_distance"] = distance
        except ValueError:
            self.show_error("Некорректный ввод перемещения")

    def start(self, axis):
        '''Простое перемещение одной оси (тестовое)'''
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return
        
        self.oneAxisLog = {  # Инициализация лога
            'time': [],
            'pos': [],
        }

        data = self.axes_data[axis]
        if data['state'] and axis in self.selected_axes:
            try:
                '''Здесь amf_relative - это флаг, который указывает, что перемещение будет относительным.'''
                acsc.toPoint(self.stand.hc, acsc.AMF_RELATIVE, axis, data['move_distance'], acsc.SYNCHRONOUS)
                data["is_in_pos_indicator"].setStyleSheet("background-color:rgb(255, 0, 0)")
                start_time = time.time()
                poll_interval = 0.05
                self.start_position_updates()
            except Exception as e:
                self.show_error(f"Ошибка при запуске движения оси {axis}: {e}")
        else:
            self.show_error(f"Ось {axis} не включена или не выбрана!")

    def startM(self):
        '''Синхронный старт движения выбранныхосей'''
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return
        
        data = self.axes_data
        move_distances = []
        self.startpointM = data[self.selected_axes[0]]['axis_obj'].get_pos()
        leader = self.selected_axes[0]
        for i in self.selected_axes:
            if data[i]['state'] and data[i]['move_distance'] != 0:
                move_distances.append(data[i]['move_distance'])
        try:
            '''
            Здесь функция toPointM вызывается напрямую из модуля acsc_modified
            ТАМ УЖЕ ДОБАВЛЯЕТСЯ -1 В КОНЦЕ СПИСКА ОСЕЙ!!!!!!!!!!!!
            Здесь acsc.AMF_RELATIVE - это флаг, который указывает, что перемещение будет относительным.
            '''
            acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(self.selected_axes), tuple(move_distances), acsc.SYNCHRONOUS)
            for i in self.selected_axes:
                data[i]["is_in_pos_indicator"].setStyleSheet("background-color:rgb(255, 0, 0)")
            print('Успешно запущенно движение осей')
            # Запускаем таймер обновления позиций
            self.start_position_updates()
        except Exception as e:
            self.show_error(f"Ошибка при запуске движения: {e}")

    def stop_all_axes(self):
        """Останавливает все оси."""
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return

        try:
            acsc.killAll(self.stand.hc, acsc.SYNCHRONOUS)
        except Exception as e:
            self.show_error(f"Ошибка при остановке осей: {e}")

    def show_error(self, message):
        """Показывает сообщение об ошибке."""
        QMessageBox.critical(self, "Ошибка", message)


    def start_position_updates(self):
        """Запуск отдельного потока для каждой выбранной оси"""
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return

        for axis_id in self.selected_axes:
            # Останавливаем предыдущий поток оси, если был
            if axis_id in self.axis_workers:
                self.axis_workers[axis_id].stop()

            # Создаём и настраиваем новый поток
            worker = SingleAxisWorker(self.stand, axis_id)
            worker.update_signal.connect(self.handle_axis_update)
            worker.error_signal.connect(self.handle_axis_error)
            worker.start()
            
            self.axis_workers[axis_id] = worker

    def stop_position_updates(self):
        """Остановка всех потоков осей"""
        for axis_id, worker in self.axis_workers.items():
            worker.stop()
        self.axis_workers.clear()

    @pyqtSlot(int, float, bool, bool)
    def handle_axis_update(self, axis_id, pos, moving, in_pos):
        """Обновление данных оси в GUI (выполняется в главном потоке)"""
        axis_data = self.axes_data[axis_id]
        
        # Обновляем значения
        axis_data["pos_label"].setText(f"Позиция: {pos:.4f} мм")
        axis_data["is_moving_label"].setText(f"Движение: {'Да' if moving else 'Нет'}")
        axis_data["is_in_pos_label"].setText(f"На месте: {'Да' if in_pos else 'Нет'}")

        # Меняем цвет индикаторов
        moving_color = "rgb(0, 128, 0)" if moving else "rgb(255, 0, 0)"  # Красный/Зелёный
        in_pos_color = "rgb(0, 128, 0)" if in_pos else "rgb(255, 0, 0)"
        
        axis_data["is_moving_indicator"].setStyleSheet(f"background-color: {moving_color}")
        axis_data["is_in_pos_indicator"].setStyleSheet(f"background-color: {in_pos_color}")

    @pyqtSlot(int, str)
    def handle_axis_error(self, axis_id, error_msg):
        """Обработка ошибок оси"""
        self.show_error(f"Ось {axis_id}: {error_msg}")
        if axis_id in self.axis_workers:
            self.axis_workers[axis_id].stop()

    def closeEvent(self, event):
        """Остановка потоков при закрытии окна"""
        self.stop_position_updates()
        super().closeEvent(event)

    def findMagAxis(self):
        '''
        Сначала необходимо на странице настроек/управления расположить нить на
        предополагаемую магнитную ось (на глаз)
        '''
        #! x-компонента (СНАЧАЛА довести до ума первый и второй интеграл, т.к. нахождение оси с их помощью)
        pass



    #TODO добавить провекру на совпадение координат противположных осей???
    def start_circular_motion(self): #! ПОКА ЧТО НАЧИНАЕТ ДВИЖЕНИЕ ИЗ ТОЧКИ ГДЕ СЕЙЧАС НАХОДИТСЯ
        """
        Запускает движение нити по окружности с заданными параметрами.
        Концы нити всегда находятся в одних и тех же координатах.
        """
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return

        # Инициализация лога координат
        self.circular_motion_log = {
            'time': [],
            'theta': [],
            'x_pos': [],
            'y_pos': [],
            'eds':[],
        }
        self.start_time = time.time()
        vector_velocity = float(self.circ_speed_input.text())
        radius = float(self.circ_radius_input.text())

        axesM = [0, 1, 2, 3]  # List of axes to move (all) for toPointM
        leader = axesM[0]

        center_x = self.axes_data[1]["axis_obj"].get_pos()  # Получаем текущую позицию оси 1
        center_y = self.axes_data[0]["axis_obj"].get_pos()  # Получаем текущую позицию оси 0
        circle_angle_rad = 2*np.pi  # Whole circle
        center_point = [center_x, center_y]
        center_points = [center_y, center_x, center_y, center_x]

        start_x = center_x + radius
        start_y = center_y
        start_point = [start_x, start_y]
        start_points = [start_y, start_x, start_y, start_x]

        self.stand.enable_all()  # Включаем все оси перед движением
        acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, axesM, start_points, acsc.SYNCHRONOUS)
        acsc.waitMotionEnd(self.stand.hc, leader, 30000)
        print('Прибыла в начальную точку')

        try:
            acsc.extendedSegmentedMotionV2(self.stand.hc, acsc.AMF_VELOCITY,
                                        axesM, start_points,
                                        vector_velocity, #? Tangential velocity 😎😎😎!!!!! (мб 10 мм/с)
                                        acsc.NONE, # EndVelocity
                                        acsc.NONE, # JunctionVelocity
                                        acsc.NONE, # Angle
                                        acsc.NONE, # CurveVelocity
                                        acsc.NONE, # Deviation
                                        radius, # Radius
                                        acsc.NONE, # MaxLength
                                        acsc.NONE, # StarvationMargin
                                        None,      # Segments (имя массива, если нужно > 50 сегм.)
                                        acsc.NONE, # ExtLoopType
                                        acsc.NONE, # MinSegmentLength
                                        acsc.NONE, # MaxAllowedDeviation
                                        acsc.NONE, # OutputIndex
                                        acsc.NONE, # BitNumber
                                        acsc.NONE, # Polarity
                                        acsc.NONE, # MotionDelay
                                        None       # Wait (синхронный вызов планирования)
                                        )
        except Exception as e:
            print(f"Ошибка при запуске движения по окружности (extendedSegmentedMotionV2)")
        
        try:
            '''Добавляем дугу (360 градусов окружнсоть) 😊😊😊😊😊'''
            acsc.segmentArc2V2(self.stand.hc,
                               acsc.AMF_VELOCITY,
                               axesM,
                               center_points,
                               circle_angle_rad,
                               None,           # FinalPoint (для вторичных осей, если есть)
                               vector_velocity,      #? Using the previous velosity we input
                               acsc.NONE,      # EndVelocity 
                               acsc.NONE,      # Time
                               None,           # Values (для user variables)
                               None,           # Variables (для user variables)
                               acsc.NONE,      # Index (для user variables)
                               None,           # Masks (для user variables)
                               acsc.NONE,      # ExtLoopType
                               acsc.NONE,      # MinSegmentLength
                               acsc.NONE,      # MaxAllowedDeviation
                               acsc.NONE,      # LciState
                               None            # Wait (синхронный вызов планирования)
                               )
        except Exception as e:
            print(f"Ошибка при добавлении дуги (acsc.segmentArc2V2)")
        
        try:
            acsc.endSequenceM(self.stand.hc, axesM, None)
            '''The function informs the controller, that no more points 
        or segments will be specified for the current multi-axis motion.
        Эта функция сигнализирует контроллеру: "Все, описание траектории закончено.
        Больше сегментов не будет.'''
        except Exception as e:
            print(f"Ошибка при завершении сегмента (acsc.endSequenceM)")
        
        acsc.waitMotionEnd(self.stand.hc, leader, 30000)
        print('Прибыла в начальную точку')
        

    def start_ffi_motion(self):
        """Проверяет режим движения и запускает соответствующий метод."""
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return
        
        #! МОЖНО СДЕЛАТЬ QDoubleValidator и автоматическую замену запятой на точку
        try:
            distance = float(self.ffi_distance_input.text())
        except ValueError:
            self.show_error("Ошибка: введите число через точку")
            self.ffi_distance_input.setText('0.0')
            distance = 0.0  # или другое значение по умолчанию
        else:
            print(f"Дистанция успешно введена и установлена")

        try:
            mode = (self.ffi_mode_input.text())
            if mode and distance != 0:
                if mode == 'X':
                    ffi_axes = [1,3]
                    leader = ffi_axes[0]
                    for axis in ffi_axes:
                        if not self.axes_data[axis]["state"]:
                            self.axes_data[axis]['axis_obj'].enable()
                            self.axes_data[axis]["state"] = True
                elif mode == 'Y':
                    ffi_axes = [0,2]
                    leader = ffi_axes[0]
                    for axis in ffi_axes:
                        if not self.axes_data[axis]["state"]:
                            self.axes_data[axis]['axis_obj'].enable()
                            self.axes_data[axis]["state"] = True
        except Exception as e:
            self.show_error("Ошибка: Введите капсом 'X' или 'Y'")
        else:
            print(f"Мод успешно выбран")

        try:
            speed = float(self.ffi_speed_input.text())
            for axis in ffi_axes:  # Задаём скорость осям с поля ввода
                    self.axes_data[axis]['axis_obj'].set_speed(speed)
        except ValueError:
            self.show_error(" Ошибка: Что-то со скоростью мб")
        else:
            print(f"Скорость успешно введена и установлена")

        self.ffi_motion_log = {  # Инициализация лога
            'time': [],
            'x_pos': [],
            'y_pos': [],
            'eds': [],
        }

        distances = [-(distance/2), -(distance/2)]
        try:
            acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(ffi_axes), tuple(distances), acsc.SYNCHRONOUS)
            acsc.waitMotionEnd(self.stand.hc, leader, 20000)
        except Exception as e:
            print(f"Ошибка при запуске синхронного движения: {e}")
        else:
            print(f"Функция acsc.toPointM выполнена без ошибок, нить выведена на старт")
        time.sleep(0.2) #! Чтобы контроллер успел увидеть остановку оси???
        try:    
            distances = [distance, distance]
            acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(ffi_axes), tuple(distances), acsc.SYNCHRONOUS)
            #*acsc.toPointM сама добавляет -1 в конец списка осей
        except Exception as e:
            print(f"Ошибка при запуске основного синхронного движения: {e}")
        else:
            print(f"Измерение FFI успешно запущено, идёт измерение...")
        
        # Writing log data
        start_time = time.time()
        poll_interval = 0.2
        pos_log = []
        nano = ktl(resource="GPIB0::7::INSTR", mode='meas')              # Создаём экземпляр класса Keithley2182A
        while True:
            pos = acsc.getFPosition(self.stand.hc, leader)  # Спрашиваем позицию оси-лидера у контроллера
            eds = nano.get_voltage()
            pos_log.append(pos)                                     # Добавляем в список координат (X или Y)
            self.ffi_motion_log['time'].append(time.time() - start_time) # Добавляем в список текущее время с момента начала движения
            self.ffi_motion_log['eds'].append(eds)                       # Добавляем значение эдс от кейтли в список

            motor_state = acsc.getMotorState(self.stand.hc, leader)        # Если ось не движется, то закрываем цикл
            if motor_state['in position']:
                self.show_error("Движение успешно завершено")
                break
            time.sleep(poll_interval)                                    # Пауза между опросами            
        
        if mode == 'X':                                                  # Вспоминаем, в какой плоскости двигались и возвращаем
            self.ffi_motion_log['x_pos'] = pos_log                  # список координат в словарь-ffi_motion_log
            self.ffi_motion_log['y_pos'] = [0] * len(self.ffi_motion_log['time'])
            print(len(self.ffi_motion_log['x_pos']),
                        len(self.ffi_motion_log['time']))
        elif mode == 'Y':
            self.ffi_motion_log['y_pos'] = pos_log
            self.ffi_motion_log['x_pos'] = [0] * len(self.ffi_motion_log['time'])
            print(len(self.ffi_motion_log['y_pos']),
                        len(self.ffi_motion_log['time']))
            

        filename = 'ffi_motion_log.csv'                                  # Сохраняем лог в CSV
        with open(filename, mode='w', newline='') as file:               # Открываем в режиме записи w-write
            writer = csv.writer(file)
            writer.writerow(['time', 'x_pos', 'y_pos', 'eds'])           # Заголовки

            rows = zip(
                self.ffi_motion_log['time'],
                self.ffi_motion_log.get('x_pos', []),
                self.ffi_motion_log.get('y_pos', []),
                self.ffi_motion_log.get('eds', [])
            )
            for row in rows:
                writer.writerow(row)

        print(f"Лог сохранён в файл: {filename}")


        
        fig = calc.firstFieldIntegral(self.ffi_motion_log, mode)
            
        try:
            # 1. Создаем буфер в памяти
            buf = io.BytesIO()
            # 2. Сохраняем фигуру в буфер в формате PNG
            #    dpi можно подобрать для нужного размера/качества на экране (напр. 96)
            fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0) # Перемещаем указатель в начало буфера

            # 3. Загружаем данные из буфера в QPixmap
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(buf.getvalue())
            buf.close() # Закрываем буфер

            # !!! ВАЖНО: Закрываем фигуру Matplotlib после использования, чтобы освободить память !!!
            plt.close(fig)

            # 4. Устанавливаем QPixmap в ваш QLabel
            self.plot_pic.setPixmap(pixmap)
            # (Опционально) Масштабируем изображение под размер QLabel
            self.plot_pic.setScaledContents(True)
            print("График отображен в QLabel.")
        except Exception as e:
            self.show_error(f"Неизвестная ошибка в calc.testFFI или отображении графика: {e}")
            if fig: plt.close(fig) # Закрыть фигуру и при других ошибках

    def check_mode_then_start(self):
        """Проверяет режим движения и запускает соответствующий метод."""
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return
        
        selected_mode = self.check_mode.currentText()
        print(f"Нажата кнопка 'Старт', выбран режим: {selected_mode}")

        if selected_mode == "По окружности":
            self.start_circular_motion()
        elif selected_mode == "Первый магнитный интеграл":
            self.start_ffi_motion()
        elif selected_mode == "Второй магнитный интеграл":  #Todo добавить возврат в ноль мб
            # self.start_homing_motion() ТУТ ДОБАВИТЬ ВТОРОЙ ИНТЕГРАЛ
            pass

    def circle_test(self):
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return

        # Инициализация лога координат
        self.circular_motion_log = {
            'time': [],
            'x_pos': [],
            'y_pos': [],
        }
        self.start_time = time.time()
        vector_velocity = float(self.circ_speed_input_test.text())
        radius = float(self.circ_radius_input_test.text())

        axesM = [0, 1]
        leader = axesM[0]
        
        center_y = self.axes_data[0]["axis_obj"].get_pos()  # Получаем текущую позицию оси 0
        center_x = self.axes_data[1]["axis_obj"].get_pos()  # Получаем текущую позицию оси 1
        circle_angle_rad = 2*np.pi
        center_points = [center_y, center_x]

        start_x = center_x + radius
        start_y = center_y
        start_points = [start_y, start_x]

        self.stand.enable_all()  # Включаем все оси перед движением
        acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, axesM, start_points, acsc.SYNCHRONOUS)
        acsc.waitMotionEnd(self.stand.hc, leader, 15000)
        print('Прибыла в начальную точку')

        #!Радиус самой дуги задается через ее геометрические параметры (центр, угол/конечная точка) в команде segmentArc....
        try:
            acsc.extendedSegmentedMotionV2(self.stand.hc, acsc.AMF_VELOCITY,
                                        axesM, start_points,
                                        vector_velocity, #? Tangential velocity 😎😎😎!!!!! (мб 10 мм/с)
                                        acsc.NONE, # EndVelocity
                                        acsc.NONE, # JunctionVelocity
                                        acsc.NONE, # Angle
                                        acsc.NONE, # CurveVelocity
                                        acsc.NONE, # Deviation
                                        acsc.NONE, # Radius только с флагом ACSC_AMF_CORNERRADIUS
                                        acsc.NONE, # MaxLength
                                        acsc.NONE, # StarvationMargin
                                        acsc.NONE,      # Segments (имя массива, если нужно > 50 сегм.)
                                        acsc.NONE, # ExtLoopType
                                        acsc.NONE, # MinSegmentLength
                                        acsc.NONE, # MaxAllowedDeviation
                                        acsc.NONE, # OutputIndex
                                        acsc.NONE, # BitNumber
                                        acsc.NONE, # Polarity
                                        acsc.NONE, # MotionDelay
                                        None       # Wait (синхронный вызов планирования)
                                        )
        except Exception as e:
            print(f"Ошибка при запуске движения по окружности (extendedSegmentedMotionV2): {e}")
            traceback.print_exc()
        else:
            print(f"Функция acsc.extendedSegmentedMotionV2 выполнена без ошибок")
        
        #!!!⬇️⬇️⬇️⬇️
        '''
        Ты все еще передаешь флаг acsc.AMF_VELOCITY и значение vector_velocity в функцию acsc.segmentArc2V2. 
        Cкорость для сегмента должна наследоваться от той, что задана в extendedSegmentedMotionV2. 
        Нужно передать 0 во флаги и acsc.NONE (-1) в скорость
        '''
        try:
            '''Добавляем дугу (360 градусов окружнсоть) 😊😊😊😊😊'''
            acsc.segmentArc2V2(self.stand.hc,
                               0,
                               axesM,
                               center_points,
                               circle_angle_rad,
                               None,           # FinalPoint (для вторичных осей, если есть)
                               acsc.NONE,      #? Using the previous velosity we input
                               acsc.NONE,      # EndVelocity 
                               acsc.NONE,      # Time
                               None,           # Values (для user variables)
                               None,           # Variables (для user variables)
                               acsc.NONE,      # Index (для user variables)
                               None,           # Masks (для user variables)
                               acsc.NONE,      # ExtLoopType
                               acsc.NONE,      # MinSegmentLength
                               acsc.NONE,      # MaxAllowedDeviation
                               acsc.NONE,      # LciState
                               None            # Wait (синхронный вызов планирования)
                               )
        except Exception as e:
            print(f"Ошибка при добавлении дуги (acsc.segmentArc2V2): {e}")
            traceback.print_exc()
        else:
            print(f"Функция acsc.segmentArc2V2 выполнена без ошибок")
        
        try:
            acsc.endSequenceM(self.stand.hc, axesM, None)
            '''The function informs the controller, that no more points 
        or segments will be specified for the current multi-axis motion.
        Эта функция сигнализирует контроллеру: "Все, описание траектории закончено.
        Больше сегментов не будет.'''
        except Exception as e:
            print(f"Ошибка при завершении сегмента (acsc.endSequenceM)")
            #!ВОЗМОЖНО СТОИТ ПЕРВУЮ ФУНКЦИЮ ЗАПУСТИТЬ ПОСЛЕДНЕЙ!!!!
        else:
            print(f"Функция acsc.endSequenceM выполнена без ошибок")
        
        acsc.waitMotionEnd(self.stand.hc, leader, 30000)
        print('Прибыла в начальную точку')

    def ffi_test(self):
        """Проверяет режим движения и запускает соответствующий метод."""
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return
        
        try:
            distance = float(self.ffi_distance_input_test.text())
        except ValueError:
            self.show_error("Ошибка: введите число через точку")
            self.ffi_distance_input_test.setText('0.0')
            distance = 0.0
        else:
            print(f"Дистанция успешно введена и устанновлена")

        try:
            mode = (self.ffi_mode_input_test.text())
            if mode and distance != 0:
                if mode == 'X':
                    ffi_axes = [0,1]
                    leader = 0
                    for axis in ffi_axes:
                        if not self.axes_data[axis]["state"]:
                            self.axes_data[axis]['axis_obj'].enable()
                            self.axes_data[axis]["state"] = True
                            # self.pos_log = self.ffi_motion_log['x_pos']
                elif mode == 'Y':
                    ffi_axes = [0,1]
                    leader = 0
                    for axis in ffi_axes:
                        if not self.axes_data[axis]["state"]:
                            self.axes_data[axis]['axis_obj'].enable()
                            self.axes_data[axis]["state"] = True
                            # self.pos_log = self.ffi_motion_log['y_pos']
        except Exception as e:
            self.show_error("Введите капсом 'X' или 'Y'")
        else:
            print(f"Мод успешно выбран")

        try:
            speed = float(self.ffi_speed_input_test.text())
            for axis in ffi_axes:
                    self.axes_data[axis]['axis_obj'].set_speed(speed)
        except ValueError:
            self.show_error("Что-то со скоростью мб")
        else:
            print(f"Скорость успешно введена и установлена")

        self.ffi_motion_log = {  # Инициализация лога
            'time': [],
            'x_pos': [],
            'y_pos': [],
            'eds': []
        }

        distances = [-(distance/2), -(distance/2)]
        try:
            acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(ffi_axes), tuple(distances), acsc.SYNCHRONOUS)
            acsc.waitMotionEnd(self.stand.hc, leader, 20000)
        except Exception as e:
            print(f"Ошибка при запуске синхронного движения: {e}")
        else:
            print(f"Функция acsc.toPointM выполнена без ошибок, нить выведена на старт")
        time.sleep(0.2) #! Чтобы контроллер успел увидеть остановку оси???

        # try:
        #     acsc.waitMotionEnd(self.stand.hc, leader, 20000)
        # except Exception as e:
        #     print(f"Ошибка при ожидании окончания первого движения: {e}")
        # else:
        #     print(f"Нить выведена на край")

        try:
            distances = [distance, distance]
            acsc.toPointM(self.stand.hc, acsc.AMF_RELATIVE, tuple(ffi_axes), tuple(distances), acsc.SYNCHRONOUS)
        except Exception as e:
            print(f"Ошибка при запуске основного синхронного движения: {e}")
        else:
            print(f"Измерение FFI успешно запущено, идёт измерение...")

        # Writing log data
        start_time = time.time()
        poll_interval = 0.2
        pos_log = []
        #! Сюда вставить подключение к кейтли и запрос ЭДС
        nano = ktl(resource="GPIB0::7::INSTR", mode='meas')              # Создаём экземпляр класса Keithley2182A
        while True:
            pos = acsc.getFPosition(self.stand.hc, leader)                 # Спрашиваем позицию оси-лидера у контроллера
            eds = nano.get_voltage()                                # Получем ЭДС с keithley
            pos_log.append(pos)                                     # Добавляем в список координат (X или Y)
            self.ffi_motion_log['time'].append(time.time() - start_time) # Добавляем в список текущее время с момента начала движения
            self.ffi_motion_log['eds'].append(eds)

            motor_state = acsc.getMotorState(self.stand.hc, leader)        # Если ось не движется, то закрываем цикл
            if motor_state['in position']:  # Тут изменил на ин позишн, как в апдейт позишн
                self.show_error("Движение успешно завершено")
                break
            time.sleep(poll_interval)                                    # Пауза между опросами            
        
        if mode == 'X':                                                  # Вспоминаем, в какой плоскости двигались и возвращаем
            self.ffi_motion_log['x_pos'] = pos_log                  # список координат в словарь-ffi_motion_log
            self.ffi_motion_log['y_pos'] = [0] * len(self.ffi_motion_log['time'])
            # self.ffi_motion_log['eds'] = [0] * len(self.ffi_motion_log['time'])
            print(len(self.ffi_motion_log['x_pos']),
                        len(self.ffi_motion_log['time']))
        elif mode == 'Y':
            self.ffi_motion_log['y_pos'] = pos_log
            self.ffi_motion_log['x_pos'] = [0] * len(self.ffi_motion_log['time'])
            # self.ffi_motion_log['eds'] = [0] * len(self.ffi_motion_log['time'])
            print(len(self.ffi_motion_log['y_pos']),
                        len(self.ffi_motion_log['time']))


        fig = calc.testFFI(self.ffi_motion_log, mode)

        try:
            # 1. Создаем буфер в памяти
            buf = io.BytesIO()
            # 2. Сохраняем фигуру в буфер в формате PNG
            #    dpi можно подобрать для нужного размера/качества на экране (напр. 96)
            fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0) # Перемещаем указатель в начало буфера

            # 3. Загружаем данные из буфера в QPixmap
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(buf.getvalue())
            buf.close() # Закрываем буфер

            # !!! ВАЖНО: Закрываем фигуру Matplotlib после использования, чтобы освободить память !!!
            plt.close(fig)

            # 4. Устанавливаем QPixmap в ваш QLabel
            self.plot_pic_test.setPixmap(pixmap)
            # (Опционально) Масштабируем изображение под размер QLabel
            self.plot_pic_test.setScaledContents(True)
            print("График отображен в QLabel.")
        except Exception as e:
            self.show_error(f"Неизвестная ошибка в calc.testFFI или отображении графика: {e}")
            if fig: plt.close(fig) # Закрыть фигуру и при других ошибках

    def check_mode_then_start_test(self):
        """Проверяет режим движения и запускает соответствующий метод."""
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return
        
        selected_mode = self.check_mode_test.currentText()
        print(f"Нажата кнопка 'Старт', выбран режим: {selected_mode}")

        if selected_mode == "По окружности":
            self.circle_test()
        elif selected_mode == "Первый магнитный интеграл":
            self.ffi_test()
        elif selected_mode == "Второй магнитный интеграл":  #Todo добавить возврат в ноль мб
            # self.start_homing_motion() ТУТ ДОБАВИТЬ ВТОРОЙ ИНТЕГРАЛ
            pass

    def sfi_test(self, ifFindMagAxis: str=''):
        if not self.stand:
            self.show_error("Контроллер не подключён!")
            return
        
        try:
            distance = float(self.sfi_distance_input_test.text())
        except ValueError:
            self.show_error("Ошибка: введите число через точку")
            self.sfi_distance_input_test.setText('0.0')
            distance = 0.0
        else:
            print(f"Дистанция успешно введена и устанновлена")

        try:
            speed = float(self.sfi_speed_input_test.text())
        except ValueError:
            self.show_error("Ошибка: введите число через точку")
            self.sfi_speed_input_test.setText('0.0')
            speed = 0.0
        else:
            print('Скорость успешно установлена')

        try:
            if ifFindMagAxis not in 'XY': #!Обрати внимание и сделай в других измерениях так же
                mode = (self.sfi_mode_input_test.text())
            else:
                mode = ifFindMagAxis #!!!
            if mode:
                if mode == 'X':
                    sfi_axes = [0,1]
                    leader = 0
                    for axis in sfi_axes:
                        if not self.axes_data[axis]["state"]:
                            self.axes_data[axis]['axis_obj'].enable()
                            self.axes_data[axis]["state"] = True
                elif mode == 'Y':
                    sfi_axes = [0,1]
                    leader = 0
                    for axis in sfi_axes:
                        if not self.axes_data[axis]["state"]:
                            self.axes_data[axis]['axis_obj'].enable()
                            self.axes_data[axis]["state"] = True
        except Exception as e:
            self.show_error("Введите капсом 'X' или 'Y'")
        else:
            print(f"Мод успешно выбран")
        
        self.sfi_motion_log = {  # Инициализация лога
            'time': [],
            'x_pos': [],
            'y_pos': [],
        }
        
        
        

        pass
if __name__ == '__main__':
    app = QApplication([])
    window = ACSControllerGUI()
    window.show()
    app.exec()
    # window.axisstate()
    # print(ACSControllerGUI.__dict__) # Shows all attributes the object have


# TODO Необходимо сделать отдельное окно в GUI, в котором можно будет выбрать режим движения (поступательно, наискосок и по окружности)
# TODO В первой итерации из произвольной точки, выставление оси нужно будет добавить потом