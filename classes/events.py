'''
EventsTree 类：
    为图形界面提供事件树的读写功能
    包括对不同版本的数据处理的管理
'''

from __future__ import annotations
import uproot
import pandas as pd
import numpy as np
from typing import Optional, Dict, Iterator, Callable
import json
import os

from classes.binFile import DataFile
from classes.optimalFilter import OptimalFilter as OF
import matplotlib.pyplot as plt
import classes.appError as appError


class EventsTree:

    file_dir: str
    noise_tree_name: str = ""
    signal_tree_name: str = ""

    sampling: int
    data_file: DataFile

    main_version: int
    template_version: int

    num_signal: int = 0
    num_signal_cut: int = 0

    tree_write_signal: Optional[uproot.WritableTree] = None
    tree_read_signal: Optional[uproot.TBranch] = None
    min_cut_signal: Dict[str, float] = {}
    max_cut_signal: Dict[str, float] = {}
    index_cut_signal: Optional[pd.Index] = None

    num_noise: int = 0
    num_noise_cut: int = 0
    tree_write_noise: Optional[uproot.WritableTree] = None
    tree_read_noise: Optional[uproot.TBranch] = None
    min_cut_noise: Dict[str, float] = {}
    max_cut_noise: Dict[str, float] = {}

    index_cut_noise: Optional[pd.Index] = None

    bl_sigma: BaselineSigma = None

    win_len: float
    pk_posi: float
    bl_end: float

    # 初始化和版本管理 ============================================================================
    def __init__(self, data_file: DataFile, win_para: Dict[str, float], version: list[int]):
        # data_file: 数据文件对象
        # win_para: window参数，包括win_len, pk_posi, bl_end
        # version: 版本号，包括main_version和template_version

        self.data_file = data_file
        self.file_dir = data_file.file_dir
        self.sampling = data_file.sampling
        self.set_win_para(win_para)
        self.set_version(version[0], version[1])
        
    def set_win_para(self, win_para: Dict[str, float]):
        self.win_len = win_para["win_len"]
        self.pk_posi = win_para["pk_posi"]
        self.bl_end = win_para["bl_end"]
    
    def set_version(self, main_version: int, template_version: int):
        # 设置版本号，同时更新对应的signal/noise树文件名和json文件名
        self.main_version = main_version
        self.template_version = template_version

        self.json_file_name = f"TemplateCut_v{self.main_version}.{self.template_version}.json"
        self._set_signal_file_name()

        # 设置NoiseTree文件，同时初始化写入和读取对象
        noise_tree_name = f"Noise_v{self.main_version}.root"
        if self.noise_tree_name == noise_tree_name:
            return
        
        self.noise_tree_name = noise_tree_name
        self.index_cut_noise = None
        self.tree_write_noise = None
        self.tree_read_noise = None
        
    def _set_signal_file_name(self):
        # 设置SignalTree文件，优先使用Filtered后的Tree文件，若不存在则使用原始Tree文件
        # 同时初始化写入和读取对象
        tree_name = f"SignalFiltered_v{self.main_version}.{self.template_version}.root"
        if not os.path.exists(self.file_dir + tree_name):
            tree_name = f"Signal_v{self.main_version}.root"

        if tree_name == self.signal_tree_name:
            return
        
        self.signal_tree_name = tree_name
        self.index_cut_signal = None
        self.tree_write_signal = None
        self.tree_read_signal = None

    def change_dir(self, data_file: DataFile):
        # 改变主目录，同时更新数据文件对象和文件路径
        if self.data_file == data_file:
            return
        self.data_file = data_file
        self.file_dir = data_file.file_dir
        self.sampling = data_file.sampling
        self._set_signal_file_name()

        self.index_cut_signal = None
        self.index_cut_noise = None
        
        self.tree_write_signal = None
        self.tree_read_signal = None
        self.tree_write_noise = None
        self.tree_read_noise = None
    
    # 导入和打开树 ============================================================================
    def delete_tree(self, tree_name: str = "signal_raw"):
        # 删除SignalTree或NoiseTree文件，同时重置对应的写入和读取对象
        # tree_name: "signal_raw" or "signal_fil" or "noise"

        if tree_name == "signal_raw":
            tree_name = f"Signal_v{self.main_version}.root"
        elif tree_name == "signal_fil":
            tree_name = f"SignalFiltered_v{self.main_version}.{self.template_version}.root"
        elif tree_name == "noise":
            tree_name = f"Noise_v{self.main_version}.root"
        else:
            raise ValueError(f"Invalid tree name: {tree_name}")
        
        try:
            os.remove(self.file_dir + tree_name)
        except:
            pass
        
        finally:
            if tree_name.startswith("signal"):
                self.index_cut_signal = None
                self.tree_write_signal = None
                self.tree_read_signal = None
                self.num_signal = 0
            elif tree_name == "noise":
                self.index_cut_noise = None
                self.tree_write_noise = None
                self.tree_read_noise = None
                self.num_noise = 0



    def recreate_tree_siganl(self, is_filtered: bool = False):
        # 重新创建SignalTree，若is_filtered为True，则创建Filtered后的Tree，否则创建原始Tree
        branch_type = {
                "Baseline": "float64",
                "BL_RMS": "float64",
                "BL_slope": "float64",
                "Amp_raw": "float64",
                "pk_time": "float64",
                "pk_interval": "float64",
                "DT": "float64",
                "RT": "float64",
                "isValid": "uint8",
                "prominence": "float64",
                "width": "float64",
                "pk_shift": "float64",
        }
        if is_filtered:
            self.open_tree_signal(is_filtered = False)
            branch_type = branch_type | {
                "Amp_fil": "float64",
                "Amp_shift": "float64",
                "pk_delay": "float64",
                "chi2_raw": "float64",
                "chi2_fil": "float64",
                "TVL": "float64",
                "TVR": "float64",
                "corr_raw": "float64",
                "corr_fil": "float64",
                "ratio_fit": "float64",
                "lstsq_fit": "float64",
            }
            tree_name = f"SignalFiltered_v{self.main_version}.{self.template_version}.root"
        else:
            tree_name = f"Signal_v{self.main_version}.root"

        try:
            root_file = uproot.recreate(self.file_dir + tree_name)
        except:
            raise appError.DataFileNotOpenedError(f"Folder {self.file_dir} is not found.") from None
        self.tree_write_signal = root_file.mktree("tree", branch_type)
        self.num_signal = 0

    def write_tree_signal(self, df: pd.DataFrame):
        # 将DataFrame写入SignalTree, a+模式
        if self.tree_write_signal is None:
            self.recreate_tree_siganl()
        
        self.tree_write_signal.extend(df.to_dict(orient="list"))
        self.num_signal += len(df)

    def open_tree_signal(self, is_filtered: Optional[bool] = None):
        # 打开SignalTree
        #   若is_filtered为True，则打开Filtered后的Tree，否则打开原始Tree
        #   若is_filtered为None，则根据self.signal_tree_name判断是否为Filtered后的Tree

        # self.signal_tree_name对应的文件不存在，则降级为原始Tree, 并打开原始Tree
        # 若原始Tree也不存在，设置self_read_signal为None, num_signal为0, 抛出异常

        if is_filtered is not None:
            if is_filtered:
                self.signal_tree_name = f"SignalFiltered_v{self.main_version}.{self.template_version}.root"
            else:
                self.signal_tree_name = f"Signal_v{self.main_version}.root"

        try:
            self.tree_read_signal: uproot.TBranch = uproot.open(self.file_dir + self.signal_tree_name + ":tree")
            self.num_signal = self.tree_read_signal.num_entries
        except:
            if "SignalFiltered" in self.signal_tree_name:
                self.signal_tree_name = f"Signal_v{self.main_version}.root"
                self.open_tree_signal()
            else:
                self.tree_read_signal = None
                self.num_signal = 0
                raise appError.DataFileNotOpenedError(f"The root file of signal is not found. Please pre-trigger first.") from None

    def open_tree_noise(self):
        # 打开NoiseTree，如果不存在则抛出异常
        try:
            self.tree_read_noise: uproot.TBranch = uproot.open(self.file_dir + self.noise_tree_name + ":tree")
            self.num_noise = self.tree_read_noise.num_entries
        except:
            self.tree_read_noise = None
            self.num_noise = 0
            raise appError.DataFileNotOpenedError(f"The root file of noise is not found. Please find noise first.") from None
          
    def find_tree_noise(self, step: int = 500):
        # NoiseTree 依附于原始数据的SignalTree
        # 
        if self.tree_read_signal is None:
            self.open_tree_signal()

        branch_type = {
            "start_time": "float64",
            "Baseline": "float64",
            "BL_RMS": "float32",
            "BL_slope": "float32",
            "BL_p2p": "float32",
            "noise_len": "float32"
        }
        root_file = uproot.recreate(self.file_dir + self.noise_tree_name)
        self.tree_write_noise = root_file.mktree("tree", branch_type)

        df = EventsDataFrame(self.sampling, self.win_len, self.pk_posi, self.bl_end)
        self.num_noise = 0

        k = 0
        for batch in self._read_tree(["pk_time","pk_interval"], tree_name="signal", step=step):
            df.import_signal(batch)
            df.find_noise_df(self.data_file)
            if df.df_noise is not None:
                self.tree_write_noise.extend({ col: df.df_noise[col] for col in df.df_noise.columns })
                self.num_noise += len(df.df_noise)
            k += 1
            yield k

    # 读取树 =====================================================================================
    def _read_tree(self, branches: Optional[list[str]] = None, tree_name: str = "signal", step: int = 500) -> Iterator[pd.DataFrame]:
        # 循环输出SignalTree或NoiseTree中的数据，步进为step
        tree = None
        if tree_name == "signal":
            if self.tree_read_signal is None:
                self.open_tree_signal()
            tree = self.tree_read_signal   
        if tree_name == "noise":
            if self.tree_read_noise is None:
                self.open_tree_noise()
            tree = self.tree_read_noise
        if tree is None:
            raise ValueError(f"tree_name {tree_name} is not supported.")

        index = 0
        for batch in tree.iterate(branches, step_size=step, library="pd"):
            batch: pd.DataFrame

            len_batch = len(batch)
            batch.index = pd.RangeIndex(index, index + len_batch)
            index += len_batch

            yield batch

    def read_tree_signal_by_time(self, branches: Optional[list[str]] = None, start_time: float = 0, length: float = 1000):
        # 读取SignalTree中指定时间范围内的数据，返回DataFrame
        #   branches: 需要读取的分支列表，默认为None，表示读取所有分支
        #   start_time: 起始时间，默认为0
        #   length: 时间范围，默认为1000秒
        #   返回值: 包含指定时间范围内的数据的DataFrame，索引从0开始，pk_time以start_time为零点
        
        if self.tree_read_signal is None:
            self.open_tree_signal()
        if branches is None:
            branches = self.tree_read_signal.keys()
        
        list_df: list[pd.DataFrame] = []
        for batch in self.tree_read_signal.iterate(branches, step_size=500, library="pd"):
            batch: pd.DataFrame
            if batch.empty:
                continue
            if batch.iloc[-1]["pk_time"] < start_time:
                continue
            if batch.iloc[0]["pk_time"] >= start_time + length:
                break

            list_df.append(batch)

        if len(list_df) == 0:
            res = pd.DataFrame(columns=branches)
        else:
            res = pd.concat(list_df, ignore_index=True)
            list_df = []
        
        res: pd.DataFrame = res[(res["pk_time"] >= start_time) & (res["pk_time"] < start_time + length)]
        res = res.reset_index(drop=True)
        res["pk_time"] -= start_time
        return res


    def get_best_index(self, valueName: str, tree_name: str = "signal", index: Optional[pd.Index] = None, num = 1000):
        # 获取SignalTree或NoiseTree中指定分支的num个最小值的索引，用于自动Cut事件
        #   valueName: 需要比较的分支名称, 可选值为"BL_RMS", "BL_slope", "Amp_raw", "pk_shift", "BL_p2p"
        #   tree_name: 树的名称，默认为"signal"，可以为"signal"或"noise"
        #   index: 要比较的索引，默认为None，表示使用默认索引
        if index is None:
            if tree_name == "signal":
                index = self.index_cut_signal
            elif tree_name == "noise":
                index = self.index_cut_noise
        
        series_list: list[pd.Series] = []
        for batch in self._read_tree([valueName], tree_name=tree_name):
            cut_index = batch.index.intersection(index)
            series_list.append(batch.loc[cut_index, valueName])

        value_series = pd.concat(series_list, ignore_index=False)
        series_list = []

        if valueName == "BL_RMS":
            return value_series.nsmallest(num).index
        if valueName == "BL_slope":
            return value_series.abs().nsmallest(num).index
        if valueName == "Amp_raw":
            return value_series.abs().nsmallest(num).index
        if valueName == "pk_shift":
            return value_series.abs().nsmallest(num).index
        if valueName == "BL_p2p":
            return value_series.nsmallest(num).index
        
        raise ValueError(f"valueName {valueName} is not supported.")
    
    def get_max_min_value(self, branches: Optional[list[str]] = None, tree_name: str = "signal", index: Optional[pd.Index] = None):
        # 获取SignalTree或NoiseTree中指定分支的最大最小值
        #   branches: 需要比较的分支列表，默认为None，表示比较所有分支
        #   tree_name: 树的名称，默认为"signal"，可以为"signal"或"noise"
        #   index: 要比较的索引，默认为None，表示使用默认索引
        #   返回值: 包含最大最小值的字典，键为分支名称，值为最大最小值的DataFrame
        if index is None:
            if tree_name == "signal":
                index = self.index_cut_signal
            elif tree_name == "noise":
                index = self.index_cut_noise
        if branches is None:
            if tree_name == "signal":
                branches = self.min_cut_signal.keys()
            elif tree_name == "noise":
                branches = self.min_cut_noise.keys()

        min_dict = {branch: np.inf for branch in branches}
        max_dict = {branch: -np.inf for branch in branches}

        for batch in self._read_tree(branches, tree_name=tree_name):
            cut_index = batch.index.intersection(index)
            for branch in branches:
                min_dict[branch] = min(min_dict[branch], batch.loc[cut_index, branch].min())
                max_dict[branch] = max(max_dict[branch], batch.loc[cut_index, branch].max())

        return min_dict, max_dict

    # process signal======================================================================================

    def apply_signal_cut(self):
        df = EventsDataFrame(self.sampling, self.win_len, self.pk_posi, self.bl_end)
        self.num_signal_cut = 0
        indices = []
        for batch in self._read_tree(tree_name="signal"):
            df.import_signal(batch)
            df.apply_signal_cut(self.min_cut_signal, self.max_cut_signal)
            if not df.index_cut_signal.empty:
                indices.append(df.index_cut_signal)
            self.num_signal_cut += df.num_signal_cut

        indices:list[pd.Index]
        self.index_cut_signal = pd.Index([]) if not indices else indices[0].append(indices[1:])
        

    def default_signal_cut(self, cut_num: int = 1000, valueName: str = "BL_slope"):

        min_cut = self.min_cut_signal.copy()
        max_cut = self.max_cut_signal.copy()
        min_cut.pop(valueName)
        max_cut.pop(valueName)

        df = EventsDataFrame(self.sampling , self.win_len, self.pk_posi, self.bl_end)
        indices: list[pd.Index] = []
        for batch in self._read_tree(tree_name="signal"):
            df.import_signal(batch)
            df.apply_signal_cut(min_cut, max_cut)
            if not df.index_cut_signal.empty:
                indices.append(df.index_cut_signal)

        index_cut = pd.Index([]) if not indices else indices[0].append(indices[1:])
        indices = []
        self.index_cut_signal = self.get_best_index(valueName, tree_name="signal", index=index_cut, num=cut_num)
        self.num_signal_cut = len(self.index_cut_signal)


    def plot_signal(self, step: int = 500, is_normalize: bool = False, ax: plt.Axes = None):
        if self.index_cut_signal is None:
            raise appError.CutNotAppliedError("Please apply signal cut first!")
        
        is_upper = True
        if ax is None:
            is_upper = False
            _ , ax = plt.subplots()

        ax.set_xlabel("Time [s]")
        if is_normalize:
            ax.set_ylabel("Normalized Amplitude")
        else:
            ax.set_ylabel("Amplitude[V]")
        ax.grid(True)
            
        df = EventsDataFrame(self.sampling, self.win_len, self.pk_posi, self.bl_end)
        k = 0
        for batch in self._read_tree(tree_name="signal", step=step):
            df.import_signal(batch, self.index_cut_signal.intersection(batch.index))
            df.plot_signal(is_normalize=is_normalize, ax=ax , data_file=self.data_file)
            k += 1
            yield k

        if not is_upper:
            plt.show()

    def add_signal(self, of: OF):
        if self.index_cut_signal is None:
            raise appError.CutNotAppliedError("Please apply signal cut first!")
        df = EventsDataFrame(self.sampling, self.win_len, self.pk_posi, self.bl_end)
        for batch in self._read_tree(tree_name="signal", branches=["pk_time", "Baseline"]):
            df.import_signal(batch, self.index_cut_signal.intersection(batch.index))
            df.add_signal(of, self.data_file)

    # process noise ==================================================================
    def apply_noise_cut(self):
        df = EventsDataFrame(self.sampling, self.win_len, self.pk_posi, self.bl_end)
        self.num_noise_cut = 0
        indices = []
        for batch in self._read_tree(tree_name="noise"):
            df.import_noise(batch)
            df.apply_noise_cut(self.min_cut_noise, self.max_cut_noise)
            if not df.index_cut_noise.empty:
                indices.append(df.index_cut_noise)
            self.num_noise_cut += df.num_noise_cut

        indices:list[pd.Index]
        self.index_cut_noise = pd.Index([]) if not indices else indices[0].append(indices[1:])

    def default_noise_cut(self, cut_num: int = 5000, valueName: str = "BL_slope", is_pre_cut: bool = True):
        min_cut = self.min_cut_noise.copy()
        max_cut = self.max_cut_noise.copy()
        min_cut.pop(valueName)
        max_cut.pop(valueName)
        if not is_pre_cut:
            min_cut = {}
            max_cut = {}

        df = EventsDataFrame(self.sampling, self.win_len, self.pk_posi, self.bl_end)
        indices: list[pd.Index] = []
        for batch in self._read_tree(tree_name="noise"):
            df.import_noise(batch)
            df.apply_noise_cut(min_cut, max_cut)
            if not df.index_cut_noise.empty:
                indices.append(df.index_cut_noise)

        index_cut = pd.Index([]) if not indices else indices[0].append(indices[1:])
        indices = []
        self.index_cut_noise = self.get_best_index(valueName, tree_name="noise", index=index_cut, num=cut_num)
        self.num_noise_cut = len(self.index_cut_noise)

    def plot_noise(self, step: int = 500, is_align: bool = False, ax: plt.Axes = None):
        if self.index_cut_noise is None:
            raise appError.CutNotAppliedError("Please apply noise cut first!")

        is_upper = True
        if ax is None:
            is_upper = False
            _ , ax = plt.subplots()

        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Voltage[V]")
        ax.grid(True)
        
        df = EventsDataFrame(self.sampling, self.win_len, self.pk_posi, self.bl_end)
        k = 0
        for batch in self._read_tree(tree_name="noise",step=step):
            df.import_noise(batch, self.index_cut_noise.intersection(batch.index))
            df.plot_noise(is_align=is_align, ax=ax , data_file=self.data_file)
            k += 1
            yield k

        if not is_upper:
            plt.show()

    def create_bl_sigma(self, of: Optional[OF] = None):
        self.bl_sigma = BaselineSigma(of)

    def add_noise(self, writer: OF|BaselineSigma):
        if self.index_cut_noise is None:
            raise appError.CutNotAppliedError("Please apply noise cut first!")
        df = EventsDataFrame(self.sampling, self.win_len, self.pk_posi, self.bl_end)
        for batch in self._read_tree(branches=["start_time", "noise_len"], tree_name="noise"):
            df.import_noise(batch, self.index_cut_noise.intersection(batch.index))
            df.add_noise(writer, self.data_file)

    # save cut ===============================================================================
    def save_cut(self, type: str = "signal noise"):
        try:
            with open(self.file_dir + self.json_file_name, "r") as f:
                save_dict = json.load(f)
        except:
            save_dict = {}
        
        if "signal" in type and self.tree_read_signal is not None:
            save_dict["signal cut"] = {
                "min": self.min_cut_signal,
                "max": self.max_cut_signal,
            }
        
        if "noise" in type and self.tree_read_noise is not None:
            save_dict["noise cut"] = {
                "min": self.min_cut_noise,
                "max": self.max_cut_noise,
            }

        try:
            with open(self.file_dir + self.json_file_name, "w") as f:
                json.dump(save_dict, f, indent=4)
        except:
            raise appError.DataFileNotOpenedError(f"Folder {self.file_dir} is not found.") from None

    def load_cut(self) -> bool:

        try:
            with open(self.file_dir + self.json_file_name, "r") as f:
                save_dict = json.load(f)    
        except:
            return False
    
        if "signal cut" in save_dict:
            self.min_cut_signal = save_dict["signal cut"]["min"]
            self.max_cut_signal = save_dict["signal cut"]["max"]
        if "noise cut" in save_dict:
            self.min_cut_noise = save_dict["noise cut"]["min"]
            self.max_cut_noise = save_dict["noise cut"]["max"]

        return True



