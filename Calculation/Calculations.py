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
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from scipy.fft import fft
    from datetime import datetime
    
    current_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    str_current_time = str(current_time)
    save_path_csv = f"Logs\\CM\\CMlog_{str_current_time}.csv"

    df = pd.DataFrame(log)
    df.index.name = 'Index'
    df.to_csv(save_path_csv, sep=',')
    
    # Угол в полярных координатах
    df["theta"] = np.arctan2(df["y_pos"], df["x_pos"])
    
    # Непрерывный накапливающийся угол
    d_theta = np.diff(-df.theta, prepend=-df.theta[0])
    d_theta[d_theta > np.pi] -= 2 * np.pi
    d_theta[d_theta < -np.pi] += 2 * np.pi
    theta_accum = np.cumsum(d_theta)
    theta_accum -= theta_accum[0]
    df["theta_accum"] = theta_accum

    # --- РАЗДЕЛЕНИЕ НА ОБОРОТЫ ПО НАКОПЛЕННОМУ УГЛУ ---
    revolution_boundaries = [0]  # Начинаем с начала
    
    # Находим точки, где накопленный угол достигает кратных 2π
    for i in range(1, int(theta_accum[-1] // (2*np.pi)) + 1):
        target_angle = i * 2 * np.pi  # Каждый полный оборот = 2π
        idx = np.where(theta_accum >= target_angle)[0]
        if len(idx) > 0:
            revolution_boundaries.append(idx[0])
    
    revolution_boundaries.append(len(df))  # Добавляем конец
    
    print(f"Найдено {len(revolution_boundaries) - 2} полных оборота(ов).")
    print("Индексы границ оборотов:", revolution_boundaries)

    # Интерполяция на равномерную угловую сетку
    interpolated_data = []
    all_amplitudes = []
    n_points_per_rev = 256
    phi_target = np.linspace(0, 2 * np.pi, n_points_per_rev, endpoint=False)

    for j in range(len(revolution_boundaries) - 1):
        start_idx = revolution_boundaries[j]
        end_idx = revolution_boundaries[j+1]
        
        # Пропускаем слишком короткие отрезки
        if end_idx - start_idx < 20:
            continue
        
        signal_j = df["eds"].iloc[start_idx:end_idx].values
        phi_j_abs = df["theta_accum"].iloc[start_idx:end_idx].values
        
        # Нормализуем угол для этого оборота от 0 до 2π
        phi_j_norm = phi_j_abs - phi_j_abs[0]
        
        # Добавляем точку в конце для циклической интерполяции
        phi_j_ext = np.append(phi_j_norm, phi_j_norm[-1] + (phi_j_norm[1]-phi_j_norm[0]))
        signal_j_ext = np.append(signal_j, signal_j[0])
        
        # Интерполяция на равномерную сетку
        f_signal = np.interp(phi_target, phi_j_ext, signal_j_ext)
        interpolated_data.append({'signal': f_signal, 'start': start_idx, 'end': end_idx})

    if not interpolated_data:
        print("Не удалось выделить ни одного полного оборота для анализа.")
        return None, None

    print(f"\nУспешно обработано {len(interpolated_data)} оборотов для анализа.")

    # --- УСРЕДНЕНИЕ И АНАЛИЗ ---
    N = n_points_per_rev
    all_signals_matrix = np.array([d['signal'] for d in interpolated_data])

    if M == 1:
        averaged_signal = np.mean(all_signals_matrix, axis=0)

        # БПФ для усредненного сигнала
        fft_result = fft(averaged_signal)
        amplitudes = 2.0/N * np.abs(fft_result[0:N//2])
        amplitudes[0] = amplitudes[0] / 2.0

        print("\nГармонический анализ усредненного сигнала:")
        for i, amp in enumerate(amplitudes[:10]):
            print(f"Гармоника {i}: амплитуда = {amp:.3e}")

        save_path = f"Logs\\CM\\CMgraph_{str_current_time}.png"
        
        # График для сохранения
        fig_to_save, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(10, 8))

        # Верхний subplot: сигналы + средний
        for i, signal_data in enumerate(all_signals_matrix):
            ax_top.plot(phi_target, signal_data, alpha=0.3)
        ax_top.plot(phi_target, averaged_signal, 'k-', lw=2, label='Усредненный сигнал')
        ax_top.set_title(f'Сигналы с {len(interpolated_data)} оборотов и их среднее')
        ax_top.set_xlabel('Угол (радианы)')
        ax_top.set_ylabel('Сигнал EDS')
        ax_top.grid(True)
        ax_top.legend()

        # Нижний subplot: гармонический анализ
        ax_bottom.stem(range(N//2), amplitudes)
        ax_bottom.set_title('Гармонический анализ (амплитудный спектр)')
        ax_bottom.set_xlabel('Номер гармоники')
        ax_bottom.set_ylabel('Амплитуда')
        ax_bottom.set_xlim(0, 11)
        ax_bottom.grid(True)

        fig_to_save.tight_layout()
        fig_to_save.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"График сохранён как {save_path}")

        # График для GUI - гармонический анализ
        fig1, ax1 = plt.subplots()
        ax1.stem(range(N//2), amplitudes)
        ax1.set_title('Гармонический анализ (амплитудный спектр)')
        ax1.set_xlabel('Номер гармоники')
        ax1.set_ylabel('Амплитуда')
        ax1.set_xlim(0, 11)
        ax1.grid(True)

    elif M == 2:
        # БПФ для каждого оборота отдельно
        for j, data in enumerate(interpolated_data):
            fft_result = fft(data['signal'])
            amplitudes = 2.0/N * np.abs(fft_result[0:N//2])
            amplitudes[0] = amplitudes[0] / 2.0
            all_amplitudes.append(amplitudes)
        
        all_amplitudes_matrix = np.array(all_amplitudes)
        averaged_amplitudes = np.mean(all_amplitudes_matrix, axis=0)
        std_amplitudes = np.std(all_amplitudes_matrix, axis=0)

        print("\nГармонический анализ с усреднением спектров:")
        for i, amp in enumerate(averaged_amplitudes[:10]):
            print(f"Гармоника {i}: амплитуда = {amp:.3e} ± {std_amplitudes[i]:.3e}")

        save_path = f"Logs\\CM\\CMgraph_{str_current_time}.png"
        
        # График для сохранения
        fig_to_save, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(10, 8))

        # Верхний subplot: сигналы
        for i, signal_dict in enumerate(interpolated_data):
            signal_data = signal_dict['signal']
            ax_top.plot(phi_target, signal_data, alpha=0.6)
        ax_top.set_title(f'Сигналы с {len(interpolated_data)} оборотов')
        ax_top.set_xlabel('Угол (радианы)')
        ax_top.set_ylabel('Сигнал EDS')
        ax_top.grid(True)

        # Нижний subplot: гармонический анализ со статистикой
        harmonics = range(N//2)
        ax_bottom.errorbar(harmonics, averaged_amplitudes, yerr=std_amplitudes, 
                          fmt='o-', capsize=5, lw=2)
        ax_bottom.set_title('Гармонический анализ (средний спектр и СКО)')
        ax_bottom.set_xlabel('Номер гармоники')
        ax_bottom.set_ylabel('Амплитуда')
        ax_bottom.set_xlim(0, 11)
        ax_bottom.grid(True)

        fig_to_save.tight_layout()
        fig_to_save.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"График сохранён как {save_path}")

        # График для GUI - гармонический анализ со статистикой
        fig1, ax1 = plt.subplots()
        ax1.errorbar(harmonics, averaged_amplitudes, yerr=std_amplitudes, 
                    fmt='o-', capsize=5, lw=2)
        ax1.set_title('Гармонический анализ (средний спектр и СКО)')
        ax1.set_xlabel('Номер гармоники')
        ax1.set_ylabel('Амплитуда')
        ax1.set_xlim(0, 11)
        ax1.grid(True)

    # Траектория нити с отметками оборотов
    fig2, ax2 = plt.subplots()
    ax2.plot(df["x_pos"], df["y_pos"], 'b-', alpha=0.7)
    
    # Отмечаем границы оборотов
    for idx in revolution_boundaries:
        if idx < len(df):
            ax2.plot(df["x_pos"].iloc[idx], df["y_pos"].iloc[idx], 'ro', markersize=6)
    
    ax2.set_xlabel('X, мм')
    ax2.set_ylabel('Y, мм')
    ax2.set_title(f'Траектория нити ({len(revolution_boundaries)-2} оборотов)')
    ax2.grid(True)
    ax2.axis('equal')

    return fig1, fig2

def first_field_int_with_N(log: dict, mode: str, vel: float):
     
     pass