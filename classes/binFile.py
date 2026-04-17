'''
binFile 类：
    为图形化界面提供与数据文件BIN2的交互接口
    包括文件读取、写入、头信息改变、文件转换等功能
    内部存储文件路径、数据的参数, 如采样率、ADC位数、满量程电压范围等
    存在一个reader对象, 用于读取文件数据
    
'''

import numpy as np
import os
from typing import Optional, BinaryIO
import struct
import math

import funcs.fileIO as fileIO
import classes.appError as appError

# ------------------------------------------------------------
# BIN2 二进制数据文件格式定义
# ------------------------------------------------------------

MAGIC_BYTES = 8
HEADER_FMT = "<HfBd5s"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

# MAGIC_BYTES = 8
# 文件起始的 magic 字节数（固定长度）
# 内容全部为 0x00
#
# 作用：
#   1) 用于区分“原始 uint32 数据文件”和“BIN2 编码后的 ADC 文件”
#   2) reader 读取文件时，通过判断前 MAGIC_BYTES 个字节是否全为 0x00，
#      来决定是否需要解析后续的文件头（header）
#
# 读取规则：
#   - 若前 MAGIC_BYTES 字节全为 0x00，则认为这是 BIN2 编码文件: self.is_encoded = True
#   - 否则，认为是未编码的原始 uint32 文件: self.is_encoded = False

# HEADER_FMT = "<HfBd5s"
# BIN2 文件头（header）的二进制结构定义（struct 格式字符串）
#
# '<'   : 小端字节序（little-endian）
#
# 'H'   : uint16，占 2 字节
#         ADC_bit
#         ADC 的有效位数（例如 16 / 18 / 24）
#
# 'f'   : float32，占 4 字节
#         Vrange
#         ADC 的满量程电压范围，表示 ±Vrange
#
# 'B'   : uint8，占 1 字节
#         n_bytes
#         每个采样点实际占用的字节数
#         通常为 ceil(ADC_bit / 8)
#
# 'd'   : float64，占 8 字节
#         sampling
#         采样率（单位：Hz）
#
# '5s'  : 5 字节保留字段
#         目前填 0，用于将来扩展或保证结构对齐
#
# header 总长度 = 2 + 4 + 1 + 8 + 5 = 20 字节


