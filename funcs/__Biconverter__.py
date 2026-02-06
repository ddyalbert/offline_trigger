#!/usr/bin/env python
# -*- coding: utf-8 -*- 
from PyQt5.QtWidgets import *
import sys
from nptdms import TdmsFile
import time
import numpy as np

def run():
    start = time.process_time()
    _ = QApplication(sys.argv)
    fname, _ = QFileDialog.getOpenFileName(None, "Open File", "/home/duandy/disk/bolometer/Data/", "TDMS file(*.tdms)")
    
    if not fname:  # 用户取消选择文件
        print("No file selected.")
        return
    
    fnewname = fname.split(".tdms", 1)[0]
    
    # 使用流式读取而不是一次性加载整个文件
    print("Opening TDMS file in streaming mode...")
    tdms_file = TdmsFile.open(fname)  # 使用open而不是read以启用流式处理
    
    end = time.process_time()
    print('Time to open the file: %s Seconds' % (end - start))
    
    # 获取组和通道信息
    all_groups = tdms_file.groups()
    print("Groups:", all_groups)
    
    if len(all_groups) < 2:
        print("Error: Expected at least 2 groups in the TDMS file")
        tdms_file.close()
        return
        
    all_group_channels = all_groups[1].channels()
    
    if len(all_group_channels) < 2:
        print("Error: Expected at least 2 channels in the group")
        tdms_file.close()
        return
    
    # 获取通道对象（注意：这里只是获取通道引用，不加载数据）
    channel_heat = all_group_channels[0]
    channel_light = all_group_channels[1]
    
    # 获取数据长度
    data_length = len(channel_heat)
    print("Data length:", data_length)
    
    # 创建输出文件
    print("Make a new File:" + fnewname + "_heat.BIN2")
    fileBIN2_heat = open(fnewname + "_heat.BIN2", 'wb')
    print("Make a new File:" + fnewname + "_light.BIN2")
    fileBIN2_light = open(fnewname + "_light.BIN2", 'wb')
    
    # 设置分块大小（可以根据需要调整）
    chunk_size = 1000000  # 每次处理1百万个样本点
    print('Total chunks: %d' % (data_length // chunk_size + (1 if data_length % chunk_size else 0)))
    
    # 分块处理数据
    for i in range(0, data_length, chunk_size):
        # 计算当前块的结束位置
        end_idx = min(i + chunk_size, data_length)
        
        if i % (chunk_size * 10) == 0:  # 每处理10个块打印一次进度
            print('Processing chunk at index: %d' % i)
        
        # 流式读取当前块的数据
        data_heat_chunk = channel_heat[i:end_idx]
        data_light_chunk = channel_light[i:end_idx]
         
        # 转换数据
        converted_heat = ((data_heat_chunk + 10.0) * (2**24) / 20).astype(np.dtype('<u4'))
        converted_light = ((data_light_chunk + 10.0) * (2**24) / 20).astype(np.dtype('<u4'))
        
        # 写入二进制文件
        txt_heat = converted_heat.tobytes()
        txt_light = converted_light.tobytes()
        fileBIN2_heat.write(txt_heat)
        fileBIN2_light.write(txt_light)
    
    # 关闭文件
    fileBIN2_light.close()
    fileBIN2_heat.close()
    tdms_file.close()  # 关闭TDMS文件
    
    print("Conversion completed successfully!")


if __name__ == "__main__":
    run()