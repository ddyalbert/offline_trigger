import numpy as np
import scipy.signal as sp_signal
from typing import Optional, Dict, Any
import matplotlib.pyplot as plt
import json

import classes.appError as appError

class OptimalFilter:
    
    # win_len: int
    # sampling: int
    pk_posi: int = 0
    pk_width: int = 0

    windowType = "hann" # boxcar # hamming

    noise_psd:Optional[np.ndarray] = None
    # noise_psd: 噪声功率谱密度
    num_noise: int = 0
    # num_noise: 噪声样本数
    rms_noise: float = 0.0
    # rms_noise: 噪声均方根
    rms_noise_filtered: float = 0.0
    # rms_noise_filtered: 噪声均方根, 过滤后的结果

    is_fit_as_template: bool = False

    signal_t_raw:Optional[np.ndarray] = None
    # signal_t_raw: 信号时间域数据_原始数据
    # signal_t:Optional[np.ndarray] = None
    # signal_t: 使用的数据
    num_signal: int = 0
    # num_signal: 信号样本数

    RT: int = 0
    # RT: 上升时间
    DT: int = 0
    # DT: 下降时间

    def __init__(self, win_len: int, sampling: int, windowType: str = "hann"):
        self.win_len = win_len
        self.sampling = sampling
        self.windowType = windowType

        self.is_can_filter = False
        self.fit: Optional[FitTemplate] = None

        self.signal_f:Optional[np.ndarray] = None
        # signal_f: 信号频率域数据

        self.noise_psd_filtered:Optional[np.ndarray] = None
        # noise_psd_filtered: 噪声功率谱密度, 过滤后的结果
        self.signal_t_filtered:Optional[np.ndarray] = None
        # signal_t_filtered: 信号过滤后的结果

        self.signal_t:Optional[np.ndarray] = None

        self.filter_t:Optional[np.ndarray] = None
        # filter_t: 响应函数时间域数据
        self.filter_f:Optional[np.ndarray] = None
        # filter_f: 响应函数频率域数据
        self.filter_padding:Optional[np.ndarray] = None
        # filter_padding: 响应函数填充数据

    @property
    def freq_array(self):
        freq = np.fft.fftfreq(self.win_len, d=1/self.sampling)
        freq[self.win_len//2] = np.abs(freq[self.win_len//2])
        return freq
    
    @property
    def time_array(self):
        return np.arange(self.win_len) / self.sampling
        
    # get noise psd -----------------------------------------
    def clear_noise(self):
        self.sum_noise_psd = 0
        self.num_noise = 0
    def add_noise(self, noise: np.ndarray):
        _, psd = sp_signal.welch(noise, fs=self.sampling, nperseg=self.win_len, window=self.windowType)
        self.sum_noise_psd += psd
        self.num_noise += noise.size//(self.win_len//2) - 1 
    def get_noise_psd(self, noise: Optional[np.ndarray] = None):
        if noise is None:
            if self.num_noise == 0:
                raise ValueError("Input Noise is None")
            psd = self.sum_noise_psd / self.num_noise
            self.sum_noise_psd = 0
        else:
            _, psd = sp_signal.welch(noise, fs=self.sampling, nperseg=self.win_len, window=self.windowType)
            self.num_noise = noise.size//(self.win_len//2) - 1 
            
        psd[-1] = 2 * psd[-2] - psd[-3]
        psd[0]  = 2 * psd[1]  - psd[2]
        self.noise_psd = np.append(psd[:-1], psd[-1:0:-1]) * 0.5  # 保证积分的能量守恒
        self.rms_noise = np.sqrt(np.sum(self.noise_psd) * (self.sampling/self.win_len))

    # get signal -----------------------------------------------
    def clear_signal(self):
        self.sum_signal_t = 0
        self.num_signal = 0
    def add_signal(self, signal: np.ndarray):
        self.sum_signal_t += signal
        self.num_signal += 1
    def get_signal_f(self, signal: Optional[np.ndarray] = None):
        if signal is None:
            if self.num_signal == 0:
                raise ValueError("Input Signal is None")
            signal = self.sum_signal_t
            self.sum_signal_t = 0
        else:
            self.num_signal = 1

        self.pk_posi : np.int64 = np.argmax(signal)
        self.pk_posi = self.pk_posi.item()
        max_val = signal[self.pk_posi]
        self.signal_t_raw = signal/max_val
        self.signal_t = self.signal_t_raw
        self.is_fit_as_template = False
        self._get_time_para()

        return max_val
    
    def _get_time_para(self):
        ratio = 0.5
        idx_r = np.where(self.signal_t[:self.pk_posi] <= ratio)[0]
        if idx_r.size <= 0:
            raise appError.SignalTemplateNotGoodError

        idx_d = np.where(self.signal_t[self.pk_posi:] <= ratio)[0]
        if idx_d.size <= 0:
            raise appError.SignalTemplateNotGoodError
        
        self.pk_width = int(max(self.pk_posi - idx_r[-1], idx_d[0]))

        # ---------------- rise time (0.1 -> 0.9) ----------------
        left = self.signal_t[:self.pk_posi]

        idx_10 = np.where(left <= 0.1)[0]
        idx_90 = np.where(left <= 0.9)[0]

        if idx_10.size > 0 and idx_90.size > 0:
            t10 = idx_10[-1]
            t90 = idx_90[-1]
            self.RT = int(t90 - t10)
        else:
            raise appError.SignalTemplateNotGoodError


        # ---------------- decay time (0.9 -> 0.3) ----------------
        right = self.signal_t[self.pk_posi:]

        idx_90 = np.where(right <= 0.9)[0]
        idx_30 = np.where(right <= 0.3)[0]

        if idx_90.size > 0 and idx_30.size > 0:
            t90 = idx_90[0]
            t30 = idx_30[0]
            self.DT = int(t30 - t90) 
        else:
            raise appError.SignalTemplateNotGoodError

    # filter ------------------------------------------------
    @staticmethod
    def _get_derivative(x: np.ndarray, sampling: int):
        x_deriv = np.zeros(x.size)
        dt = 1/sampling
        x_deriv[0] = (x[1] - x[0])/dt
        x_deriv[1:-1] = (x[2:] - x[:-2])/(2*dt)
        x_deriv[-1] = (x[-1] - x[-2])/dt
        return x_deriv


    def get_filter(self, is_hann = False):
        if self.noise_psd is None:
            raise appError.OptimalFilterCreatedError("Noise template has not been gotten!")
        if self.signal_t is None:
            raise appError.OptimalFilterCreatedError("Signal template has not been gotten!")
        if self.noise_psd.size != self.signal_t.size:
            raise appError.OptimalFilterCreatedError("Noise template and signal template have different length! Please check!")
        
        # construct filter ----------------------------------------------------
        self.signal_f = np.fft.fft(self.signal_t)
        self.filter_f = np.conj(self.signal_f)/self.noise_psd
        self.filter_f[0] = 0

        # normalize ----------------------------------------------
        if is_hann:
            fil_t = np.real(np.fft.ifft(self.filter_f))
            w = 0.5 * (1 - np.cos(2*np.pi*(np.arange(self.win_len) - np.argmax(fil_t) - self.win_len//2)/(self.win_len - 1)))
            fil_t *= w
            self.filter_f = np.fft.fft(fil_t)
        
        self.signal_t_filtered = np.real(np.fft.ifft(self.filter_f * self.signal_f))

        max_ind = np.argmax(self.signal_t_filtered)
        self.filter_f /= self.signal_t_filtered[max_ind]
        self.filter_t = np.real(np.fft.ifft(self.filter_f))[::-1]
        self.filter_f *= np.exp( - 1j * 2 * np.pi * self.freq_array * (self.pk_posi - max_ind)/self.sampling)

        # filter all ----------------------------------------------
        self.signal_t_filtered = np.real(np.fft.ifft(self.filter_f * self.signal_f))

        self.noise_psd_filtered = self.noise_psd * np.abs(self.filter_f) ** 2
        self.rms_noise_filtered = np.sqrt(np.sum(self.noise_psd_filtered) * (self.sampling/self.win_len))

        fil_t = np.real(np.fft.ifft(self.filter_f))
        filter_2t = np.zeros(2 * self.win_len)
        filter_2t[:self.win_len//2] =fil_t[:self.win_len//2]
        filter_2t[-self.win_len//2:]=fil_t[-self.win_len//2:]

        self.filter_padding = np.fft.fft(filter_2t)
        if self.is_fit_as_template:
            self.signal_t_deriv = self.fit.derivative_from_fit()
        else:
            self.signal_t_deriv = OptimalFilter._get_derivative(self.signal_t, self.sampling)
        self.signal_t_deriv_filtered = OptimalFilter._get_derivative(self.signal_t_filtered, self.sampling)
        
        self.is_can_filter = True


    # fit signal template ----------------------------------------------
    def fit_signal_template(self, num_comp: int, is_filter: bool):
        if self.signal_t_raw is None:
            raise appError.OptimalFilterCreatedError("Signal template has not been gotten!")
        self.fit = FitTemplate(self.sampling)
        self.fit.import_template(self.signal_t_raw)

        pk_posi = self.pk_posi/self.sampling
        riseT = self.RT / self.sampling
        decayT = self.DT / self.sampling

        t0_range = (pk_posi - 3 * riseT, pk_posi - riseT, pk_posi - 1.5 * riseT)
        tr_range = (0.5 * riseT,  5 * riseT, riseT)
        td_range = (0.5 * decayT, 1, decayT)

        self.fit.set_model(num_comp, is_filter, t0_range,  td_range, tr_range)

        self.fit.fitTemp()

    def fit_as_template(self, is_true = True):

        if is_true:
            self.signal_t = self.fit.result.best_fit / self.fit.amplitude
            self.is_fit_as_template = True
        else:
            self.signal_t = self.signal_t_raw
            self.is_fit_as_template = False

    # filter data ----------------------------------------------
    def filter_data_t(self, vt: np.ndarray):
        if self.filter_t is None:
            raise appError.FilterNotConstructedError("Filter has not been constructed! Please construct the filter first!")
        
        y = sp_signal.correlate(vt, self.filter_t, mode="full")
        return y[self.win_len - self.pk_posi -1 : y.size - self.pk_posi]
    
    def filter_data_f(self, vt: np.ndarray):
        if self.filter_padding is None:
            raise appError.FilterNotConstructedError("Filter has not been constructed! Please construct the filter first!")
        
        wl = self.win_len
        y = np.zeros_like(vt)
        for k in range(0,vt.size//wl - 1):
            x = np.fft.fft(vt[k*wl : (k + 2)*wl]) * self.filter_padding
            y[k*wl + wl//2 : (k + 2)*wl - wl//2] = np.real(np.fft.ifft(x))[wl//2 : 3 * wl//2]

        return y
    
    def filter_window_data(self, vt: np.ndarray):
        if vt.size != self.win_len:
            raise ValueError("Input data length must be equal to window length!")
        
        return np.real(np.fft.ifft(self.filter_f * np.fft.fft(vt)))
    
    # plot ----------------------------------------------
    def plot_time_domain(self, ax = None, plot_type: str = "f_ sf_", ):
        is_upper = True
        if ax is None:
            _, ax = plt.subplots()
            is_upper = False
        
        leg = []
        t = self.time_array
        ax.plot(t, self.signal_t)
        leg.append('Signal')
        if self.filter_t is not None and "f_" in plot_type:
            ax.plot(t, self.filter_t/ np.max(self.filter_t))
            leg.append('Filter H(t)')
        if self.signal_t_filtered is not None and "sf_" in plot_type:
            ax.plot(t, self.signal_t_filtered)
            leg.append('Filtered Signal')

        ax.legend(leg)

        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Normalized Amplitude')
        ax.grid(True)

        if not is_upper:
            plt.show(block=False)
        

    def plot_freq_domain(self, ax = None, plot_type: str = "n_ s_ sf_ nf_"):
        
        is_upper = True
        if ax is None:
            _, ax = plt.subplots()
            is_upper = False

        freq = self.freq_array
        
        ind = freq >= 0
        leg = []

        if self.noise_psd is not None and "n_" in plot_type:
            nf = np.sqrt(self.noise_psd[ind])
            ax.plot(freq[ind], nf)
            leg.append('Noise PSD')
        if self.signal_f is not None and "s_" in plot_type:
            ax.plot(freq[ind], np.abs(self.signal_f[ind]))
            leg.append('Signal FFT')
        if self.filter_f is not None and "f_" in plot_type:
            ax.plot(freq[ind], np.abs(self.filter_f[ind]))
            leg.append('Filter H(f)')
        if self.noise_psd is not None and self.filter_f is not None and "nf_" in plot_type:
            ax.plot(freq[ind], nf * np.abs(self.filter_f[ind]))
            leg.append('Filtered Noise PSD')

        ax.legend(leg)
        ax.set_xscale('log')
        ax.set_yscale('log')

        ax.set_xlabel('Frequency (Hz)')
        ax.set_ylabel('PSD (V/Sqrt[Hz])')
        ax.grid(True)
        
        if not is_upper:
            plt.show(block=False)


    # save and load ------------------------------------------------------

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if k in OptimalFilter.__dict__: 
                if v is None:
                    continue
                if isinstance(v, np.ndarray):
                    v = v.tolist()
                d[k] = v
        return d

    def from_dict(self, dic : Dict[str, Any]):
        for k, v in dic.items():
            if isinstance(v, list):
                v = np.array(v)
            setattr(self, k, v)
    
    def save_json(self, file_dir, version:list[int]):
        file_path = f"{file_dir}Filter_v{version[0]}.{version[1]}.json"
        
        try:
            with open(file_path, "r") as f:
                existing_data = json.load(f)
        except:
            existing_data = {}

        current_data = self.to_dict()
        for key, value in current_data.items():
            existing_data[key] = value

        try:
            with open(file_path, "w") as f:
                json.dump(existing_data, f, indent=4, sort_keys=True)
        except:
            raise appError.DataFileNotOpenedError(f"Folder {file_dir} is not found.") from None
        

    def load_json(self, file_dir, version:list[int]) -> bool:

        file_path = f"{file_dir}Filter_v{version[0]}.{version[1]}.json"
        try:
            with open(file_path, "r") as f:
                self.from_dict(json.load(f))
            if not self.is_fit_as_template:
                self.signal_t = self.signal_t_raw
            return True
        except:
            return False
    
    
# -------------------------------------------------------------------
# fit template ------------------------------------------------------
# -------------------------------------------------------------------
import lmfit
import funcs.filters as fil

class FitTemplate:

    v : np.ndarray = None
    data_len : int = 0
    
    num_comp : int = 1
    sampling : int

    amplitude : float = 1 # fit 后的波形幅值

    model : Optional[lmfit.Model] = None
    params : Optional[lmfit.Parameters] = None
    result : Optional[lmfit.model.ModelResult] = None

    def __init__(self, sampling: float):
        self.sampling = sampling

    def import_template(self, v: np.ndarray):
        self.v = v
        self.data_len = v.size

    @property
    def time_array(self):
        return np.arange(self.data_len) / self.sampling
    
    @staticmethod
    def single_component_model(t, A, td, tr, t0, is_filter, sampling):
        t = t - t0
        y = np.zeros_like(t)

        mask = t > 0
        y[mask] = A * ( np.exp(- t[mask] / td)  - np.exp(- t[mask] / tr) )

        if is_filter: 
            y = fil.bessel_filter(y, sampling, fc=100, order=8)
        return y
    
    @staticmethod
    def multi_component_model(t, num_comp, A, tr, t0, is_filter, sampling, **params):
        t = t - t0
        mask = t > 0

        y = np.zeros_like(t)
        sum_p = 1
        for i in range(num_comp - 1):
            sum_p -= params[f"p_{i}"]
            y[mask] += params[f"p_{i}"] * np.exp(- t[mask] / params[f"td_{i}"])

        y[mask] += sum_p * np.exp(- t[mask] / params[f"td_{num_comp-1}"])
        y[mask] -= np.exp(- t[mask] / tr)

        if is_filter: 
            y = fil.bessel_filter(y, sampling, fc=100, order=8)

        return A * y
    
    def set_model(self, num_comp: int, is_filter: bool, t0_range = (0.97, 1.0, 0.98), td_range = (0.001, 1, 0.02), tr_range = (0.001, 0.1, 0.005)):
        self.num_comp = num_comp

        if num_comp == 1:
            self.model = lmfit.Model(FitTemplate.single_component_model, independent_vars=['t','is_filter','sampling'], is_filter=is_filter, sampling=self.sampling)
        else:
            self.model = lmfit.Model(FitTemplate.multi_component_model, independent_vars=['t','num_comp','is_filter','sampling'], num_comp=num_comp, is_filter=is_filter, sampling=self.sampling)

        self.params = lmfit.Parameters()
        self.params.add('A',   value=1.000, min=1, max=1000)
        self.params.add('tr',  value=tr_range[2], min=tr_range[0], max=tr_range[1])
        self.params.add('t0',  value=t0_range[2], min=t0_range[0], max=t0_range[1])

        if num_comp == 1:
            self.params.add('td',  value=td_range[2], min=td_range[0],  max=td_range[1])
            return

        for i in range(self.num_comp - 1):
            self.params.add(f"p_{i}",            value=1/num_comp , min=0,  max=1)
            self.params.add(f"td_{i}",           value=td_range[2], min=td_range[0],  max=td_range[1])
        self.params.add(f"td_{self.num_comp-1}", value=td_range[2], min=td_range[0],  max=td_range[1])
    

    def fitTemp(self):
        if self.data_len == 0:
            raise ValueError("Data length is 0, please import data first.")

        t = self.time_array
        self.result = self.model.fit(self.v, self.params, t = t)
        self.print_fit_summary()

    def print_fit_summary(self):
        if self.result is None:
            raise ValueError("Fit has not been performed yet.")
        
        print("")
        print("Fit Summary ============================")
        print(
            f"redχ²={self.result.redchi:.3e}, "
            f"R²={self.result.rsquared:.5f}, "
        )
        # ---- fitted parameters ----
        print("Parameters:")
        params: lmfit.Parameters = self.result.params
        for name, par in params.items():
            par: lmfit.Parameter
            if par.stderr is not None:
                print(f"  {name:8s} = {par.value:.6g} ± {par.stderr:.2g}")
            else:
                print(f"  {name:8s} = {par.value:.6g}")
        print("========================================")


    def derivative_from_fit(self) -> np.ndarray:
        if self.result is None:
            raise ValueError("No fit result available.")

        t = self.time_array
        p: lmfit.Parameters = self.result.params

        A  = p['A'].value/self.amplitude
        tr = p['tr'].value
        t0 = p['t0'].value

        tau = t - t0
        mask = tau > 0

        dy = np.zeros_like(t)

        if self.num_comp == 1:
            td: lmfit.Parameter = p['td']
            dy[mask] -= A * (1.0 / td.value) * np.exp(-tau[mask] / td.value)
        else:
            sum_p = 1.0
            for i in range(self.num_comp - 1):
                pi  = p[f"p_{i}"].value
                tdi = p[f"td_{i}"].value
                sum_p -= pi
                dy[mask] -= A * (pi / tdi) * np.exp(-tau[mask] / tdi)

            td_last = p[f"td_{self.num_comp - 1}"].value

            dy[mask] -= A * (sum_p / td_last) * np.exp(-tau[mask] / td_last)

        dy[mask] += A * (1.0 / tr) * np.exp(-tau[mask] / tr)

        return dy


    def plotFit(self, ax: Optional[plt.Axes] = None, show_components: bool = True):

        if self.result is None:
            raise ValueError("Fit has not been performed yet.")

        is_upper = True
        if ax is None:
            _, ax = plt.subplots()
            is_upper = False

        t = self.time_array
        params: lmfit.Parameters = self.result.params

        # ---- data & total fit ----
        ax.plot(t, self.v, 'o', markersize=3, label="data", alpha=0.6)
        ax.plot(t, self.result.best_fit, '-', label="total fit", linewidth=2)

        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # ---- components ----
        if show_components:
            amp: lmfit.Parameter = params['A']
            t0: lmfit.Parameter = params['t0']

            tt = t - t0.value
            mask = tt > 0

            if self.num_comp == 1:
                td: lmfit.Parameter = params['td']
                yi = amp.value * np.exp(- tt[mask] / td.value) 
                ax.plot(t[mask], yi, '--', label=f"decay term")
            else:
                plast = 1
                for i in range(self.num_comp - 1):
                    pi: lmfit.Parameter = params[f"p_{i}"]
                    tdi: lmfit.Parameter = params[f"td_{i}"]

                    yi = amp.value * pi.value * np.exp(-tt[mask] / tdi.value)
                    ax.plot(t[mask], yi, '--', label=f"decay {i}")

                    plast -= pi

                td_last: lmfit.Parameter = params[f"td_{self.num_comp-1}"]
                yi = amp.value * plast * np.exp(-tt[mask] / td_last.value)
                ax.plot(t[mask], yi, '--', label=f"decay {self.num_comp-1}")


        ax.set_xlabel("Time (s)")
        ax.legend()

        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.grid(True)


        if not is_upper:
            plt.show()
    