class DataFile:

    file_name: str = "" # "cc"
    file_dir: str = ""  # "aa/bb/"
    file_path: str = "" # "aa/bb/cc.ext"

    sampling : int
    ADC_bit: int
    ADC2V: float # V: [-V_range, V_range]
    n_bytes: int = 4
    Vrange: float # V: [-V_range, V_range]

    # reader: Optional[BinaryIO] = None
    total_length: int = 0
    total_duration: float = 0 # hour

    # header info ----------------------------------------------
    is_encoded: bool = False
    data_offset: int = 0

    def __init__(self, sampling: int = 5000, ADC_bit: int = 24, Vrange: float = 10.0):

        self.sampling = sampling
        self.reader: Optional[BinaryIO] = None
        self.set_ADC_para(ADC_bit, Vrange)

    def open(self, file_path: Optional[str] = None, parent_window = None):

        if file_path is None:
            file_path = fileIO.get_file(parent_window=parent_window, filter="(*.BIN2);;(*.BIN)")
            if file_path == "":
                raise appError.DataFileNotOpenedError(f"No data file has been chosen!") from None

        try:
            reader = open(file_path, "rb")
        except:
            raise appError.DataFileNotOpenedError(f"No such file: {file_path}") from None

        self.close()
        self.reader = reader
        self.file_path = file_path
        self.file_dir, self.file_name, _ = fileIO.extract_file_info(file_path)

        self._detect_format()

        filesize = os.path.getsize(file_path)
        self.total_length = (filesize - self.data_offset) // self.n_bytes
        self.total_duration = self.total_length / self.sampling / 3600.0 # hour

        self.reset_reader()    


    def _detect_format(self):
        # 识别文件开头的信息编码格式
        self.reader.seek(0)
        magic = self.reader.read(MAGIC_BYTES)

        if magic == b"\x00" * MAGIC_BYTES:
            # ---- BIN2 file ----
            self.is_encoded = True

            header = self.reader.read(HEADER_SIZE)
            ADC_bit, Vrange, n_bytes, sampling, _ = struct.unpack(
                HEADER_FMT, header
            )

            self.ADC_bit = ADC_bit
            self.Vrange = Vrange
            self.sampling = int(sampling)
            self.n_bytes = n_bytes
            self.ADC2V = (2 * Vrange) / (2 ** ADC_bit)

            self.data_offset = MAGIC_BYTES + HEADER_SIZE
        else:
            # ---- raw uint32 ----
            self.is_encoded = False
            self.n_bytes = 4
            self.data_offset = 0
            self.reader.seek(0)


    def set_sampling(self, sampling: int):
        if self.is_encoded:
            return
        self.sampling = sampling
        self.total_duration = self.total_length / self.sampling / 3600.0 # hour
        
    def set_ADC_para(self, ADC_bit: int, Vrange: float):
        if self.is_encoded:
            return
        self.ADC_bit = ADC_bit
        self.Vrange = Vrange
        self.ADC2V = (2 * Vrange) / (2**ADC_bit)


    # read helper --------------------------------------------------
    def reset_reader(self, index: int = 0):
        # 重置读取指针到指定索引位置，默认文件开头
        if self.reader is None:
            raise appError.DataFileNotOpenedError("The data file has not been opened")
        self.reader.seek(self.data_offset + index * self.n_bytes, 0)

    def _read_raw_ADC(self, length: int) -> np.ndarray:
        # 读取长度为length的ADC数据序列，返回uint32数组
        if self.n_bytes == 4:
            return np.fromfile(self.reader, dtype=np.uint32, count=length)
        
        if self.n_bytes == 2:
            return np.fromfile(self.reader, dtype=np.uint16, count=length)

        if self.n_bytes == 1:
            return np.fromfile(self.reader, dtype=np.uint8, count=length)
        
        if self.n_bytes != 3:
            raise ValueError(f"{self.n_bytes} bytes ADC data is not supported!")

        raw = self.reader.read(length * 3)
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)

        adc = np.zeros(len(b), dtype=np.uint32)
        for i in range(3):
            adc |= b[:, i].astype(np.uint32) << (8 * i)

        return adc

    # read data methods -----------------------------------------

    def read_next_by_index(self, length: int) -> np.ndarray:
        # 读取长度为length(单位：采样点)的ADC数据序列，返回V数组
        adc = self._read_raw_ADC(length)
        return adc * self.ADC2V - self.Vrange

    def read_next_by_time(self, duration: float) -> np.ndarray:
        # 读取长度为duration(单位：秒)的ADC数据序列，返回V数组
        length = int(duration * self.sampling)
        return self.read_next_by_index(length)
    
    def read_by_index(self, start: int, length: int) -> np.ndarray:
        # 读取从start开始的length(单位：采样点)的ADC数据序列，返回V数组
        if start < 0:
            start = 0
        self.reset_reader(start)
        return self.read_next_by_index(length)

    def read_by_time(self, start_time: float, duration: float) -> np.ndarray:
        # 读取从start_time开始的duration(单位：秒)的ADC数据序列，返回V数组
        start = int(start_time * self.sampling)
        length = int(duration * self.sampling)
        return self.read_by_index(start, length)

    def close(self):
        # 关闭文件读取器
        if self.reader is not None:
            self.reader.close()
            self.reader = None

    # create a bin file -------------------------------------------------------------------------------
    def copy_file_with_header(self, out_file: Optional[str] = None, step: int = 1E6,
            sampling: Optional[int] = None, ADC_bit: Optional[int] = None, Vrange: Optional[float] = None):
        # 复制BIN文件并添加头信息

        if self.reader is None:
            raise appError.DataFileNotOpenedError("The data file has not been opened")
        if out_file is None:
            out_file = self.file_dir + self.file_name + "_copy.BIN2"
        
        
        sampling = self.sampling if sampling is None else sampling
        ADC_bit = self.ADC_bit if ADC_bit is None else ADC_bit
        Vrange = self.Vrange if Vrange is None else Vrange
        n_bytes = int(math.ceil(ADC_bit / 8))
        if n_bytes > 4:
            raise ValueError(f"{n_bytes} bytes ADC data is not supported!")

        header = struct.pack(HEADER_FMT, ADC_bit, Vrange, n_bytes, float(sampling), b"\x00" * 5 )

        num_chunk = int(math.ceil(self.total_length / step))

        with open(out_file, "wb") as fout:
            fout.write(b"\x00" * MAGIC_BYTES)
            fout.write(header)

            self.reset_reader()

            for k in range(num_chunk):
                v = self.read_next_by_index(step)
                v = np.round((v + Vrange) / (2 * Vrange) * (1 << ADC_bit)).astype(np.uint32)
                v = np.clip(v, 0, (1 << 8 * n_bytes) - 1)

                if n_bytes == 3:
                    buf = np.empty(v.size * 3, dtype=np.uint8)
                    buf[0::3] = (v & 0xFF)
                    buf[1::3] = (v >> 8) & 0xFF
                    buf[2::3] = (v >> 16) & 0xFF
                    buf.tofile(fout)
                else:
                    dtype_map = {1: np.uint8, 2: np.uint16, 4: np.uint32}
                    v.astype(dtype_map[n_bytes]).tofile(fout)

                yield k

    @staticmethod
    def convert_TDMS(tdms_file: str, sampling: int, ADC_bit: int, Vrange: float, 
            out_file: Optional[str] = None, step: int = 1E6):
        
        # 转换TDMS文件为BIN文件, 并添加头信息
        from nptdms import TdmsFile, TdmsGroup, TdmsChannel

        n_bytes = int(math.ceil(ADC_bit / 8))
        if n_bytes > 4:
            raise ValueError(f"{n_bytes} bytes ADC data is not supported!")
        

        tdms_reader = TdmsFile.open(tdms_file)
        group: TdmsGroup = tdms_reader.groups()[1]
        channel: TdmsChannel = group.channels()[0]
        
        header = struct.pack(HEADER_FMT, ADC_bit, Vrange, n_bytes, float(sampling), b"\x00" * 5 )
        data_length = len(channel)
        num_chunk = int(math.ceil(data_length / step))

        file_dir, file_name, _ = fileIO.extract_file_info(tdms_file)
        out_file = file_dir + file_name + ".BIN2"

        yield num_chunk

        with open(out_file, "wb") as fout:
            fout.write(b"\x00" * MAGIC_BYTES)
            fout.write(header)

            for k in range(num_chunk):

                start_ind = k * step
                end_ind = min((k + 1) * step, data_length)
                v = channel[start_ind:end_ind]
                
                v = np.round((v + Vrange) / (2 * Vrange) * (1 << ADC_bit)).astype(np.uint32)
                v = np.clip(v, 0, (1 << 8 * n_bytes) - 1)

                if n_bytes == 3:
                    buf = np.empty(v.size * 3, dtype=np.uint8)
                    buf[0::3] = (v & 0xFF)
                    buf[1::3] = (v >> 8) & 0xFF
                    buf[2::3] = (v >> 16) & 0xFF
                    buf.tofile(fout)
                else:
                    dtype_map = {1: np.uint8, 2: np.uint16, 4: np.uint32}
                    v.astype(dtype_map[n_bytes]).tofile(fout)

                yield k
            
            tdms_reader.close()
            yield k

            



    def change_header(self, sampling: Optional[int] = None, ADC_bit: Optional[int] = None, Vrange: Optional[float] = None):
        # 改变BIN文件头信息，并且写入文件
        
        if not self.is_encoded:
            raise appError.BinFileInfoChangedError("This BIN2 file has no header, cannot change header")
        if self.reader is None:
            raise appError.DataFileNotOpenedError("The data file has not been opened")

        sampling = self.sampling if sampling is None else sampling
        ADC_bit = self.ADC_bit if ADC_bit is None else ADC_bit
        Vrange = self.Vrange if Vrange is None else Vrange
        n_bytes = int(math.ceil(ADC_bit / 8))

        header = struct.pack(HEADER_FMT, ADC_bit, Vrange, n_bytes, float(sampling), b"\x00" * 5 )

        self.reader.close()
        with open(self.file_path, "r+b") as f:
            f.seek(0)
            f.write(b"\x00" * MAGIC_BYTES)
            f.write(header)
        self.reader = open(self.file_path, "rb")
        self._detect_format()