#######################################################################################################
# EventsDataFrame -------------------------------------------------------------------------------------
#######################################################################################################
'''
EventsDataFrame类
    用于管理更小的事件数据
    也用于EventsTree类的分块处理接口
'''
class EventsDataFrame:

    v: Optional[np.ndarray] = None
    sampling: int

    win_len: float
    pk_posi: float
    bl_end: float

    df_signal: Optional[pd.DataFrame] = None
    index_cut_signal: Optional[pd.Index] = None
    num_signal_cut: int = 0

    df_noise: Optional[pd.DataFrame] = None
    index_cut_noise: Optional[pd.Index] = None
    num_noise_cut: int = 0


    # 初始化 EventsDataFrame ===============================================================================
    def __init__(self, sampling: int, win_len: float, pk_posi: float, bl_end: float):
        self.sampling = sampling
        self.set_win_para(win_len, pk_posi, bl_end)

    def set_win_para(self, win_len: float, pk_posi: float, bl_end: float):
        self.win_len = win_len
        self.pk_posi = pk_posi
        self.bl_end = bl_end

    # 导入signal/noise/data数据和cut =========================================================================
    def import_signal(self, df: pd.DataFrame, index_cut: pd.Index = None):
        self.df_signal = df
        self.index_cut_signal = index_cut
    
    def import_noise(self, df: pd.DataFrame, index_cut: pd.Index = None):
        self.df_noise = df
        self.index_cut_noise = index_cut

    def import_data(self, v: np.ndarray):
        # 导入data数组，一般用于小规模数据处理
        # 正式的大规模数据处理应使用EventsTree类的分块处理接口，使用上层DataFile类读取数据
        self.v = v

    def _get_noise_data(self, data_file: Optional[DataFile] = None) -> Callable[[float, float], np.ndarray]:
        # 获取读取噪声Data的函数
        if data_file is not None:
            vv = lambda start_time, noise_len: data_file.read_by_time(start_time, noise_len)
        else:
            vv = lambda start_time, noise_len: self.v[
                int(start_time * self.sampling) : int((start_time + noise_len) * self.sampling)]
        return vv
    
    def _get_signal_data(self, data_file: Optional[DataFile] = None) -> Callable[[float], np.ndarray]:
        # 获取读取信号Data的函数    
        if data_file is not None:
            vv = lambda pk_time: data_file.read_by_time(pk_time - self.pk_posi, self.win_len)
        else:
            vv = lambda pk_time: self.v[
                int((pk_time - self.pk_posi) * self.sampling) : int((pk_time - self.pk_posi + self.win_len) * self.sampling)]
        return vv

    # 查找噪声数据 ==================================================================
    def find_noise_df(self, data_file: Optional[DataFile] = None):
        if self.v is None and data_file is None:
            raise ValueError("Data of signal has not been imported.")
        if self.df_signal is None:
            raise ValueError("DataFrame of signal has not been imported.")
        
        read_noise: Callable[[float, float], np.ndarray] = self._get_noise_data(data_file)
        dd = []
        
        for i in self.df_signal.index:
            interval = self.df_signal['pk_interval'][i]
            if interval < 2 * self.win_len:
                # 事件间隔小于2*win_len, 无法找到足够长度的噪声数据，跳过该事件
                continue

            # 计算噪声数据的起始时间和和长度
            interval -= self.win_len
            k = int(interval // (self.win_len / 2))
            noise_len = k * (self.win_len / 2)
            start_time = self.df_signal['pk_time'][i] - self.pk_posi + self.bl_end - noise_len
            
            noise_size = int(noise_len * self.sampling)
            v = read_noise(start_time, noise_len)
            pp = np.polyfit(np.arange(noise_size) / self.sampling, v, 1, full=True)

            dd.append({
                "Baseline": np.mean(v),
                "BL_RMS": np.sqrt(pp[1][0]/noise_size) * 1000,
                "BL_slope": pp[0][0] * 1000,
                "BL_p2p": ( np.max(v) - np.min(v) ) * 1000,
                "start_time": start_time,
                "noise_len": noise_len,
            })

        if dd:
            self.df_noise = pd.DataFrame(dd)
        else:
            self.df_noise = None

    # process signal ==================================================================
    def apply_signal_cut(self, min_cut: Dict[str, float] = {}, max_cut: Dict[str, float] = {}):
        if self.df_signal is None:
            raise ValueError("DataFrame of signal has not been imported.")

        mask = self.df_signal["isValid"] == 1
        for col, vmin in min_cut.items():
            if col in self.df_signal:
                m = self.df_signal[col] >= vmin
                mask &= m

        for col, vmax in max_cut.items():
            if col in self.df_signal:
                m = self.df_signal[col] <= vmax
                mask &= m

        mask &= self.df_signal["pk_shift"].abs() <= 1/self.sampling * 1000000 - 1
        mask &= self.df_signal["pk_interval"] >= self.win_len
        mask &= self.df_signal["pk_interval"].shift(-1).fillna(0) >= self.win_len
        mask.iloc[-1] = False

        self.index_cut_signal = self.df_signal.index[mask]
        self.num_signal_cut = len(self.index_cut_signal)
    

    def plot_signal(self, is_normalize: bool = False, ax: plt.Axes = None , data_file: Optional[DataFile] = None):
        # data_file: 上层类的接口，用于读取信号
        if self.v is None and data_file is None:
            raise ValueError("Data of signal has not been imported.")
        if self.index_cut_signal is None:
            raise ValueError("Index of signal has not been cut.")
        if self.df_signal is None:
            raise ValueError("DataFrame of signal has not been imported.")
        
        if self.index_cut_signal.empty:
            return
        
        read_signal = self._get_signal_data(data_file)

        is_upper = True
        if ax is None:
            is_upper = False
            _ , ax = plt.subplots()
            ax.set_xlabel("Time[s]")
            if is_normalize:
                ax.set_ylabel("Normalized Amplitude")
            else:
                ax.set_ylabel("Amplitude[V]")
            ax.grid(True)

        time = np.arange(self.win_len * self.sampling) / self.sampling
        for i in self.index_cut_signal:
            label = (f"{i}: "
                    f"RMS={self.df_signal['BL_RMS'][i]:.2f}, "
                    f"RT={self.df_signal['RT'][i]:.1f}, "
                    f"DT={self.df_signal['DT'][i]:.1f}, "
                    f"slope={self.df_signal['BL_slope'][i]:.3f}"
                    )
            
            v = read_signal(self.df_signal['pk_time'][i]) - self.df_signal['Baseline'][i]
            if is_normalize:
                v = v / self.df_signal['Amp_raw'][i]
            ax.plot(time, v, picker=4, label=label)

        if not is_upper:
            plt.show()


    def add_signal(self, of: OF, data_file: Optional[DataFile] = None):
        # data_file: 上层类的接口，用于读取信号
        if self.v is None and data_file is None:
            raise ValueError("Data of signal has not been imported.")
        if self.index_cut_signal is None:
            raise ValueError("Index of signal has not been cut.")
        if self.df_signal is None:
            raise ValueError("DataFrame of signal has not been imported.")
        
        read_signal = self._get_signal_data(data_file)
                
        for i in self.index_cut_signal: 
            of.add_signal(read_signal(self.df_signal['pk_time'][i]) - self.df_signal['Baseline'][i])

    # process noise ==================================================================
    def apply_noise_cut(self, min_cut: Dict[str, float] = {}, max_cut: Dict[str, float] = {}):
        if self.df_noise is None:
            raise ValueError("DataFrame of noise has not been imported.")
        
        mask = pd.Series(True, index=self.df_noise.index)
        for col, vmin in min_cut.items():
            if col in self.df_noise:
                m = self.df_noise[col] >= vmin
                mask &= m

        for col, vmax in max_cut.items():
            if col in self.df_noise:
                m = self.df_noise[col] <= vmax
                mask &= m

        self.index_cut_noise = self.df_noise.index[mask]
        self.num_noise_cut = len(self.index_cut_noise)


    def plot_noise(self, is_align: bool = False, ax: plt.Axes = None , data_file: Optional[DataFile] = None):
        if self.v is None and data_file is None:
            raise ValueError("Data of noise has not been imported.")
        if self.index_cut_noise is None:
            raise ValueError("Index of noise has not been cut.")
        if self.df_noise is None:
            raise ValueError("DataFrame of noise has not been imported.")
            
        if self.index_cut_noise.empty:
            return
        
        read_noise = self._get_noise_data(data_file)
            
        is_upper = True
        if ax is None:
            is_upper = False
            _ , ax = plt.subplots()
            ax.set_xlabel("Time[s]")
            ax.set_ylabel("Voltage[V]")
            ax.grid(True)

        for i in self.index_cut_noise:
            noise_len = self.df_noise['noise_len'][i]
            label = (f"{i}: "
                    f"p2p={self.df_noise['BL_p2p'][i]:.2f}, "
                    f"slope={self.df_noise['BL_slope'][i]:.3f}, "
                    f"RMS={self.df_noise['BL_RMS'][i]:.2f}, "
                    f"length={noise_len:.1f}")
            v = read_noise(self.df_noise['start_time'][i], noise_len)
            if is_align:
                v = v - np.mean(v)
            ax.plot(np.arange(noise_len * self.sampling) / self.sampling, v , picker=4, label=label)

        if not is_upper:
            plt.show()

    def add_noise(self, writer: BaselineSigma|OF, data_file: Optional[DataFile] = None):
        if self.v is None and data_file is None:
            raise ValueError("Data of noise has not been imported.")
        if self.index_cut_noise is None:
            raise ValueError("Index of noise has not been cut.")
        if self.df_noise is None:
            raise ValueError("DataFrame of noise has not been imported.")
                    
        read_noise = self._get_noise_data(data_file)
        for i in self.index_cut_noise:
            writer.add_noise(read_noise(self.df_noise['start_time'][i], self.df_noise['noise_len'][i]))
    
# =================================================================================
# BaselineSigma ===================================================================
# =================================================================================

from funcs.fit import gauss_fit_hist

class BaselineSigma:

    sigma_raw: float = 0.0
    sigma_fil: float = 0.0 

    _data_raw_list: list[np.ndarray] = []
    _data_fil_list: list[np.ndarray] = []

    data_raw: np.ndarray = np.array([])
    data_fil: np.ndarray = np.array([])
    of: Optional[OF] = None

    def __init__(self, of: Optional[OF] = None):
        self.of = of

    def reset(self):
        self._data_raw_list = []
        self._data_fil_list = []
        self.data_raw = np.array([])
        self.data_fil = np.array([])

    def add_noise(self, noise: np.ndarray):
        nn = noise - np.mean(noise)
        nn = 1000 * nn
        self._data_raw_list.append(nn)
        if self.of is None or not self.of.is_can_filter:
            return
        
        wl = self.of.win_len
        n_win = noise.size // wl
        for i in range(n_win):
            self._data_fil_list.append(self.of.filter_window_data(nn[i*wl:(i+1)*wl]))
            
    def plot(self, ax: plt.Axes = None):
        
        is_upper = True
        if ax is None:
            is_upper = False
            _, ax = plt.subplots()

        self.data_raw = np.concatenate(self._data_raw_list)
        self._data_raw_list = []
        self.data_fil = np.concatenate(self._data_fil_list)
        self._data_fil_list = []

        self.sigma_fil = 0.0

        self.sigma_raw = BaselineSigma._hist_gauss(ax, self.data_raw, label='Raw Noise', color='b')
        if self.data_fil.size != 0:
            self.sigma_fil = BaselineSigma._hist_gauss(ax, self.data_fil, label='Filtered Noise', color='r')

        ax.set_ylabel("Counts")
        ax.legend(loc='upper right')
        ax.grid(True)
        ax.set_xlabel("Baseline[mV]")

        if not is_upper:
            plt.show(block=False)

        self.reset()

    @staticmethod
    def _hist_gauss(ax: plt.Axes, data:np.ndarray, label='', color=None):

        sigma0 = 1.4826 * np.median(np.abs(data - np.median(data)))
        binwith = np.ceil(sigma0 *100) / 1000

        return gauss_fit_hist(data, ax, 
                binWidth=binwith, data_std=sigma0, nBins=50, mid = 0, unit='mV',
                label=label, color=color)
    

    




    