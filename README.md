# 命名规范

所有变量有类型注解：
int   类型： 单位为默认为 sample point / ADC
float 类型： 单位为默认为 s / V

1. global:
    - sampling: 采样率（Hz）
    - pk_posi: 脉冲峰值位置
    - bl_end: 基线结束位置
    - win_len: 窗口长度
    - data_len: 数据长度（sample point）
    - duration: 数据的时长, 单位确定为时间时使用

2. events tree(用于外部储存)
    
    - Baseline: 基线 [V]
    - BL_RMS: 基线均方根值 [V]
    - BL_slope: 基线斜率 [mV/s]

    - prominence: 脉冲峰值 prominence [mV]
    - width: 脉冲半高宽

    - Amp_raw: 原始信号幅度 [V]
    - Amp_fil: 过滤后的信号幅度 [V]
    
    - pk_delay: 滤波后与原始信号相比的的信号延迟 [ms]
    - pk_time: 信号峰值位置 [s]
    - pk_interval: 信号峰值与前一个的间隔 [s]
    - pk_shift: 峰位与格点相比的偏移量 [us]

    - DT: 下降时间 [ms]
    - RT: 上升时间 [ms]
    
    - chi2_raw: 原始信号chi2值
    - chi2_fil: 过滤后的信号chi2值
    - TVL: 左半信号chi2值
    - TVR: 右半信号chi2值
    - corr_raw: 原始信号相关系数
    - corr_fil: 过滤后的信号相关系数
    

    - isValid: 是否为有效事件

3. noise tree(用于外部储存)

    - Baseline: 基线 [V]
    - BL_RMS: 基线均方根值 [V]
    - BL_slope: 基线斜率 [mV/s]
    - BL_p2p: 基线峰峰值 [V]
    - start_time: 噪声起始时间 [s]
    - noise_len: 噪声长度[s]
