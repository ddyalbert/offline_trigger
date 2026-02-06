import numpy as np
from typing import Optional, Dict, Any
from scipy import signal
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from classes.optimalFilter import OptimalFilter as OF
import time


# Trigger, 除输出数据外，不涉及时间单位，所有参数均为采样点（sample point）
class Trigger:

    sampling: int
    threshold: float # unit: mV
    width_min: float # unit: ms
    height_div_width: float # unit: mV/ms
    
    num_events: int = 0

    v: Optional[np.ndarray] = None # float
    vf: Optional[np.ndarray] = None # float

    pulse_paras: Optional[pd.DataFrame] = None
    peaks: Optional[np.ndarray] = None # int
    peaks_f: Optional[np.ndarray] = None # int

    win_len: int = 0
    pk_posi: int = 0
    bl_end: int = 0

    data_len: int = 0

    baseline: float = 0.0

    of: Optional[OF] = None

    def __init__(self, sampling: int , threshold: float, width_min: float, height_div_width: float):
        self.sampling = sampling
        self.threshold = threshold
        self.width_min = width_min
        self.height_div_width = height_div_width

    def importData(self, v: np.ndarray = None, pulse_paras: Optional[pd.DataFrame] = None):
        self.v = v
        self.vf = None
        self.pulse_paras = pulse_paras

        if pulse_paras is None:
            self.peaks = None # int
            self.peaks_f = None # int
            self.num_events = 0
            self.baseline = 0.0
        else:
            self.peaks = (pulse_paras['pk_time'] * self.sampling).to_numpy().astype(int)
            if 'pk_delay' in pulse_paras.columns:
                self.peaks_f = (pulse_paras['pk_delay'] * self.sampling/1000).to_numpy().astype(int) + self.peaks
            else:
                self.peaks_f = None
            self.pulse_paras['isValid'] = self.pulse_paras['isValid'].astype(bool)
            self.num_events = self.peaks.size
            self.baseline = pulse_paras['Baseline'].mean()
        
        if v is None:
            self.data_len = 0
        else:
            self.data_len = self.v.size

    def set_win_para(self, win_len: int, bl_end: int, pk_posi: int):
        # 注意参数是索引位置，而不是时间位置
        self.win_len = win_len
        self.bl_end = bl_end
        self.pk_posi = pk_posi

    def set_filter(self, of: OF):
        self.of = of

    @property
    def time_array(self):
        return np.arange(self.data_len) / self.sampling
    
    #================================================================================
    # raw data trigger ==============================================================
    #================================================================================
    def find_peaks(self):
        if self.v is None:
            raise ValueError("Data has not been imported")
        threshold = self.threshold / 1000
        width = self.width_min * self.sampling/1000
        self.peaks, properties = signal.find_peaks(self.v, prominence = threshold, width = width , distance = 3, rel_height=0.9)
        self.prominences = properties.get('prominences')
        self.widths = properties.get('widths')
        self.num_events = self.peaks.size
    
    def get_pulse_parameters(self, segment: Optional[int] = None):
        # segment 留给上层类的接口，0 代表v是中间数据段， - 1 代表v是开始数据段， 1 代表v是结束数据段，None 代表v是完整数据段
        if self.peaks is None:
            raise ValueError("Peaks have not been found")
        if self.win_len == 0:
            raise ValueError("Window parameters has not been set")

        pp = PulseParas(self.sampling, 
            {'win_len': self.win_len, 'bl_start': 0, 'bl_end': self.bl_end,'pk_posi': self.pk_posi,'data_len': self.win_len } )

        rows = []
        prev_pk_time = 0
        tf = np.zeros(self.num_events, dtype=bool)

        threshold = self.threshold / 1000
        hDv = self.height_div_width / self.sampling
        nthresh = 3

        for i in range(self.num_events):

            if self.prominences[i] < nthresh * threshold and self.prominences[i] < hDv * self.widths[i]:
                continue

            start_ind = self.peaks[i] - pp.pk_posi
            end_ind = start_ind + pp.data_len

            # 如果是起始段，末尾事件会直接抛掉，而不是记录为 isValid = False
            # 如果是结束段，起始事件会直接抛掉，而不是记录为 isValid = False
            # 如果是中间段，两端的事件都会被抛掉
            pulse_para = {"isValid": False}
            if start_ind < 0:
                if segment == 1 or segment == 0:
                    continue
            elif end_ind > self.data_len:
                if segment == -1 or segment == 0:
                    continue
            else:
                v_pulse = self.v[start_ind : end_ind]
                pp.import_data(v_pulse)
                pp.get_baseline_para()
                pp.get_raw_amplitude_para()
                pp.get_time_para()
        
                pulse_para = pp.export_pulse_paras()
                if self.prominences[i] < nthresh * threshold and pulse_para["Amp_raw"] < threshold:
                    continue
                    
                pulse_para['prominence'] = self.prominences[i] * 1000
                pulse_para['width'] = self.widths[i] * 1000 / self.sampling
                pulse_para['pk_time'] = self.peaks[i] / self.sampling
                pulse_para['pk_interval'] = pulse_para['pk_time'] - prev_pk_time
                prev_pk_time = pulse_para['pk_time']

            tf[i] = True
            rows.append(pulse_para)
            
        self.num_events = np.sum(tf)
        self.pulse_paras = pd.DataFrame(rows)
        self.pulse_paras.fillna(0, inplace=True)

        self.baseline = self.pulse_paras['Baseline'].mean()
        self.peaks = self.peaks[tf]

        self.prominences = None
        self.widths = None

    #================================================================================
    # filter data trigger ===========================================================
    #================================================================================

    def filter_data(self):
        if self.of is None:
            raise ValueError("Filter has not been set")
        self.vf = self.of.filter_data_f(self.v)

    def trigger_with_filter(self):
        if self.vf is None:
            self.filter_data()
        if self.pulse_paras is None:
            raise ValueError("Pulse parameters of raw data have not been computed")
        
        pk_width = self.of.pk_width
        self.peaks_f = np.zeros(self.num_events, dtype=int)

        for i in range(self.num_events):          
            vv = self.vf[self.peaks[i] - pk_width : self.peaks[i] + pk_width]
            ind_max = np.argmax(vv)
            self.peaks_f[i] = self.peaks[i] - pk_width + ind_max


    def get_pulse_parameters_filter(self, segment: Optional[int] = None):
        # segment 留给上层类的接口，0 代表v是中间数据段， - 1 代表v是开始数据段， 1 代表v是结束数据段，None 代表v是完整数据段
        if self.peaks_f is None:
            self.trigger_with_filter()
        
        
        bl_start = self.win_len - self.pk_posi
        pp = PulseParas(self.sampling, 
            {'win_len': self.win_len, 'bl_start': bl_start, 'bl_end': self.bl_end + bl_start, 'pk_posi': self.win_len, 'data_len': 2 * self.win_len,} )
        pp.set_pulse_template(self.of)

        rows = []
        tf = np.zeros(self.num_events, dtype=bool)

        for i in range(self.num_events):
            
            start_ind = self.peaks[i] - pp.pk_posi
            end_ind = start_ind + pp.data_len
            pulse_para = {}
            
            if start_ind < 0:
                if segment == 1 or segment == 0:
                    continue
                self.pulse_paras.loc[i, 'isValid'] = False
            elif end_ind > self.data_len:
                if segment == -1 or segment == 0:
                    continue
                self.pulse_paras.loc[i, 'isValid'] = False
            else: 
                v_pulse  = self.v[start_ind : end_ind]
                vf_pulse = self.vf[start_ind : end_ind]
                pp.import_data(v_pulse, vf_pulse, self.peaks_f[i] - start_ind)
                pp.import_pulse_paras(self.pulse_paras.loc[i])
                pp.get_filtered_amplitude_para()
                pp.get_quality_para()
                pulse_para = pp.export_pulse_paras(type='fil')


            tf[i] = True
            rows.append(pulse_para)
    
        self.num_events = np.sum(tf)
        self.peaks = self.peaks[tf]
        self.peaks_f = self.peaks_f[tf]
        self.pulse_paras = self.pulse_paras[tf]
        self.pulse_paras.index = pd.RangeIndex(self.num_events)
        rows = pd.DataFrame(rows)
        self.pulse_paras = pd.concat([self.pulse_paras, rows], axis=1)

            
    # 绘制触发结果 ----------------------------------------------
    def plot(self,  ax = None, plot_str: str = 'win pk filter info'):
        if self.v is None:
            raise ValueError("Data has not been imported")

        is_upper = True
        if ax is None:
            is_upper = False
            _ , ax = plt.subplots()
        
        tt = self.time_array
        legends = []

        
        if "filter" in plot_str:
            baseline = self.baseline
        else:
            baseline = 0

        legends.append(ax.plot(tt, self.v - baseline, label='raw data')[0])

        if self.of.is_can_filter and "filter" in plot_str:
            if self.vf is None:
                self.filter_data()
            legends.append(ax.plot(tt, self.vf, label='filtered data')[0])

        ax.set_xlabel('Time (s)')
        ax.set_ylabel('V (Volt)')
        ax.grid(True)

        if "pk" in plot_str and self.peaks is not None:
            is_filtered = False
            legends.append(mlines.Line2D([0], [0], marker='x', linestyle='None', color='red', label='raw peak'))
        
            if "filter" in plot_str and self.peaks_f is not None:
                is_filtered = True
                legends.append(mlines.Line2D([0], [0], marker='x', linestyle='None', color='green', label='fil peak'))
            
            is_picker = False
            if "info" in plot_str:
                is_picker = True
            
            self._plot_peaks(ax, baseline, is_picker=is_picker, is_filtered=is_filtered)

        
        if self.pulse_paras is not None and "win" in plot_str:
            self._plot_with_win(ax)
            legends.append(mlines.Line2D([0], [0], color='black', linestyle='--', label='window region'))
            legends.append(mlines.Line2D([0], [0], color='green', linestyle='--', label='baseline region'))

        if legends:
            ax.legend(handles=legends, loc='upper right')

        if not is_upper:
            plt.show()


    def _plot_peaks(self, ax: plt.Axes, baseline = 0, is_picker: bool = False, is_filtered: bool = False):

        if self.pulse_paras is None:
            is_picker = False

        if is_picker and "Amp_raw" in self.pulse_paras.columns:
            for i in range(self.num_events):
                label = ( 
                    f"isValid={self.pulse_paras['isValid'][i]}, "
                    f"height={self.pulse_paras['prominence'][i]:.3g}, "
                    f"width={self.pulse_paras['width'][i]:.3g}, "
                    f"RT={self.pulse_paras['RT'][i]:.3g}, "
                    f"DT={self.pulse_paras['DT'][i]:.3g}"
                    )
                ax.plot(self.peaks[i]/self.sampling, self.v[self.peaks[i]] - baseline, 'x' , color='red', picker=5, label=label)
        else: 
            ax.plot(self.peaks/self.sampling, self.v[self.peaks] - baseline,'x', color='red')

        if not is_filtered:
            return

        if is_picker and "Amp_fil" in self.pulse_paras.columns:
            for i in range(self.num_events):
                label = ( 
                    f"Amp_fil: {self.pulse_paras['Amp_fil'][i]:.2f}, " 
                    f"Chi: {self.pulse_paras['chi2_fil'][i]*1000:.2f}, " 
                    f"Corr: {(1 - self.pulse_paras['corr_fil'][i]) * 1000:.1f}, "
                    f"Delay: {self.pulse_paras['pk_delay'][i]:.2f}"
                    )
                ax.plot(self.peaks_f[i]/self.sampling, self.vf[self.peaks_f[i]], 'x' , color='green', picker=5, label=label)
        else:
            ax.plot(self.peaks_f/self.sampling, self.vf[self.peaks_f],'x', color='green')



    def _plot_with_win(self, ax: plt.Axes):
        pk_posi_time = self.pk_posi / self.sampling
        win_len_time = self.win_len / self.sampling
        bl_end_time = self.bl_end / self.sampling
        
        for i in range(self.num_events):
            if not self.pulse_paras['isValid'][i]:
                continue
            pk = self.pulse_paras['pk_time'][i]
            ax.plot([pk - pk_posi_time, pk - pk_posi_time + win_len_time], [self.pulse_paras['Baseline'][i], self.pulse_paras['Baseline'][i]], '--', color='black')
            ax.plot([pk - pk_posi_time, pk - pk_posi_time + bl_end_time], [self.pulse_paras['Baseline'][i], self.pulse_paras['Baseline'][i]], '--', color='green')


