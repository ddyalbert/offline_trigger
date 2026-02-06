import numpy as np
import pandas as pd
from typing import Optional, Dict
import matplotlib.pyplot as plt



from funcs.filters import bessel_filter
from classes.optimalFilter import OptimalFilter as OF

# 生成单脉冲 ============================================================
class SinglePulse:
    t : Optional[np.ndarray] = None
    v : Optional[np.ndarray] = None
    start_posi : int = 0
    pk_posi_to_start : int = 0
    data_len : int = 0
    sampling: int

    tr : float = 0.01
    td : float = 0.1
    proportion : float = 1
    
    def __init__(self, sampling = 5000, tr = 0.01, td = 0.1, proportion = 1):
        # td, proportion 可以是列表，代表多成分脉冲
        self.set_time_constant(tr, td, proportion)
        self.sampling = sampling

    def set_time_constant(self, tr = 0.01, td = 0.1, proportion = 1):
        self.tr = tr
        self.td = td
        self.proportion = proportion

        from collections.abc import Iterable
        if not isinstance(self.proportion, Iterable):
            self.proportion = [self.proportion]
        if not isinstance(self.td, Iterable):
            self.td = [self.td]
    
    @property
    def duration(self):
        return self.data_len / self.sampling
    @property
    def time_array(self):
        return np.arange(self.data_len) / self.sampling

    def generate_pulse(self, duration:float = - 5, is_normalize = True , amp:float = 1, start_time:float = 0):
        
        if duration < 0:
            duration =  - duration * np.max(self.td) + start_time
        if duration != 0:
            self.data_len = int(duration * self.sampling)
            self.start_posi = int(start_time * self.sampling)

        t = self.time_array - start_time
        t[t < 0] = 0

        self.v = - np.exp( - t / self.tr)
        for prop, tt in zip(self.proportion, self.td):
            self.v =  self.v + prop * np.exp(- t / tt)

        max_ind = np.argmax(np.abs(self.v))
        self.pk_posi_to_start = max_ind - self.start_posi
        
        if is_normalize:
            self.v = self.v / self.v[max_ind]
        if amp == 1:
            return self.v
        self.v = self.v * amp
        return self.v

    def bessel_filter(self, cut_freq = 100, order = 8, is_normalize = True):
        self.v = bessel_filter(self.v, self.sampling, fc = cut_freq, order = order, analog=False)
        max_ind = np.argmax(np.abs(self.v))
        self.pk_posi_to_start = max_ind - self.start_posi

        max_amp = 1
        if is_normalize:
            max_amp = self.v[max_ind]
            self.v = self.v / max_amp
        return max_amp
    
    def plot_pulse(self):
        import matplotlib.pyplot as plt
        plt.figure()
        plt.plot(self.time_array, self.v)
        plt.xlabel('Time (s)')
        plt.ylabel('Amplitude')
        plt.title('Single Pulse')
        plt.grid(True)
        plt.show(block=False)


# 生成脉冲信息 =========================================================
class PulseInfo:
    info : pd.DataFrame = None

    duration : float = 0
    num_pulses : int = None
    events_rate : float = None

    def generate_pulse_info(self, duration = 1000, random_time_range = 0, events_rate = 0.1):

        self.events_rate = events_rate
        self.duration = duration

        self.info = pd.DataFrame(columns=['start_time', 'amplitude'])
        num_pulses = int(np.ceil(self.events_rate * self.duration))
        self.num_pulses = num_pulses

        pulse_times = np.linspace(0, self.duration, num_pulses + 2)
        pulse_times = pulse_times[1:-1]
        
        if random_time_range > 0:
            pulse_times = pulse_times + np.random.uniform(-random_time_range, random_time_range, num_pulses)

        self.info['start_time'] = pulse_times
        self.info['amplitude'] = np.ones(num_pulses)

