import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime
import cmath
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

def fft(x):
    N = len(x)
    if N == 1:
        return x
    if N % 2 != 0:
        raise ValueError("Длина массива должна быть степенью двойки")
    
    even = fft(x[0::2])
    odd = fft(x[1::2])
    
    twiddle_factors = [cmath.exp(-2j * cmath.pi * k / N) * odd[k] for k in range(N // 2)]
    
    result = [even[k] + twiddle_factors[k] for k in range(N // 2)] + \
            [even[k] - twiddle_factors[k] for k in range(N // 2)]
    
    return result

def harmonicAnalysis(log: dict, M: int = 1):
    current_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    str_current_time = str(current_time)
    save_path_csv = f"Logs\\CM\\CMlog_{str_current_time}.csv"  # Путь сохранения в папку CM


    df = pd.DataFrame(log)
    df.index.name = 'Index'  # Присваю имя index индексам (создаются автоматически, можно даже отключить)
    df.to_csv(save_path_csv, sep = ',')
    # Используем `arctan2` для получения угла в диапазоне [-π, π]
    df["theta"] = np.arctan2(df["y_pos"], df["x_pos"])
    
    # Расчет непрерывного, монотонно возрастающего угла (unwrapping)
    # Движение по часовой стрелке, поэтому `theta` убывает от π к -π.
    # `-df.theta` делает его возрастающим.
    d_theta = np.diff(-df.theta, prepend=-df.theta[0])
    d_theta[d_theta > np.pi] -= 2 * np.pi
    d_theta[d_theta < -np.pi] += 2 * np.pi  #! Убираем пики при переходе на n-й поворот
    theta_accum = np.cumsum(d_theta) #! СОздаём список с постоянно возрастающим углом(например, если 3 оборотоа до до 6Пи)
    theta_accum -= theta_accum[0] #! Начинается с угла равного 0
    df["theta_accum"] = theta_accum

    # Разделение на обороты по минимуму X координаты
    revolution_boundaries = [0]
    for i in range(1, len(df) - 1):
        if df["x_pos"][i] < df["x_pos"][i-1] and df["x_pos"][i] < df["x_pos"][i+1]:
            revolution_boundaries.append(i)
    revolution_boundaries.append(len(df))

    print(f"Найдено {len(revolution_boundaries) - 1} оборота(ов).")
    print("Индексы границ оборотов:", revolution_boundaries)

    # Интерполяция на равномерную угловую сетку
    interpolated_data = []
    all_amplitudes = []  #! Для усреднения по FFT
    n_points_per_rev = 256  #! Степень двойка для удобного FFT
    phi_target = np.linspace(0, 2 * np.pi, n_points_per_rev, endpoint=False)

    for j in range(len(revolution_boundaries) - 1):
        start_idx = revolution_boundaries[j]
        end_idx = revolution_boundaries[j+1]  #! Определение границ оборотов для дальнейшего анализа каждого оборота по отдельности
        
        if end_idx - start_idx < n_points_per_rev / 4: #????? если осталось меньше четверти оборота, то скип
            continue

        signal_j = df["eds"].iloc[start_idx:end_idx].values
        phi_j_abs = df["theta_accum"].iloc[start_idx:end_idx].values
        
        phi_for_interp = phi_j_abs - phi_j_abs[0]  #! Сдвигаем начало угла к нулю

        # Добавляем точку в конце для корректной циклической интерполяции
        phi_j_ext = np.append(phi_for_interp, phi_for_interp[-1] + (phi_for_interp[1]-phi_for_interp[0]) )
        signal_j_ext = np.append(signal_j, signal_j[0])

        # Интерполяция
        f_signal = np.interp(phi_target, phi_j_ext, signal_j_ext)
        
        interpolated_data.append({'signal': f_signal})

    if not interpolated_data:
        print("Не удалось выделить ни одного полного оборота для анализа.")
        return

    # --- ШАГ 3: УСРЕДНЕНИЕ СИГНАЛОВ ---
    print(f"\nУсреднение {len(interpolated_data)} оборотов...")
    all_signals_matrix = np.array([d['signal'] for d in interpolated_data])

    N = n_points_per_rev

    if M == 1:
        averaged_signal = np.mean(all_signals_matrix, axis=0)

        # --- ШАГ 4: БПФ И ГАРМОНИЧЕСКИЙ АНАЛИЗ ---
        print("Выполнение БПФ для усредненного сигнала...")
        fft_result = fft(averaged_signal.tolist()) 
        
        amplitudes = 2.0/N * np.abs(fft_result[0:N//2])
        amplitudes[0] = amplitudes[0] / 2.0

        # Вывод коэффициентов мультипольного разложения
        for i, amp in enumerate(amplitudes[:10]): # Перебираем первые 10 гармоник
            print(f"Гармоника {i}: амплитуда = {amp:.3e}") # Форматируем с одной цифрой после запятой
        
        save_path = f"Logs\\CM\\CMgraph_{str_current_time}.png"
        
        fig_to_save, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(10, 8))

        # Верхний subplot: сигналы + средний
        for i, signal_data in enumerate(all_signals_matrix):
            ax_top.plot(phi_target, signal_data, alpha=0.3, label=f"{i}-й оборот")
        ax_top.plot(phi_target, averaged_signal, 'k-', lw=2, label='Усредненный сигнал')
        ax_top.set_title('Сигналы со всех оборотов и их среднее')
        ax_top.set_xlabel('Угол (радианы)')
        ax_top.set_ylabel('Сигнал EDS')
        ax_top.grid(True)
        ax_top.legend()

        # Нижний subplot: гармонический анализ (точки)
        ax_bottom.stem(range(N//2), amplitudes)
        ax_bottom.set_title('Гармонический анализ (амплитудный спектр)')
        ax_bottom.set_xlabel('Номер гармоники')
        ax_bottom.set_ylabel('Амплитуда')
        ax_bottom.set_xlim(0, 11)
        ax_bottom.grid(True)

        fig_to_save.tight_layout()

        # Сохранение
        if save_path:
            fig_to_save.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"График сохранён как {save_path}")

        # Для отрисовки в GUI только гармонический анализ
        fig1, ax1 = plt.subplots()
        ax1.stem(range(N//2), amplitudes)
        ax1.set_title('Гармонический анализ (амплитудный спектр)')
        ax1.set_xlabel('Номер гармоники')
        ax1.set_ylabel('Амплитуда')
        ax1.set_xlim(0, 11)
        ax1.grid(True)

    elif M == 2:

        for j in range(len(revolution_boundaries) - 1):
            fft_result = fft(interpolated_data[j]['signal'].tolist())
            amplitudes = 2.0/N * np.abs(fft_result[0:N//2])
            amplitudes[0] = amplitudes[0] / 2.0
            all_amplitudes.append(amplitudes)
        
        all_amplitudes_matrix = np.array(all_amplitudes)
        averaged_amplitudes = np.mean(all_amplitudes_matrix, axis=0)
        std_amplitudes = np.std(all_amplitudes_matrix, axis=0)

        for i, amp in enumerate(amplitudes[:10]): # Перебираем первые 10 гармоник
            print(f"Гармоника {i}: амплитуда = {amp:.3e}") # Форматируем с одной цифрой после запятой
        
        save_path = f"Logs\\CM\\CMgraph_{str_current_time}.png"
        
        fig_to_save, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(10, 8))

        # Верхний subplot: сигналы + средний
        for i, signal_dict in enumerate(interpolated_data):
            signal_data = signal_dict['signal']  # Извлекаем массив значений
            ax_top.plot(phi_target, signal_data, alpha=0.6, label=f'Оборот {i+1}')
        ax_top.set_title('Сигналы со всех оборотов и их среднее')
        ax_top.set_xlabel('Угол (радианы)')
        ax_top.set_ylabel('Сигнал EDS')
        ax_top.grid(True)
        ax_top.legend()

        # Нижний subplot: гармонический анализ (точки)
        harmonics = range(N//2)
        ax_bottom.plot(harmonics, averaged_amplitudes, 'o-', lw=2, label='Средняя амплитуда')
        ax_bottom.fill_between(harmonics, 
                     averaged_amplitudes - std_amplitudes, 
                     averaged_amplitudes + std_amplitudes, 
                     color='skyblue', alpha=0.5, label='Среднеквадратичное отклонение (СКО)')
        ax_bottom.set_title('Гармонический анализ (средний спектр и СКО)')
        ax_bottom.set_xlabel('Номер гармоники')
        ax_bottom.set_ylabel('Амплитуда')
        ax_bottom.set_xlim(0, 11)
        ax_bottom.grid(True)
        ax_bottom.legend()

        fig_to_save.tight_layout()

        # Сохранение
        if save_path:
            fig_to_save.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"График сохранён как {save_path}")

        # Для отрисовки в GUI только гармонический анализ
        fig1, ax1 = plt.subplots()
        ax1.plot(harmonics, averaged_amplitudes, 'o-', lw=2, label='Средняя амплитуда')
        ax1.fill_between(harmonics, 
                     averaged_amplitudes - std_amplitudes, 
                     averaged_amplitudes + std_amplitudes, 
                     color='skyblue', alpha=0.5, label='Среднеквадратичное отклонение (СКО)')
        ax1.set_title('Гармонический анализ (средний спектр и СКО)')
        ax1.set_xlabel('Номер гармоники')
        ax1.set_ylabel('Амплитуда')
        ax1.set_xlim(0, 11)
        ax1.grid(True)
        ax1.legend()

    # Траектория нити
    fig2, ax2 = plt.subplots()
    ax2.plot(df["x_pos"], df["y_pos"])
    ax2.set_xlabel('X, мм')
    ax2.set_ylabel('Y, мм')
    ax2.set_title('Должна быть окружность')
    ax2.grid(which="both", linestyle="--")

    return fig1, fig2

def first_field_int_with_N(log: dict, mode: str, vel: float):
     
     pass