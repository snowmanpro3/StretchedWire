import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.integrate import cumulative_trapezoid # Для интегрирования методом трапеций
from scipy.fft import fft, fftfreq
from scipy.signal import get_window  # Добавляем оконную функцию
import warnings
import chardet

def firstFieldIntegral(log: dict, mode: str, vel: float):
    current_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    str_current_time = str(current_time)
    save_path_csv = f"Logs\\FFI\\FFIlog_{str_current_time}.csv"  # Путь сохранения в папку FFI
    
    df = pd.DataFrame(log)
    if mode == 'X':
          pos = df['x_pos']
    elif mode == 'Y':
          pos = df['y_pos']
    df.index.name = 'Index'  # Присваю имя index индексам (создаются автоматически, можно даже отключить)
    df.to_csv(save_path_csv, sep = ',') 

    pos_previous = pos.to_numpy()[:-1]
    time = np.array(df['time'])[1:]
    current_pos = pos.to_numpy()[1:]
    eds = np.array(df['eds'])[1:]
    ffi = eds / vel
    print(len(current_pos), len(ffi))

    fig, ax = plt.subplots()

    save_path = f"Logs\\FFI\\FFIgraph_{str_current_time}.png"
        
    ax.plot(current_pos, ffi)
    ax.set_xlabel(f"Координата, {mode}")
    ax.set_ylabel(f"Первый магнитный интеграл, Тл/м")
    ax.set_title('Распределение первого магнитного интеграла')
    ax.grid(which="both", linestyle="--")  # Сетка для удобства

    if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"График сохранён как {save_path}")
    
    return fig

def secondFieldIntegral(log: dict, mode : str, vel: float):
    L = 2 # Длина нити
    current_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    str_current_time = str(current_time)
    save_path_csv = f"Logs\\SFI\\SFIlog_{str_current_time}.csv"  # Путь сохранения в папку SFI
    
    df = pd.DataFrame(log)
    if mode == 'X':
          pos_0 = df['x_pos_0']
          pos_1 = df['x_pos_1']
    elif mode == 'Y':
          pos_0 = df['y_pos_0']
          pos_1 = df['y_pos_1']
    df.index.name = 'Index'  # Присваю имя index индексам (создаются автоматически, можно даже отключить)
    df.to_csv(save_path_csv, sep = ',') 

    pos_0_previous = pos_0.to_numpy()[:-1]
    pos_1_previous = pos_1.to_numpy()[:-1]
    time = np.array(df['time'])[1:]
    current_pos_0 = pos_0.to_numpy()[1:]
    current_pos_1 = pos_1.to_numpy()[1:]
    eds = np.array(df['eds'])[1:]
    sfi = eds*L / (2*vel)
    print(len(current_pos_0), len(sfi))

    fig, ax = plt.subplots()

    save_path = f"Logs\\SFI\\SFIgraph_{str_current_time}.png"
        
    ax.plot(current_pos_0, sfi)
    ax.set_xlabel(f"Координата, {mode}")
    ax.set_ylabel(f"Первый магнитный интеграл, Тл/м")
    ax.set_title('Распределение первого магнитного интеграла')
    ax.grid(which="both", linestyle="--")  # Сетка для удобства

    if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"График сохранён как {save_path}")
    
    return fig

def harmonicAnalysis(log: dict):
    L = 2 # Длина нити
    current_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    str_current_time = str(current_time)
    save_path_csv = f"Logs\\CM\\CMlog_{str_current_time}.csv"  # Путь сохранения в папку CM
    
    df = pd.DataFrame(log)
    pos_X = df['x_pos']
    pos_Y = df['y_pos']
    df.index.name = 'Index'  # Присваю имя index индексам (создаются автоматически, можно даже отключить)
    df.to_csv(save_path_csv, sep = ',')

    pos_X_previous = pos_X.to_numpy()[:-1]
    pos_Y_previous = pos_Y.to_numpy()[:-1]
    time = np.array(df['time'])[1:]
    pos_X_current = pos_X.to_numpy()[1:]
    pos_Y_current = pos_Y.to_numpy()[1:]
    eds = np.array(df['eds'])[1:]

    # Убираем DC-компоненту (вычитаем среднее значение)
    eds -= np.mean(eds)

    # Применяем оконную функцию Ханна
    window = get_window("hann", len(eds))  # Создаем окно Ханна
    eds *= window  # Применяем окно к сигналу

    # Выполняем преобразование Фурье
    N = len(time)  # Количество точек во временном ряду
    fft_values = fft(eds)  # Преобразование Фурье для ЭДС
    freqs = np.fft.fftfreq(N, d=(time[1] - time[0])) * 2 * np.pi  # Преобразуем в круговую частоту

    # Вычисление амплитуд гармоник
    amplitudes = 2.0 / N * np.abs(fft_values[:N // 2])  # Вычисление модуля спектра

    # Отбрасываем слишком малые амплитуды (шум)
    threshold = 1e-10  # Порог отсечения
    amplitudes[amplitudes < threshold] = np.nan  # Меняем малые значения на NaN, чтобы они не отображались

    # Вывод коэффициентов мультипольного разложения
    for i, amp in enumerate(amplitudes[:10]):  # Перебираем первые 10 гармоник
        print(f"Гармоника {i}: амплитуда = {amp:.3e}")  # Форматируем с одной цифрой после запятой

    fig1, ax = plt.subplots()

    save_path = f"Logs\\CM\\CMgraph_{str_current_time}.png"
    
    # Строим график зависимости первого магнитного поля от координаты нити (X1, например)
    ax.plot(freqs[:N // 2], amplitudes)
    ax.set_xlabel('Круговая частота (рад/с)')
    ax.set_ylabel('Амплитуда')
    ax.set_title('Мультипольное разложение ЭДС (логарифмическая шкала)')
    ax.grid(which="both", linestyle="--")  # Сетка для удобства

    if save_path:
            fig1.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"График сохранён как {save_path}")
    
    
    fig2, ax2 = plt.subplots()
    ax2.plot(pos_X, pos_Y)
    ax2.set_xlabel('X, мм')
    ax2.set_ylabel('Y, мм')
    ax2.set_title('Должна быть окружность')
    ax2.grid(which="both", linestyle="--")  # Сетка для удобства


    return fig1, fig2