# 生成时间序列 ==========================================================
class MultiplePulse:
    v_orig : np.ndarray = None
    noise : np.ndarray = None

    v_fil : np.ndarray = None

    of : OF = None

    data_len: int = 0
    single_pulse: SinglePulse
    pulse_info: PulseInfo

    is_recreate_pulse : bool = False

    def __init__(self, single_pulse: SinglePulse, pulse_info: Optional[PulseInfo] = None):
        self.single_pulse = single_pulse
        self.pulse_info = pulse_info if pulse_info is not None else PulseInfo()
        self.sampling = self.single_pulse.sampling

    @staticmethod
    def get_instance(sampling = 5000, tr = 0.01, td = 0.1, proportion = 1 , duration = 1000, events_rate = 0.1, random_time_range = 0):
        single_pulse = SinglePulse(sampling, tr, td, proportion)
        single_pulse.generate_pulse(duration = -20, is_normalize = True, amp = 1, start_time = 0)
        pulse_info = PulseInfo()
        pulse_info.generate_pulse_info(duration, random_time_range, events_rate)
        return MultiplePulse(single_pulse, pulse_info)
    
    @property
    def duration(self):
        return self.data_len / self.sampling
    @property
    def time_array(self):
        return np.arange(self.data_len) / self.sampling
    @property
    def v_raw(self):
        if self.v_orig is None:
            return None
        return self.v_orig + self.noise

    # 生成多个脉冲 =======================================================================
    def generate_multiple_pulses(self, is_recreate_pulse : bool = False):
        self.data_len = int(self.pulse_info.duration * self.sampling)
        self.v_orig = np.zeros(self.data_len)
        self.is_recreate_pulse = is_recreate_pulse


        sp_start = self.single_pulse.start_posi
        sp_len = self.single_pulse.data_len - sp_start
        sp_start_time = sp_start / self.sampling
        
        for i in range(self.pulse_info.num_pulses):

            start_idx = int(self.pulse_info.info['start_time'][i] * self.sampling)
            dt = self.pulse_info.info['start_time'][i] - start_idx/self.sampling
            
            if is_recreate_pulse:
                self.single_pulse.generate_pulse(is_normalize = True, start_time = dt + sp_start_time, duration = 0)

            pulse_len = min(sp_len, self.data_len - start_idx)

            self.v_orig[start_idx: start_idx + pulse_len] += self.single_pulse.v[sp_start: sp_start + pulse_len] * self.pulse_info.info['amplitude'][i]

        self.noise = np.zeros(self.data_len)

    # 添加噪声 =======================================================================

    def add_write_noise(self, rms = 0.1):
        noise = np.random.normal(0, rms, self.data_len)
        self.noise += noise

    def bessel_filter(self, cut_freq = 100, order = 8, is_normalize = True):
        self.v_orig = bessel_filter(self.v_orig, self.sampling, fc = cut_freq, order = order, analog=False)
        self.noise = bessel_filter(self.noise, self.sampling, fc = cut_freq, order = order, analog=False)
        max_amp = self.single_pulse.bessel_filter(cut_freq, order, is_normalize)
        self.v_orig = self.v_orig / max_amp

    def add_sin_noise(self, freq = 1000, amp= 0.1):
        noise = amp * np.sin(2 * np.pi * freq * self.time_array + np.random.uniform(0, 2 * np.pi))
        self.noise += noise

    def clear_noise(self):
        self.noise = np.zeros(self.data_len)

    # Optimal Filter =======================================================================
    def optimal_filter(self, win_len:float = 2 , windowType = "hann", is_from_data = False, is_hann_filter = False):
        self.of = OF(int(win_len * self.sampling), self.sampling, windowType)
        self.of.get_noise_psd(self.noise)

        if is_from_data or self.is_recreate_pulse:
            v_raw = self.v_raw
            self.of.clear_signal()
            for i in range(self.pulse_info.num_pulses):
                start_idx = int(self.pulse_info.info['start_time'][i] * self.sampling)  - self.single_pulse.start_posi
                end_idx = start_idx + win_len * self.sampling
                if start_idx < 0:
                    continue
                if end_idx > self.data_len:
                    break
                self.of.add_signal(v_raw[start_idx: end_idx])
                if i == 100:
                    break

            self.of.get_signal_f()
        else:
            self.of.get_signal_f(self.single_pulse.v)

        self.of.get_filter(is_hann = is_hann_filter)

        print("RMS noise[mV]:", self.of.rms_noise * 1000)
        print("RMS noise filtered[mV]:", self.of.rms_noise_filtered * 1000)

        print("Filtering ...")
        self.v_fil = self.of.filter_data_f(self.v_raw)
        print("Filtering done.")
    


    # 绘制脉冲 =======================================================================
    def plot_pulse(self, duration = -1):
        plt.figure()
        if duration == -1:
            plt.plot(self.time_array, self.v_raw, label = 'Original Signal')
            if self.v_fil is not None:
                plt.plot(self.time_array, self.v_fil, label = 'Filtered Signal')
        else:
            end_idx = int(duration * self.sampling)
            plt.plot(self.time_array[:end_idx], self.v_raw[:end_idx], label = 'Original Signal')
            if self.v_fil is not None:
                plt.plot(self.time_array[:end_idx], self.v_fil[:end_idx], label = 'Filtered Signal')


        plt.xlabel('Time (s)')
        plt.ylabel('Amplitude')
        plt.grid(True)
        plt.show(block=False)
        plt.legend()

    def plot_noise_psd(self, win_time = 2):
        from scipy.signal import welch

        ff, psd = welch(self.noise, fs=self.sampling, nperseg=self.sampling * win_time)

        plt.figure()
        plt.plot(ff, psd)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('$V/\sqrt{\mathrm{Hz}}$')
        plt.title('Noise Power Spectral Density')
        plt.xscale('log')
        plt.yscale('log')
        plt.grid(True)
        plt.show(block=False)