######################################################################################################################


class PulseParas:

    Baseline: Optional[float] = None # [V]
    BL_RMS: Optional[float] = None # [mV]
    BL_slope: Optional[float] = None # [V/s]

    Amp_raw: Optional[float] = None # [V]
    Amp_fil: Optional[float] = None # [V]
    Amp_shift: Optional[float] = None # [V]
    pk_delay: Optional[float] = None # [ms]
    pk_shift: Optional[float] = None # [us]
    
    DT: Optional[float] = None # [ms]
    RT: Optional[float] = None # [ms]

    chi2_raw: Optional[float] = None # [1]
    chi2_fil: Optional[float] = None # [1]
    TVL: Optional[float] = None # [1]
    TVR: Optional[float] = None # [1]
    corr_raw: Optional[float] = None # [1]
    corr_fil: Optional[float] = None # [1]

    ratio_fit: Optional[float] = None # [1]
    lstsq_fit: Optional[float] = None # [1]

    isValid: bool = False


    # -----------------------
    # sampling: int # [Hz]
    # pk_posi: int
    # bl_start: int
    # bl_end: int
    # win_len: int
    # data_len: int

    # -------------------------
    # pk_posi_vf: Optional[int]

    # v: np.ndarray # [V]
    # vf: Optional[np.ndarray] # [V]
    # pulse_norm: Optional[np.ndarray] # [1]

    # template: Optional[np.ndarray] # [V]
    # template_fil: Optional[np.ndarray] # [V]

    def __init__(self, sampling: int, dict_win_para: Dict[str, int]):
        self.sampling : int = sampling
        self.set_win_para(dict_win_para)
    
    def set_win_para(self, dict_win_para: Dict[str, int]):
        self.pk_posi : int = dict_win_para['pk_posi']
        self.bl_end : int = dict_win_para['bl_end']
        self.win_len : int = dict_win_para['win_len']
        self.data_len : int = dict_win_para['data_len']
        self.bl_start : int = dict_win_para['bl_start']
        self.time_array = np.arange(self.data_len) / self.sampling
        self.time_array = self.time_array[self.bl_start:self.bl_end]

    # 导入导出参数 ---------------------------------------------------------------------------------
    def import_data(self, v: Optional[np.ndarray], vf: Optional[np.ndarray] = None, pk_posi_vf: Optional[int] = None):
        self.v: np.ndarray = v
        self.vf: Optional[np.ndarray] = vf
        self.pk_posi_vf: Optional[int] = pk_posi_vf

        for k in self.__dict__.keys():
            if k in PulseParas.__dict__: 
                setattr(self, k, None)
        if v is None:
            self.isValid: bool = False
        else:
            self.isValid: bool = True
        
        self.pulse_norm: Optional[np.ndarray] = None

    def set_pulse_template(self, of: OF):
        # template 长度 wl, 全波形
        # template_fil 长度 >= wlD2 + 1, index = 0 为最大值
        
        self.template: np.ndarray = of.signal_t
        max_arg = np.argmax(of.signal_t_filtered)
        self.template_fil: np.ndarray = of.signal_t_filtered[max_arg:]
        
        wlD2 = self.win_len // 2
        if self.template_fil.size < wlD2 + 1:
            raise ValueError("Filtered template length must be greater than or equal to win_len // 2 + 1")
        self.template_fil_all: np.ndarray = np.append(self.template_fil[wlD2:0:-1], self.template_fil[0:wlD2])

        template_fil_deriv: np.ndarray = of.signal_t_deriv_filtered[max_arg:]
        template_fil_deriv = np.append(- template_fil_deriv[wlD2:0:-1], template_fil_deriv[0:wlD2])
        self.mat = np.column_stack((self.template_fil_all, template_fil_deriv, np.ones(self.win_len)))


    def export_pulse_paras(self, type: str = 'raw'):

        types = []
        if 'raw' in type:
            types.extend(['Baseline', 'BL_RMS', 'BL_slope', 'Amp_raw', 'DT', 'RT', 'isValid', 'pk_shift'])
        if 'fil' in type:
            types.extend(['Amp_fil', 'Amp_shift', 'pk_delay','chi2_raw', 'chi2_fil', 'TVL', 'TVR', 'corr_raw' , 'corr_fil', "ratio_fit", "lstsq_fit"])
 
        dd = {}
        for key in types:
            if key in self.__dict__:
                if self.__dict__[key] is not None:
                    dd[key] = self.__dict__[key]
                else:
                    dd[key] = 0
            else:
                dd[key] = 0

        return dd
    
    def import_pulse_paras(self, ss: pd.Series):
        for k, v in ss.items():
            if k in PulseParas.__dict__:
                setattr(self, k, v)
                
        if self.Amp_raw is not None:
            self.pulse_norm = (self.v[self.bl_start:self.bl_start + self.win_len] - self.Baseline) / self.Amp_raw
        

    # 计算参数(无滤波) ===========================================================================
    def get_baseline_para(self):
        if self.v is None:
            raise ValueError("Raw data have not been imported.")

        y = self.v[self.bl_start:self.bl_end]
        x = self.time_array

        xm = x.mean()
        ym = y.mean()
        dx = x - xm
        dy = y - ym

        # 线性拟合参数（闭式解）
        num = dx @ dy
        den = dx @ dx
        slope = num / den

        # baseline RMS（残差 RMS）
        rss = (dy @ dy) - num * slope
        self.BL_RMS = np.sqrt(rss / (self.bl_end - self.bl_start)) * 1000   # mV

        self.BL_slope = slope * 1000
        self.Baseline = ym

        # pulse 归一化
        self.pulse_norm = ( self.v[self.bl_start:self.bl_start + self.win_len] - self.Baseline)



        
    def get_raw_amplitude_para(self):

        if self.Baseline is None:
            self.get_baseline_para()

        self.Amp_raw = self.v[self.pk_posi] - self.Baseline
        self.pk_shift, _ = PulseParas._get_pulse_shift(self.sampling, self.v[self.pk_posi - 2: self.pk_posi + 3])
        if self.Amp_raw <= 0:
            self.isValid = False
        else:
            self.pulse_norm = self.pulse_norm / self.Amp_raw
    
    @staticmethod
    def _get_pulse_shift(sampling: int, y: np.ndarray):
        max_shift = 1/sampling * 1000000

        if np.max(y) != y[2]:
            return 0, 0
        
        if np.sum(y == y[2]) >= 3:
            return max_shift, 0

        pk_shift = (y[3] - y[1]) / (2*y[2] - y[3] - y[1])/sampling/2 * 1000000
        Amp_shift = (y[3] - y[1])**2 / 8 / (2*y[2] - y[3] - y[1])

        return pk_shift, Amp_shift
          
    def get_time_para(self):

        if self.Amp_raw is None:
            self.get_raw_amplitude_para()
        if not self.isValid:
            return
        
        pk_posi = self.pk_posi - self.bl_start
        
        # ---------------- rise time (0.1 -> 0.9) ----------------
        left = self.pulse_norm[:pk_posi]

        mask10 = left <= 0.1
        mask90 = left <= 0.9
        
        if mask10.any() and mask90.any():
            t10 = np.argmax(mask10[::-1])
            t90 = np.argmax(mask90[::-1])
            self.RT = (t10 - t90) / self.sampling * 1000
        else:
            self.isValid = False

        # ---------------- decay time (0.9 -> 0.3) ----------------
        right = self.pulse_norm[pk_posi:]
        mask90 = right <= 0.9
        mask30 = right <= 0.3
        if mask90.any() and mask30.any():
            t90 = np.argmax(mask90)
            t30 = np.argmax(mask30)
            self.DT = (t30 - t90) / self.sampling * 1000
        else:
            self.isValid = False


    # 计算参数(滤波) ===========================================================================
    def get_filtered_amplitude_para(self):
        if self.vf is None:
            raise ValueError("Filtered data have not been imported.")

        if self.Baseline is None:
            self.get_baseline_para()

        self.Amp_fil = self.vf[self.pk_posi_vf]
        _, self.Amp_shift = PulseParas._get_pulse_shift(self.sampling, self.vf[self.pk_posi_vf - 2: self.pk_posi_vf + 3])

        if self.Amp_fil <= 0:
            self.isValid = False
        self.pk_delay = (self.pk_posi_vf - self.pk_posi) / self.sampling * 1000

 
    def get_quality_para(self):

        if self.template is None:
            raise ValueError("Pulse template has not been set")
        if self.Amp_raw is None:
            self.get_raw_amplitude_para()
        if self.Amp_fil is None:
            self.get_filtered_amplitude_para()
        if not self.isValid:
            return
        
        wlD2 = self.win_len // 2

        self.chi2_raw = np.sqrt(np.sum((self.pulse_norm - self.template)**2) / self.win_len)
        self.corr_raw = np.corrcoef(self.pulse_norm, self.template)[0, 1]

        pulse_normal_fil = self.vf[self.pk_posi_vf - wlD2 : self.pk_posi_vf + wlD2] / self.Amp_fil
        
        self.TVL = np.sqrt( np.sum((pulse_normal_fil[:wlD2] - self.template_fil[wlD2:0:-1])**2) / wlD2 )
        self.TVR = np.sqrt( np.sum((pulse_normal_fil[wlD2:] - self.template_fil[0:wlD2])**2)    / wlD2 )
        
        self.chi2_fil = np.sqrt( (self.TVL**2 + self.TVR**2) / 2 )

        self.corr_fil = np.corrcoef(pulse_normal_fil, self.template_fil_all)[0, 1]

        coef, residual, _, _ = np.linalg.lstsq(self.mat, pulse_normal_fil, rcond=None)
        self.ratio_fit = coef[0]
        self.lstsq_fit = residual[0]
        