from funcs.fit import gauss_fit_hist

class PulseAmplitude:
    # 得到脉冲幅值
    amps: pd.DataFrame = None
    amp_std: Dict[str, float] = None
    # columns: [
    # "pk_orig"  : 生成器对应的脉冲峰位置
    # "pk_raw_to_orig"   : 原始信号对应的最大位置，相对于生成器对应的脉冲峰位置
    # "pk_fil_to_orig"   : 过滤后的信号对应的最大位置，相对于生成器对应的脉冲峰位置
    # "amp_orig" : 生成器对应的脉冲幅值
    # "amp_raw"  : 原始信号对应的脉冲幅值
    # "amp_fil"  : 过滤后的信号对应的脉冲幅值
    # "amp_raw_by_orig"  : 原始信号对应的脉冲幅值，依据生成器对应的脉冲峰位置
    # "amp_fil_by_orig"  : 过滤后的信号对应的脉冲幅值，依据生成器对应的脉冲峰位置
    # "amp_fil_by_raw"   : 过滤后的信号对应的脉冲幅值，依据原始信号对应的脉冲峰位
    # "amp_raw_by_fil"   : 原始信号对应的脉冲幅值，依据过滤后的信号对应的脉冲峰位
    # ]

    def get_pulse_amplitude(self, mp: MultiplePulse, width = 30):
        
        dd = []
        v_raw = mp.v_raw
        v_fil = mp.v_fil

        for i in range(mp.pulse_info.num_pulses):
            pk_orig = int(mp.pulse_info.info['start_time'][i] * mp.sampling) + mp.single_pulse.pk_posi_to_start
            pk_raw = np.argmax(v_raw[pk_orig - width: pk_orig + width]) - width + pk_orig
            pk_fil = np.argmax(v_fil[pk_orig - width: pk_orig + width]) - width + pk_orig

            dd.append({ 
                "pk_orig" : pk_orig,
                "pk_raw_to_orig" : pk_raw - pk_orig,
                "pk_fil_to_orig" : pk_fil - pk_orig,
                "amp_orig" : mp.pulse_info.info['amplitude'][i],
                "amp_raw" :  v_raw[pk_raw],
                "amp_fil" :  v_fil[pk_fil],
                "amp_raw_by_orig" : v_raw[pk_orig],
                "amp_fil_by_orig" : v_fil[pk_orig],
                "amp_fil_by_raw" : v_fil[pk_raw],
                "amp_raw_by_fil" : v_raw[pk_fil],
            })

        self.amps = pd.DataFrame(dd)
        self.amp_std = {
            "amp_orig" : self.amps["amp_orig"].std(),
            "amp_raw" : self.amps["amp_raw"].std(),
            "amp_fil" : self.amps["amp_fil"].std(),
            "amp_raw_by_orig" : self.amps["amp_raw_by_orig"].std(),
            "amp_fil_by_orig" : self.amps["amp_fil_by_orig"].std(),
            "amp_fil_by_raw" : self.amps["amp_fil_by_raw"].std(),
            "amp_raw_by_fil" : self.amps["amp_raw_by_fil"].std(),
        }

    def plot_amp_hist(self, data_name: list[str]):
        plt.figure()
        ax = plt.gca()
        k = 0
        cm = plt.get_cmap('tab10')
        for name in data_name:
            self._hist_gauss(ax, name, color=cm(k))
            k += 1

        plt.grid(True)
        plt.xlabel("Amplitude[V]")
        plt.ylabel("Counts")
        plt.legend()
        plt.show(block=False)

    def _hist_gauss(self, ax: plt.Axes, data_name: str, color=None):
        if self.amps is None:
            raise ValueError("Amplitude data is None. Please get pulse amplitude first.")
        if color is None:
            color = 'r'

        resolu = 1000000
        binwith = np.ceil(self.amp_std[data_name] * resolu / 10) / resolu 

        sigma = gauss_fit_hist(self.amps[data_name], ax, 
                binWidth=binwith, data_std=self.amp_std[data_name], nBins=50, 
                mid = 1, unit='V',
                label=data_name, color=color)

            
