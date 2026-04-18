from PyQt5.QtWidgets import *
from PyQt5 import uic
from PyQt5 import QtGui, QtCore

import numpy as np
from typing import Optional
import time
import sys
import json

import classes.UIwidget as myUI
import classes.events as et
import classes.binFile as binFile
import classes.trigger as tri
import classes.optimalFilter as OF
import classes.appError as appError

class DataAnalyzer(QMainWindow):

    data_file: Optional[binFile.DataFile] = None
    trigger: Optional[tri.Trigger] = None
    events: Optional[et.EventsTree] = None
    of: Optional[OF.OptimalFilter] = None

    sampling: int = 0
     
    win_len: int = 0
    pk_posi: int = 0
    bl_end: int = 0

    main_version = 0
    template_version = 0
    

    def __init__(self):
        super().__init__()
        uic.loadUi("main.ui", self)

        self.setToolTip("")
        for w in self.findChildren(QWidget):
            w:QWidget
            w.setToolTip("")

        self.setFocus()
        self.title = self.windowTitle()
        self.Tabs: QTabWidget
        self.Tabs.setCurrentIndex(0)

        # --------- 初始化 ---------
        self._init_actions()
        self._init_global()
        self._init_preTrigger()
        self._init_findSignal()
        self._init_findNoise()
        self._init_optimalFilter()


    # ============================================================================
    # =========================  actions =========================================
    # ============================================================================

    def _init_actions(self):
        style = self.style()

        self.statusBar: myUI.StatusBarWithProgress
        self.Act_open_data: QAction
        self.Act_save_json: QAction
        self.Act_copy_BIN: QAction
        self.Act_obj_browser: QAction
        self.Act_convert_TDMS: QAction
        self.Act_convert_open_TDMS: QAction

        self.Act_save_json.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        self.Act_save_json.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        self.Act_save_json.triggered.connect(self._save_json)
        self.Act_save_json.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))

        self.Act_open_data.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        self.Act_open_data.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        self.Act_open_data.triggered.connect(lambda: self._open_data(file_path=""))
        self.Act_open_data.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))

        self.Act_copy_BIN.triggered.connect(self._copy_BIN)
        self.Act_obj_browser.triggered.connect(self._obj_browser)
        self.Act_convert_TDMS.triggered.connect(self._convert_TDMS)
        self.Act_convert_open_TDMS.triggered.connect(self._convert_open_TDMS)

        self.test: QPushButton
        # self.test.clicked.connect(self._test)

    def _obj_browser(self):
        if not hasattr(self, "_obj_browser_dialog"):
            self._obj_browser_dialog = myUI.ObjectBrowserDialog(self, parent=self)
        self._obj_browser_dialog.show()
        self._obj_browser_dialog.raise_()
        self._obj_browser_dialog.activateWindow()

    def _reset_widget(self):
        self.mpl_FT.clear_axes()
        self.mpl_NT.clear_axes()
        self.mpl_PT.clear_axes()
        self.mpl_ST.clear_axes()
        self._is_lock_change = False
        self._is_change_startTime = False

    def _create_objs(self):
        self._check_data_file()

        self.trigger = None
        self.of = None
        self.events = None

        threshold = self.DSB_threshold.value()
        width_min = self.DSB_width_min.value()
        height_div_width = self.DSB_height_div_width.value()

        self.trigger = tri.Trigger(self.SB_sampling.value(), threshold, width_min, height_div_width)
        self.trigger.set_win_para(int(self.win_len * self.sampling), int(self.bl_end * self.sampling), int(self.pk_posi * self.sampling))

        self.events = et.EventsTree(self.data_file, {"win_len": self.win_len, "pk_posi": self.pk_posi, "bl_end": self.bl_end}, [self.main_version, self.template_version])
        for method in [self._open_signal_tree, self._open_noise_tree]:
            try:
                method()
            except:
                pass

        self.of = OF.OptimalFilter(int(self.win_len * self.sampling), self.sampling)
        self.trigger.of = self.of

    def _open_data(self, file_path: str = ""):

        # 如果没有data_file类实例，创建一个; 否则，使用已有的实例
        if self.data_file is None:
            sampling = self.SB_sampling.value()
            ADC_bit = self.SB_ADC_bit.value()
            Vrange = self.DSB_Vrange.value()
            data_file = binFile.DataFile(sampling, ADC_bit, Vrange)
        else:
            data_file = self.data_file
        
        # 如果文件文本框有改变，重新打开此文件; 否则，打开文件浏览器选择文件
        if file_path != "":
            self._is_change_filePath = False
            data_file.open(file_path, parent_window=self)
        else:
            if self._is_change_filePath:
                file_path = self.LE_file_path.text()
                self._is_change_filePath = False
                data_file.open(file_path, parent_window=self)
            else:
                try:
                    data_file.open(parent_window=self)
                except:
                    self.statusBar.set_text(f"Sorry, No data file has been chosen!",type_str="No File Chosen Error")
                    return

        if self.data_file is None:
            self.data_file = data_file


        # 设置参数值
        self._reset_widget()
        self._is_warning("off")

        # 如果是编码文件，设置参数值，并且取消用户可以修改的权限
        is_encoded = self.data_file.is_encoded
        if is_encoded:
            self.SB_sampling.setValue(self.data_file.sampling)
            self.SB_ADC_bit.setValue(self.data_file.ADC_bit)
            self.DSB_Vrange.setValue(self.data_file.Vrange)
            self._set_ADC_para()
            self._set_sampling()

        self.SB_sampling.setEnabled(not is_encoded)
        self.SB_ADC_bit.setEnabled(not is_encoded)
        self.DSB_Vrange.setEnabled(not is_encoded)
        
        self.LE_file_path.setText(self.data_file.file_path)
        self.LCD_total_duration.display(self.data_file.total_duration)


        # 重置窗口，创建必要的功能类实例，加载Json
        self._reset_widget()
        self._create_objs()
        self._load_json()
        
        self.SB_start_time_FT.setValue(0)
        self.SB_start_time_PT.setValue(0)
        self._is_warning("on")
        
        self._is_change_filePath = False
        self.statusBar.set_text(f"Open file success: {data_file.file_path}")

    def _browser_data(self, type_str, SB_start_time: QSpinBox, SB_browser_duration: QSpinBox,  mpl: myUI.MPLwidget):
        
        # type_str option: "pk"  "win"  "filter"
        browser_duration = SB_browser_duration.value()
        start_time = SB_start_time.value()
        if self._is_change_startTime:
            vt = self.data_file.read_by_time(start_time, browser_duration)
            self._is_change_startTime = False
        else:
            vt = self.data_file.read_next_by_time(browser_duration)

        if len(vt) < browser_duration * self.sampling:
            QMessageBox.information(self, "Warning!", "You have reached the end of the file! The data will be reset to the beginning.")
            self.data_file.reset_reader(int(start_time * self.sampling))
            return
        else:
            SB_start_time.setValue(start_time + browser_duration)
        
        message = f"Browser: start_time = {start_time} s, duration = {browser_duration} s"

        if self.events.tree_read_signal is not None:
            df = self.events.read_tree_signal_by_time(None, start_time, browser_duration)
            self.trigger.importData(vt, df)
        else:
            self.trigger.importData(vt)
        
        if self.events.tree_read_signal is not None and ("win" in type_str or "pk" in type_str):
            rate = self.trigger.num_events / browser_duration
            message += f"; num of triggered events: {self.trigger.num_events}, trigger rate: {rate:.3f} Hz"
            
        mpl.clear_axes()
        self.trigger.plot(mpl.axes, plot_str=type_str)
        mpl.after_draw()

        return message
    
        
    # ============================================================================
    # =========================  Global methods ==================================
    # ============================================================================
    _is_change_filePath = False

    def _init_global(self):
        self.LCD_total_duration: QLCDNumber
        self.LE_file_path: QLineEdit
        self.SB_sampling: QSpinBox
        self.DSB_Vrange: QSpinBox
        self.SB_ADC_bit: QSpinBox
        self.LCD_total_duration: QLCDNumber
        self.PB_open_data: QPushButton
        self.CB_configuration_list: myUI.FileComboBox
        
        self.SB_main_version: QSpinBox
        self.SB_template_version: QSpinBox

        self.DSB_Vrange.editingFinished.connect(self._set_ADC_para)
        self.SB_ADC_bit.editingFinished.connect(self._set_ADC_para)
        self.SB_sampling.editingFinished.connect(self._set_sampling)
        self.LE_file_path.textChanged.connect(self._change_file_path)
        self.SB_main_version.editingFinished.connect(self._change_version)
        self.SB_template_version.editingFinished.connect(self._change_version)

        self.PB_open_data.clicked.connect(lambda: self._open_data(file_path=""))
        
        self.CB_configuration_list.setFolder(folder=".configuration/", suffix=".json")

        self.main_version = self.SB_main_version.value()
        self.template_version = self.SB_template_version.value()

        self._set_ADC_para()
        self._set_sampling()

    def _change_file_path(self):
        self._is_change_filePath = True

    def _change_version(self):
        mainVersion = self.SB_main_version.value()
        templateVersion = self.SB_template_version.value()
        if mainVersion == self.main_version and templateVersion == self.template_version:
            return
        
        self.main_version = mainVersion
        self.template_version = templateVersion
        if self.data_file is None:
            return
            
        if self.events is not None:
            self.events.set_version(self.main_version, self.template_version)
        
        self._is_warning("off")
        self._reset_widget()
        self._create_objs()
        self._load_json()
        self._is_warning("on")

        self.statusBar.set_text(f"Change version to v{self.main_version}.{self.template_version}")

    # 是否强制改变Global参数
    _is_insist_change: bool = False
    # 是否锁定Global参数的修改
    _is_lock_change: bool = False

    def _is_warning(self, status_str: str = ""):
        if status_str == "off":
            self._is_insist_change = True
        elif status_str == "on":
            self._is_insist_change = False
        elif status_str == "":
            self._is_insist_change = not self._is_insist_change
        
    def _show_change_warning(self) -> bool:
        if getattr(self.events, "tree_read_signal", None) is None:
            return False
        if self._is_insist_change:
            return False
        
        self._is_lock_change = True
        reply = QMessageBox.warning(self, "Warning", 
            "You are change the important parameters, it has been used for pre-trigger. If you want to correct the result, please click Yes, and pre-trigger again after change the parameters.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        self._is_lock_change = False
        
        if reply == QMessageBox.StandardButton.Yes:
            self._is_warning("off")
            return False
        else:
            self._is_warning("on")
            return True
        
    def _set_ADC_para(self):
        if self._is_lock_change:
            return
        if self.data_file is None:
            return
        ADC_bit = self.SB_ADC_bit.value()
        Vrange = self.DSB_Vrange.value()
        if self.data_file.ADC_bit == ADC_bit and self.data_file.Vrange == Vrange:
            return
        if self._show_change_warning():
            self.SB_ADC_bit.setValue(self.data_file.ADC_bit)
            self.DSB_Vrange.setValue(self.data_file.Vrange)
            return

        self.data_file.set_ADC_para(ADC_bit, Vrange)

    def _set_sampling(self):
        if self._is_lock_change:
            return
        sampling = self.SB_sampling.value()
        if self.sampling == sampling:
            return
        if self._show_change_warning():
            self.SB_sampling.setValue(self.data_file.sampling)
            return
        
        self.sampling = sampling
        if self.data_file is not None:
            self.data_file.set_sampling(sampling)
            self.LCD_total_duration.display(self.data_file.total_duration)
        if self.trigger is not None:
            self.trigger.sampling = sampling
        if self.events is not None:
            self.events.sampling = sampling
        if self.of is not None:
            self.of.sampling = sampling

        self._set_win_para_with_sampling()

    def _check_data_file(self):
        if self.data_file is None:
            raise appError.DataFileNotOpenedError(f"Please Open a data file first!")
        
    # ============================================================================
    # =========================  pre-Trigger Tab ==================================
    # ============================================================================
    _is_change_startTime = False

    def _init_preTrigger(self):
        self.DSB_win_len: QDoubleSpinBox
        self.DSB_pk_posi: QDoubleSpinBox
        self.DSB_bl_end: QDoubleSpinBox
        self.DSB_threshold: QDoubleSpinBox
        self.DSB_width_min: QDoubleSpinBox
        self.DSB_height_div_width: QDoubleSpinBox
        self.SB_start_time_PT: QSpinBox
        self.SB_browser_duration_PT: QSpinBox

        self.mpl_PT: myUI.MPLwidget
        self.LCD_events_num: QLCDNumber

        self.PB_browser_PT: QPushButton
        self.PB_pre_trigger: QPushButton
        self.PB_pre_trigger_all: QPushButton

        self.CB_is_plot_win: QCheckBox
        self.CB_is_plot_info_PT: QCheckBox

        self.SB_start_time_PT.valueChanged.connect(self._change_startTime_PT)
        self.DSB_threshold.editingFinished.connect(self._set_threshold)
        self.DSB_width_min.editingFinished.connect(self._set_threshold)
        self.DSB_height_div_width.editingFinished.connect(self._set_threshold)

        self.PB_browser_PT.clicked.connect(self._browser_preTrigger)
        self.PB_pre_trigger.clicked.connect(self._pre_trigger)
        self.PB_pre_trigger_all.clicked.connect(self._pre_trigger_all)

        self.DSB_win_len.editingFinished.connect(self._set_win_para)
        self.DSB_pk_posi.editingFinished.connect(self._set_win_para)
        self.DSB_bl_end.editingFinished.connect(self._set_win_para)

        self._set_win_para()

    def _change_startTime_PT(self):
        self._is_change_startTime = True

    def _set_win_para(self):
        if self._is_lock_change:
            return
        win_len = self.DSB_win_len.value()
        pk_posi = self.DSB_pk_posi.value()
        bl_end = self.DSB_bl_end.value()
        if self.win_len == win_len and self.pk_posi == pk_posi and self.bl_end == bl_end:
            return
        if self._show_change_warning():
            self.DSB_win_len.setValue(self.win_len)
            self.DSB_pk_posi.setValue(self.pk_posi)
            self.DSB_bl_end.setValue(self.bl_end)
            return
        self.win_len = win_len
        self.pk_posi = pk_posi
        self.bl_end = bl_end

        if self.events is not None:
            self.events.set_win_para({"win_len": self.win_len, "pk_posi": self.pk_posi, "bl_end": self.bl_end})

        self._set_win_para_with_sampling()

    def _set_win_para_with_sampling(self):
        if self.trigger is None and self.of is None:
            return
        win_len = int(self.win_len * self.sampling)
        pk_posi = int(self.pk_posi * self.sampling)
        bl_end = int(self.bl_end * self.sampling)
        if self.trigger is not None:
            self.trigger.set_win_para(win_len, bl_end, pk_posi)
        if self.of is not None:
            self.of.win_len = win_len

    def _set_threshold(self):
        if self.trigger is None:
            return
        threshold = self.DSB_threshold.value()
        width_min = self.DSB_width_min.value()
        height_div_width = self.DSB_height_div_width.value() 

        self.trigger.threshold = threshold
        self.trigger.width_min = width_min
        self.trigger.height_div_width = height_div_width

    def _browser_preTrigger(self):
        self._check_data_file()
        plot_str = "pk "
        if self.CB_is_plot_win.isChecked():
            plot_str += "win "
        if self.CB_is_plot_info_PT.isChecked():
            plot_str += "info "
        message = self._browser_data(plot_str, self.SB_start_time_PT, self.SB_browser_duration_PT, self.mpl_PT)
        self.statusBar.set_text(message)

    def _pre_trigger(self):
        self._check_data_file()
        if self.trigger.v is None:
            QMessageBox.critical(self, "Error!", "Please browser the data first!")
            return

        self.trigger.find_peaks()
        self.trigger.get_pulse_parameters()
        rate = self.trigger.num_events/(self.trigger.data_len/self.sampling)
        self.statusBar.set_text(f"Pre-Trigger this window done! Num of Events: {self.trigger.num_events}, trigger rate: {rate:.3f} Hz", type_str="Pre-Trigger")
        
        xl = self.mpl_PT.axes.get_xlim()
        yl = self.mpl_PT.axes.get_ylim()

        plot_str = "pk "
        if self.CB_is_plot_win.isChecked():
            plot_str += "win "
        if self.CB_is_plot_info_PT.isChecked():
            plot_str += "info "

        self.mpl_PT.clear_axes()
        self.trigger.plot(self.mpl_PT.axes,  plot_str=plot_str)
        self.mpl_PT.after_draw()

        self.mpl_PT.axes.set_xlim(xl)
        self.mpl_PT.axes.set_ylim(yl)
        self.mpl_PT.canvas.draw()

    def _pre_trigger_all(self):
        try:
            self.__pre_trigger_all()
        except Exception as e:
            self.events.delete_tree("signal_raw")
            QMessageBox.critical(self, "Error!", f"An error occurred, the pre-trigger root file has been deleted!")

    def __pre_trigger_all(self):
        self._check_data_file()

        self.events.recreate_tree_siganl()
        read_step = int(3600 * self.sampling)
        read_len = read_step + self.trigger.win_len - 1
        self.data_file.reset_reader()
        num_chunk = int(np.ceil(self.data_file.total_length / read_step))

        self.statusBar.start(f"Pre-triggering...", 0, num_chunk)

        time_start = time.time()
        for i in range(num_chunk):
            vt = self.data_file.read_by_index(i * read_step, read_len)
            if len(vt) < 5 * self.trigger.win_len:
                break
            self.trigger.importData(vt)
            self.trigger.find_peaks()
            if i == 0:
                segment = -1
            elif i == num_chunk - 1:
                segment = 1
            else:
                segment = 0

            self.trigger.get_pulse_parameters(segment)
            
            self.trigger.pulse_paras['pk_time'] += i * read_step/self.sampling
            self.events.write_tree_signal(self.trigger.pulse_paras)
            self.statusBar.set_value(i + 1)

        time_end = time.time()
        rate = self.events.num_signal/ self.LCD_total_duration.value() / 3600
        self.statusBar.finish(f"Pre-trigger done! Num of Events: {self.events.num_signal}; trigger rate: {rate:.3f} Hz; Time cost: {time_end - time_start:.3f} s")

        self._reopen_signal_tree(is_filtered = False)

        self.LCD_events_num.display(self.events.num_signal)
        self._is_warning("on")

        self.trigger.importData()
        self.data_file.reset_reader()
        self._save_general_para()


    # ============================================================================
    # =========================  Find Signal Tab ==================================
    # ============================================================================
    def _init_findSignal(self):
        self.DSB_Amp_raw_min: QDoubleSpinBox
        self.DSB_Amp_raw_max: QDoubleSpinBox
        self.DSB_DT_min: QDoubleSpinBox
        self.DSB_DT_max: QDoubleSpinBox
        self.DSB_RT_min: QDoubleSpinBox
        self.DSB_RT_max: QDoubleSpinBox
        self.DSB_BL_RMS_min: QDoubleSpinBox
        self.DSB_BL_RMS_max: QDoubleSpinBox
        self.DSB_BL_slope_min: QDoubleSpinBox
        self.DSB_BL_slope_max: QDoubleSpinBox
        self.DSB_pk_shift_min: QDoubleSpinBox
        self.DSB_pk_shift_max: QDoubleSpinBox
        self.SB_num_comp: QSpinBox
        self.SB_default_cut_num_ST: QSpinBox
        self.CB_is_fit_filter: QCheckBox
        self.CoB_default_cut_value_ST: QComboBox

        self._min_signal_cut = {
            "Amp_raw": self.DSB_Amp_raw_min,
            "DT": self.DSB_DT_min,
            "RT": self.DSB_RT_min,
            "BL_RMS": self.DSB_BL_RMS_min,
            "BL_slope": self.DSB_BL_slope_min,
            "pk_shift": self.DSB_pk_shift_min,
        }
        self._max_signal_cut = {
            "Amp_raw": self.DSB_Amp_raw_max,
            "DT": self.DSB_DT_max,
            "RT": self.DSB_RT_max,
            "BL_RMS": self.DSB_BL_RMS_max,
            "BL_slope": self.DSB_BL_slope_max,
            "pk_shift": self.DSB_pk_shift_max,
        }
        self._symmetry_signal_cut = {
            "BL_slope": self.DSB_BL_slope_max,
            "pk_shift": self.DSB_pk_shift_max,
        }

        for key in self._symmetry_signal_cut:
            self._symmetry_signal_cut[key].valueChanged.connect(lambda: self._set_signal_cut_symmetry(False))
            self._symmetry_signal_cut[key].editingFinished.connect(lambda: self._set_signal_cut_symmetry(True))
        for key in self._min_signal_cut:
            self._min_signal_cut[key].editingFinished.connect(self._set_signal_cut_min)
        for key in self._max_signal_cut:
            self._max_signal_cut[key].editingFinished.connect(self._set_signal_cut_max)

        self.mpl_ST: myUI.MPLwidget
        self.PB_cut_ST: QPushButton
        self.PB_get_ST: QPushButton
        self.PB_plot_ST: QPushButton
        self.PB_fit_template: QPushButton
        self.PB_fit_as_template: QPushButton
        self.PB_default_cut_ST: QPushButton
        self.LCD_cut_num_ST: QLCDNumber
        self.CB_is_normalize: QCheckBox
        
        self.PB_cut_ST.clicked.connect(self._apply_signal_cut)
        self.PB_plot_ST.clicked.connect(self._plot_signal)
        self.PB_get_ST.clicked.connect(self._get_signal)
        self.PB_fit_template.clicked.connect(self._fit_signal_template)
        self.PB_fit_as_template.clicked.connect(self._fit_as_template)
        self.PB_default_cut_ST.clicked.connect(self._default_signal_cut)

            
    def _reopen_signal_tree(self, is_filtered: bool = None):
        self.events.open_tree_signal(is_filtered = is_filtered)
        self._set_signal_cut_min()      
        self._set_signal_cut_max()
    def _open_signal_tree(self):
        self._check_data_file()
        if self.events.tree_read_signal is None:
            self._reopen_signal_tree()


    def _set_signal_cut_symmetry(self, is_update_min: bool):
        for key in self._symmetry_signal_cut:
            self._min_signal_cut[key].setValue( - self._symmetry_signal_cut[key].value())
        if is_update_min:
            self._set_signal_cut_min()

    def _set_signal_cut_min(self):
        if self.events.tree_read_signal is None:
            return
        self.events.min_cut_signal = {
            key: self._min_signal_cut[key].value() for key in self._min_signal_cut
        }
    def _set_signal_cut_max(self):
        if self.events.tree_read_signal is None:
            return
        self.events.max_cut_signal = {
            key: self._max_signal_cut[key].value() for key in self._max_signal_cut
        }

    def _default_signal_cut(self):
        self._open_signal_tree()

        value_name = self.CoB_default_cut_value_ST.currentText()
        self.events.default_signal_cut(cut_num= self.SB_default_cut_num_ST.value(), valueName=value_name)
        self.LCD_cut_num_ST.display(self.events.num_signal_cut)
        min_dict, max_dict = self.events.get_max_min_value(tree_name="signal")

        for key in self._min_signal_cut:
            self._min_signal_cut[key].setValue(min_dict[key])
        for key in self._max_signal_cut:
            self._max_signal_cut[key].setValue(max_dict[key])
        self._set_signal_cut_max()
        self._set_signal_cut_min()

        self.statusBar.set_text(f"Default cut done! "
            f"Num of signal template: {self.events.num_signal_cut}, total num: {self.events.num_signal}", 
            type_str="Default Cut Signal")

    def _apply_signal_cut(self):
        self._open_signal_tree()

        self.events.apply_signal_cut()
        self.LCD_cut_num_ST.display(self.events.num_signal_cut)
        self.statusBar.set_text(f"Cut done! "
            f"Num of signal template: {self.events.num_signal_cut}, total num: {self.events.num_signal}",
            type_str="Apply Signal Cut")

    def _plot_signal(self):
        self._open_signal_tree()
        
        is_normalize = self.CB_is_normalize.isChecked()
        self.mpl_ST.clear_axes()
        
        step = 500
        num_chunk = self.events.num_signal_cut // step + 1
        t_start = time.time()
        self.statusBar.start(text="Plotting the noise...", minimum=0, maximum=num_chunk)

        try:
            for k in self.events.plot_signal(step, is_normalize, self.mpl_ST.axes):
                self.statusBar.set_value(k)
        except:
            self.statusBar.finish("")
            raise

        self.statusBar.finish(f"Rendering the figure...")
        QApplication.processEvents()
        self.mpl_ST.after_draw()

        t_end = time.time()
        out_str = f"Num of signal template: {self.events.num_signal_cut}, Time cost: {t_end-t_start:.2f} s"

        if is_normalize:
            self.statusBar.set_text(f"Plot all the signal with normalize, {out_str}", type_str="Plot Signal Normalize")
        else:
            self.statusBar.set_text(f"Plot all the signal without normalize, {out_str}", type_str="Plot Signal Without Normalize")

    def _get_signal(self):
        self._open_signal_tree()
        
        self.of.clear_signal()
        self.events.add_signal(self.of)
        sum_amp = self.of.get_signal_f()
        self.statusBar.set_text(f"Get the signal template; "
            f"Num of signal: {self.events.num_signal_cut}, Total amplitude = {sum_amp:.2f} V; "
            f"RT = {self.of.RT/self.of.sampling*1000:.2f} ms, DT = {self.of.DT/self.of.sampling*1000:.2f} ms",
            type_str="Get Signal")

        self.mpl_ST.clear_axes()
        self.of.plot_time_domain(self.mpl_ST.axes, plot_type="s_")
        self.mpl_ST.after_draw()
        
        self.events.save_cut("signal")
        self.of.save_json(self.data_file.file_dir,[self.main_version, self.template_version])

    def _fit_signal_template(self):
        self._check_data_file()
        self.of.fit_signal_template(self.SB_num_comp.value(), self.CB_is_fit_filter.isChecked())
        self.mpl_ST.clear_axes()
        self.of.fit.plotFit(self.mpl_ST.axes)
        self.mpl_ST.after_draw()
        self.statusBar.set_text(f"Fit the signal template", type_str="Fit Signal Template")

    def _fit_as_template(self):
        if self.of is None:
            raise appError.CutNotAppliedError("Please fit the signal template first!")

        self.of.fit_as_template(is_true = not self.of.is_fit_as_template)
        try:
            self._construct_optimalFilter()
        except:
            pass

        if self.of.is_fit_as_template:
            self.statusBar.set_text(f"Fit result has set as signal template!")
        else:
            self.statusBar.set_text(f"Fit result has canceled as signal template!")

    # ============================================================================
    # =========================  Find Noise Tab ==================================
    # ============================================================================
    def _init_findNoise(self):
        self.DSB_BL_noise_min: QDoubleSpinBox
        self.DSB_BL_noise_max: QDoubleSpinBox
        self.DSB_BL_RMS_noise_min: QDoubleSpinBox
        self.DSB_BL_RMS_noise_max: QDoubleSpinBox
        self.DSB_BL_slope_noise_min: QDoubleSpinBox
        self.DSB_BL_slope_noise_max: QDoubleSpinBox
        self.DSB_BL_p2p_noise_min: QDoubleSpinBox
        self.DSB_BL_p2p_noise_max: QDoubleSpinBox
        self.DSB_noise_len_min: QDoubleSpinBox
        self.DSB_noise_len_max: QDoubleSpinBox
        self.SB_default_cut_num_NT: QSpinBox

        self._min_noise_cut = {
            "Baseline": self.DSB_BL_noise_min,
            "BL_RMS": self.DSB_BL_RMS_noise_min,
            "BL_slope": self.DSB_BL_slope_noise_min,
            "BL_p2p": self.DSB_BL_p2p_noise_min,
            "noise_len": self.DSB_noise_len_min,
        }
        self._max_noise_cut = {
            "Baseline": self.DSB_BL_noise_max,
            "BL_RMS": self.DSB_BL_RMS_noise_max,
            "BL_slope": self.DSB_BL_slope_noise_max,
            "BL_p2p": self.DSB_BL_p2p_noise_max,
            "noise_len": self.DSB_noise_len_max,
        }
        self._symmetry_noise_cut = {
            "BL_slope": self.DSB_BL_slope_noise_max,
        }

        for key in self._symmetry_noise_cut:
            self._symmetry_noise_cut[key].valueChanged.connect(lambda: self._set_symmetry_noise_cut(False))
            self._symmetry_noise_cut[key].editingFinished.connect(lambda: self._set_symmetry_noise_cut(True))
        for key in self._min_noise_cut:
            self._min_noise_cut[key].editingFinished.connect(self._set_noise_cut_min)
        for key in self._max_noise_cut:
            self._max_noise_cut[key].editingFinished.connect(self._set_noise_cut_max)

        self.mpl_NT: myUI.MPLwidget
        self.PB_find_noise: QPushButton
        self.PB_cut_NT: QPushButton
        self.PB_get_NT: QPushButton
        self.PB_plot_NT: QPushButton
        self.PB_default_cut_NT: QPushButton
        self.LCD_cut_num_NT: QLCDNumber
        self.PB_get_baseline_resolution: QPushButton
        self.CB_is_align: QCheckBox
        
        self.PB_find_noise.clicked.connect(self._find_noise)
        self.PB_cut_NT.clicked.connect(self._apply_noise_cut)
        self.PB_plot_NT.clicked.connect(self._plot_noise)
        self.PB_get_NT.clicked.connect(self._get_noise)
        self.PB_default_cut_NT.clicked.connect(self._default_noise_cut)
        self.PB_get_baseline_resolution.clicked.connect(self._get_baseline_resolution)

    def _reopen_noise_tree(self):
        self.events.open_tree_noise()
        self._set_noise_cut_min()
        self._set_noise_cut_max()
    def _open_noise_tree(self):
        self._check_data_file()
        if self.events.tree_read_noise is None:
            self._reopen_noise_tree()

    def _set_symmetry_noise_cut(self, is_update_min: bool):
        for key in self._symmetry_noise_cut:
            self._min_noise_cut[key].setValue( - self._symmetry_noise_cut[key].value())
        if is_update_min:
            self._set_noise_cut_min()

    def _set_noise_cut_min(self):
        if self.events.tree_read_noise is None:
            return
        self.events.min_cut_noise = {
            key: self._min_noise_cut[key].value() for key in self._min_noise_cut
        }
    def _set_noise_cut_max(self):
        if self.events.tree_read_noise is None:
            return
        self.events.max_cut_noise = {
            key: self._max_noise_cut[key].value() for key in self._max_noise_cut
        }
    
    def _find_noise(self):
        self._open_signal_tree()
        step = 500
        num_chunk = self.events.num_signal // step + 1
        self.statusBar.start(text="Finding the noise...", minimum=0, maximum=num_chunk)
        t_start = time.time()
        for k in self.events.find_tree_noise(step=step):
            self.statusBar.set_value(k)
        t_end = time.time()
        self.statusBar.finish(f"Find the noise done! Total num of noise: {self.events.num_noise}, "
            f"Time cost: {t_end - t_start:.2f} s")
        self._reopen_noise_tree()

    def _default_noise_cut(self):
        self._open_noise_tree()
        
        value_name = "BL_slope"
        self.events.default_noise_cut(cut_num=self.SB_default_cut_num_NT.value(), valueName=value_name)
        self.LCD_cut_num_NT.display(self.events.num_noise_cut)

        min_dict, max_dict = self.events.get_max_min_value(tree_name="noise")
        for key in min_dict:
            self._min_noise_cut[key].setValue(min_dict[key])
        for key in max_dict:
            self._max_noise_cut[key].setValue(max_dict[key])
        self._set_noise_cut_max()
        self._set_noise_cut_min()
        self.statusBar.set_text(f"Default cut done! Num of noise template: {self.events.num_noise_cut}, "
            f"total num: {self.events.num_noise}", type_str="Default Noise Cut")

    def _apply_noise_cut(self):
        self._open_noise_tree()

        self.events.apply_noise_cut()
        self.LCD_cut_num_NT.display(self.events.num_noise_cut)
        self.statusBar.set_text(f"Cut done! Num of noise template: {self.events.num_noise_cut}, "
            f"total num: {self.events.num_noise}", type_str="Default Noise Cut")

    def _plot_noise(self):
        self._open_noise_tree()
        
        is_align = self.CB_is_align.isChecked()

        self.mpl_NT.clear_axes()

        step = 500
        num_chunk = self.events.num_noise // step + 1
        t_start = time.time()
        self.statusBar.start(text="Plotting the noise...", minimum=0, maximum=num_chunk)
        try:
            for k in self.events.plot_noise(step, is_align, self.mpl_NT.axes):
                self.statusBar.set_value(k)
        except:
            self.statusBar.finish("")
            raise

        self.statusBar.finish(f"Rendering the figure...")
        QApplication.processEvents()

        self.mpl_NT.after_draw()
        
        t_end = time.time()

        out_str = (f"Num of noise template: {self.events.num_noise_cut}, "
                     f"Time cost: {t_end - t_start:.2f} s" )
        if is_align:
            self.statusBar.set_text(f"Plot all the noise with align, {out_str}", type_str="Plot Noise Align")
        else:
            self.statusBar.set_text(f"Plot all the noise without align, {out_str}", type_str="Plot Noise Without Align")

    def _get_noise(self):
        self._open_noise_tree()
        
        self.of.clear_noise()

        self.events.add_noise(self.of)
        self.of.get_noise_psd()
        self.statusBar.set_text(f"Get the noise template, "
            f"Num of noise: {self.events.num_noise_cut}, Num of noise window: {self.of.num_noise}, "
            f"RMS of noise: {self.of.rms_noise * 1000:.3f} mV", type_str="Get Noise")

        self.mpl_NT.clear_axes()
        self.of.plot_freq_domain(self.mpl_NT.axes, plot_type="n_")
        self.mpl_NT.after_draw()

        self.events.save_cut("noise")
        self.of.save_json(self.data_file.file_dir,[self.main_version, self.template_version])
        
    def _get_baseline_resolution(self):
        self._open_noise_tree()
        self.events.create_bl_sigma(self.of)

        self.events.add_noise(self.events.bl_sigma)

        self.mpl_NT.clear_axes()
        self.events.bl_sigma.plot(self.mpl_NT.axes)
        self.mpl_NT.after_draw()

        text = (f"Get the baseline resolution: "
            f"Raw baseline resolution: {self.events.bl_sigma.sigma_raw:.3f} mV") 
        if self.events.bl_sigma.sigma_fil != 0.0:
            text += f", Filtered baseline resolution: {self.events.bl_sigma.sigma_fil:.3f} mV"

        self.statusBar.set_text(text, type_str="Get Baseline Resolution")

    # ============================================================================
    # =========================  Optimal Filter Tab ==============================
    # ============================================================================

    def _init_optimalFilter(self):
        self.PB_browser_FT: QPushButton
        self.PB_filter: QPushButton
        self.PB_filter_all: QPushButton
        self.PB_construct_filter: QPushButton

        self.RB_freq_domain: QRadioButton
        self.RB_time_domain: QRadioButton

        self.SB_start_time_FT: QSpinBox
        self.SB_browser_duration_FT: QSpinBox

        self.CB_is_plot_peaks: QCheckBox
        self.CB_is_plot_info_FT: QCheckBox

        self.mpl_FT: myUI.MPLwidget

        self.PB_construct_filter.clicked.connect(lambda: self._construct_optimalFilter(is_save=True))
        self.RB_freq_domain.toggled.connect(self._plot_optimalFilter)
        self.SB_start_time_FT.valueChanged.connect(self._change_startTime_FT)

        self.PB_browser_FT.clicked.connect(self._browser_optimalFilter)
        
        self.PB_filter.clicked.connect(self._filter)
        self.PB_filter_all.clicked.connect(self._filter_all)

    def _change_startTime_FT(self):
        self._is_change_startTime = True
    
    def _construct_optimalFilter(self, is_save: bool = True):
        self._check_data_file()
        self.of.get_filter()
        self._plot_optimalFilter()
        self.statusBar.set_text(f"Construct the optimal filter done! "
            f"Num of signal: {self.of.num_signal}, Num of noise: {self.of.num_noise}, "
            f"RMS of noise: {self.of.rms_noise * 1000:.3f} mV, RMS of filtered noise: {self.of.rms_noise_filtered * 1000:.3f} mV",
            type_str="Construct Optimal Filter")
        
        if is_save:
            self.of.save_json(self.data_file.file_dir,[self.main_version, self.template_version])

    def _plot_optimalFilter(self):
        if not self.of.is_can_filter:
            return
        self.mpl_FT.clear_axes()
        if self.RB_freq_domain.isChecked():
            self.of.plot_freq_domain(self.mpl_FT.axes)
        else:
            self.of.plot_time_domain(self.mpl_FT.axes)
        self.mpl_FT.after_draw()

    def _browser_optimalFilter(self):
        self._check_data_file()
        plot_str = "filter "
        if self.CB_is_plot_peaks.isChecked():
            plot_str += "pk "
        if self.CB_is_plot_info_FT.isChecked():
            plot_str += "info "

        massage = self._browser_data(plot_str,self.SB_start_time_FT, self.SB_browser_duration_FT, self.mpl_FT)
        self.statusBar.set_text(massage)

    def _filter(self):
        self._check_data_file()
        if self.trigger.v is None:
            QMessageBox.critical(self, "Error!", "Please browser the data first!")
            return
        if self.events.tree_read_signal is None:
           raise appError.RootFileNotOpenedError("Root file of signal is not found! Please pre-trigger first!")
        
        self.trigger.trigger_with_filter()
        self.trigger.get_pulse_parameters_filter()

        rate = self.trigger.num_events/(self.trigger.data_len/self.sampling)
        self.statusBar.set_text(f"Filter and trigger this window done! " 
            f"Num of Events: {self.trigger.num_events}, trigger rate: {rate:.3f} Hz", type_str="Filter and Trigger")
        
        xl = self.mpl_FT.axes.get_xlim()
        yl = self.mpl_FT.axes.get_ylim()

        plot_str = "filter "
        if self.CB_is_plot_peaks.isChecked():
            plot_str += "pk "
        if self.CB_is_plot_info_FT.isChecked():
            plot_str += "info "

        self.mpl_FT.clear_axes()
        self.trigger.plot(self.mpl_FT.axes,  plot_str=plot_str)
        self.mpl_FT.after_draw()

        self.mpl_FT.axes.set_xlim(xl)
        self.mpl_FT.axes.set_ylim(yl)
        self.mpl_FT.canvas.draw()

    def _filter_all(self):
        try:
            self.__filter_all()
        except Exception as e:
            self.events.delete_tree("signal_fil")
            QMessageBox.critical(self, "Error!", f"An error occurred, the filtered root file has been deleted!")

    def __filter_all(self):
        self._check_data_file()
        
        self.events.recreate_tree_siganl(is_filtered=True)

        read_step = int(1800 * self.sampling)
        read_len = read_step + 2 * self.trigger.win_len - 1
        self.data_file.reset_reader()
        num_chunk = int(np.ceil(self.data_file.total_length / read_step))

        self.statusBar.start(f"Filter and trigger ...", 0, num_chunk)

        time_start = time.time()
        for i in range(num_chunk):
            vt = self.data_file.read_by_index(i * read_step, read_len)
            if len(vt) < 5 * self.trigger.win_len:
                break
            
            start_time = i * read_step/self.sampling
            df = self.events.read_tree_signal_by_time(None, start_time, read_len/self.sampling)
            self.trigger.importData(vt, df)

            if i == 0:
                segment = -1
            elif i == num_chunk - 1:
                segment = 1
            else:
                segment = 0
            
            self.trigger.filter_data()
            self.trigger.trigger_with_filter()
            self.trigger.get_pulse_parameters_filter(segment=segment)

            self.trigger.pulse_paras['pk_time'] += start_time
            self.events.write_tree_signal(self.trigger.pulse_paras)
            self.statusBar.set_value(i + 1)

        time_end = time.time()
        rate = self.events.num_signal/ self.LCD_total_duration.value() / 3600
        self.statusBar.finish(f"Filter and trigger all done! Num of Events: {self.events.num_signal}; trigger rate: {rate:.3f} Hz; "
            f"Time cost: {time_end - time_start:.3f} s")

        self._reopen_signal_tree(is_filtered = True)

        self.trigger.importData()
        self.data_file.reset_reader()

    # ============================================================================
    # =========================  Save and Load JSON ==============================
    # ============================================================================

    def _save_json(self):
        self._check_data_file()

        self._save_general_para()

        save_info = f"Save general para json success"

        if self.events is not None:
            self.events.save_cut()
            save_info += f", save cut json success"

        if self.of is not None:
            self.of.save_json(self.data_file.file_dir,[self.main_version, self.template_version])
            save_info += f", save filter json success"

        self.statusBar.set_text(save_info, type_str="Save JSON")

    def _save_general_para(self):
        self._check_data_file()
        dict_config = {
            "sampling": self.sampling,
            "Vrange": self.DSB_Vrange.value(),
            "ADC_bit": self.SB_ADC_bit.value(),
            "win_len": self.win_len,
            "pk_posi": self.pk_posi,
            "bl_end": self.bl_end,
            "pk_width_min": self.DSB_width_min.value(),
            "height_div_width": self.DSB_height_div_width.value(),
            "threshold": self.DSB_threshold.value(),
        }
        json_file_name = f"GeneralPara_v{self.main_version}.json"
        with open(self.data_file.file_dir + json_file_name, "w") as f:
            json.dump(dict_config, f, indent=4, sort_keys=True)
    
    def _load_json(self):
        self._check_data_file()
        json_file_name = f"GeneralPara_v{self.main_version}.json"
        try:
            with open(self.data_file.file_dir + json_file_name, "r") as f:
                dict_config = json.load(f)
        except:
            return
        
        self._is_warning("off")
        if not self.data_file.is_encoded:
            self.SB_sampling.setValue(dict_config["sampling"])
            self.DSB_Vrange.setValue(dict_config["Vrange"])
            self.SB_ADC_bit.setValue(dict_config["ADC_bit"])

        self.DSB_win_len.setValue(dict_config["win_len"])
        self.DSB_pk_posi.setValue(dict_config["pk_posi"])
        self.DSB_bl_end.setValue(dict_config["bl_end"])
        self.DSB_height_div_width.setValue(dict_config["height_div_width"])
        self.DSB_width_min.setValue(dict_config["pk_width_min"])
        self.DSB_threshold.setValue(dict_config["threshold"])

        self._set_ADC_para()
        self._set_win_para()
        self._set_sampling()
        self._set_threshold()
        
        tab_index = 3
        if self.events.load_cut():
            self._get_cut_to_widget()
        else:
            tab_index = 1

        if self.of.load_json(self.data_file.file_dir, [self.main_version, self.template_version]):
            try:
                self._construct_optimalFilter(is_save=False)
            except:
                pass
        
        if self.of.is_can_filter:
            tab_index = 3
        elif self.of.signal_t_raw is not None:
            tab_index = 2
        else:
            tab_index = 1

        if self.events.tree_read_signal is None:
            tab_index = 0
        else:
            self.LCD_events_num.display(self.events.num_signal)

        self._is_warning("on")
        
        self.Tabs.setCurrentIndex(tab_index)
        self.statusBar.set_text(f"Load json success!", type_str="Load JSON")
        
    def _get_cut_to_widget(self):
        if self.events.max_cut_noise:
            for key in self._max_noise_cut:
                self._max_noise_cut[key].setValue(self.events.max_cut_noise[key])
        if self.events.min_cut_noise:
            for key in self._min_noise_cut:
                self._min_noise_cut[key].setValue(self.events.min_cut_noise[key])
        if self.events.max_cut_signal:
            for key in self._max_signal_cut:
                self._max_signal_cut[key].setValue(self.events.max_cut_signal[key])
        if self.events.min_cut_signal:
            for key in self._min_signal_cut:
                self._min_signal_cut[key].setValue(self.events.min_cut_signal[key])

    # ============================================================================
    # ==========================Other Function ===================================
    # ============================================================================

    def __input_get_BIN_para(self):

        if hasattr(self, "sampling"):
            sampling = self.sampling
        else:
            sampling = 5000

        if hasattr(self,"data_file") and hasattr(self.data_file,"ADC_bit"):
            ADC_bit = self.data_file.ADC_bit
        else:
            ADC_bit = 16
        
        if hasattr(self,"data_file") and hasattr(self.data_file,"Vrange"):
            Vrange = self.data_file.Vrange
        else:
            Vrange = 5


        sampling, ok1 = QInputDialog.getInt(self, "Input Sampling", "Please input sampling rate of File (Hz):", value=sampling, min=1)
        if not ok1:
            return (False, None, None, None)
        
        ADC_bit, ok2 = QInputDialog.getInt(self, "Input ADC bits", "Please input ADC bits of new file:", value=ADC_bit, min=1, max=32)
        if not ok2:
            return (False, None, None, None)
        
        Vrange, ok3 = QInputDialog.getDouble(self, "Input Vrange", "Please input Voltage range of new file (±V):", value=Vrange, min=0.01)
        if not ok3:
            return (False, None, None, None)
        
        return (True, sampling, ADC_bit, Vrange)


    def _copy_BIN(self):
        self._check_data_file()

        if self.data_file.is_encoded:
            reply0 = QMessageBox.question( self, "Warning",
                "The data file is already encoded.\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
            )
            if reply0 == QMessageBox.StandardButton.No:
                self.statusBar.set_text("Copy BIN file action canceled.", type_str="Copy BIN File Canceled")
                return
        
        reply = QMessageBox.question( self, "Copy BIN File with header",
            f"The program will copy the BIN file with header. Please make sure follow info of raw file is correct:\n\nADC bit = {self.data_file.ADC_bit}, Voltage range(±) = {self.data_file.Vrange} V ",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )

        ok, sampling, ADC_bit, Vrange = self.__input_get_BIN_para()
        if not ok:
            self.statusBar.set_text("Copy BIN file action canceled.", type_str="Copy BIN File Canceled")
            return
        
        if reply == QMessageBox.StandardButton.No:
            self.statusBar.set_text("Copy BIN file action canceled.", type_str="Copy BIN File Canceled")
            return
        
        step = int(1e6)
        num_chunk = int(np.ceil(self.data_file.total_length / step))
        self.statusBar.start("Copying BIN file...", 0, num_chunk)
        
        out_file = self.data_file.file_dir + self.data_file.file_name + "_copy.BIN2"
        for k in self.data_file.copy_file_with_header(out_file=out_file, sampling=sampling, ADC_bit=ADC_bit, Vrange=Vrange, step=step):
            self.statusBar.set_value(k + 1)
        self.data_file.reset_reader()
        self.statusBar.finish("Copy BIN file successfully to " + out_file)

    
    def _convert_TDMS(self):

        import funcs.fileIO as fileIO

        tdms_file = fileIO.get_file(self, filter="TDMS file(*.tdms)", title="Choose a TDMS file")
        if tdms_file == "":
            self.statusBar.set_text("No TDMS file chosen.", type_str="Convert TDMS File Canceled")
            return
        
        self.statusBar.set_text("Opening TDMS file ... ")

        ok, sampling, ADC_bit, Vrange = self.__input_get_BIN_para()
        if not ok:
            self.statusBar.set_text("Convert TDMS file action canceled.", type_str="Convert TDMS File Canceled")
            return
        
        
        step = int(1e6)

        file_dir, file_name, _ = fileIO.extract_file_info(tdms_file)
        out_file = file_dir + file_name + ".BIN2"

        

        is_first = True
        for k in binFile.DataFile.convert_TDMS(tdms_file, sampling, ADC_bit, Vrange, out_file, step):
            if is_first:
                self.statusBar.start("Converting TDMS to BIN file...", 0, k)
                is_first = False
            self.statusBar.set_value(k + 1)

        self.statusBar.finish("Convert TDMS file successfully to " + out_file)
        return out_file

    def _convert_open_TDMS(self):
        out_file = self._convert_TDMS()
        self._open_data(out_file)
        self.statusBar.set_text("Convert and open TDMS file successfully: " + out_file)
        



    # def _copy_BIN(self):
    #     self._check_data_file()

    #     if self.data_file.is_encoded:
    #         reply0 = QMessageBox.question( self, "Warning",
    #             "The data file is already encoded.\nDo you want to continue?",
    #             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
    #         )
    #         if reply0 == QMessageBox.StandardButton.No:
    #             self.statusBar.set_text("Copy BIN file action canceled.")
    #             return
        
    #     reply = QMessageBox.question( self, "Copy BIN File with header",
    #         f"The program will copy the BIN file with header. Please make sure follow info of raw file is correct:\n\nADC bit = {self.data_file.ADC_bit}, Voltage range(±) = {self.data_file.Vrange} V ",
    #         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
    #     )

    #     if reply == QMessageBox.StandardButton.No:
    #         self.statusBar.set_text("Copy BIN file action canceled.")
    #         return
        
    #     sampling, ok1 = QInputDialog.getInt(self, "Input Sampling", "Please input sampling rate of File (Hz):", value=self.sampling, min=1)
    #     if not ok1:
    #         self.statusBar.set_text("Copy BIN file action canceled.")
    #         return
        
    #     ADC_bit, ok2 = QInputDialog.getInt(self, "Input ADC bits", "Please input ADC bits of new file:", value=self.data_file.ADC_bit, min=1, max=32)
    #     if not ok2:
    #         self.statusBar.set_text("Copy BIN file action canceled.")
    #         return
        
    #     Vrange, ok3 = QInputDialog.getDouble(self, "Input Vrange", "Please input Voltage range of new file (±V):", value=self.data_file.Vrange, min=0.01)
    #     if not ok3:
    #         self.statusBar.set_text("Copy BIN file action canceled.")
    #         return
        
    #     self._progress = QProgressDialog( "Copying data...", "Cancel", 0, 100, self)
    #     # self._progress.setWindowTitle("Processing")
    #     self._progress.setMinimumDuration(0)
    #     self._progress.setAutoClose(True)
    #     self._progress.setAutoReset(True)
    #     self._progress.show()

    #     self._args = (sampling, ADC_bit, Vrange)
    #     # 线程
    #     self._copy_thread = QtCore.QThread(self)
    #     self._copy_thread.started.connect(self._copy_BIN_worker)
    #     self._copy_thread.finished.connect(self._copy_thread.deleteLater)

    #     self._abort_copy = False
    #     self._progress.canceled.connect(self._copy_BIN_canceled)

    #     self._copy_thread.start()

    # def _copy_BIN_canceled(self):
    #     self._abort_copy = True

    # @QtCore.pyqtSlot()
    # def _copy_BIN_finished(self):
    #     if self._abort_copy:
    #         QMessageBox.information(self, "Aborted", "Copy BIN file action canceled.")
    #     else:
    #         QMessageBox.information(self, "Success", "Copy BIN file finished.")
        
    #     self._progress = None
    #     self._copy_thread = None
    #     self._args = None
    #     self._abort_copy = None
        
    # def _copy_BIN_worker(self):
    #     try:
    #         step = int(1e6)
    #         num_chunk = int(np.ceil(self.data_file.total_length / step))
    #         sampling, ADC_bit, Vrange = self._args
    #         temp_open_file = binFile.dataFile(sampling=sampling, ADC_bit=self.data_file.ADC_bit, Vrange=self.data_file.Vrange)
    #         temp_open_file.open(self.data_file.file_path)

    #         out_file = self.data_file.file_dir + self.data_file.file_name + "_copy.BIN2"
    #         for k in temp_open_file.copy_file_with_header(out_file=out_file, sampling=sampling, ADC_bit=ADC_bit, Vrange=Vrange, step=step):
    #             if self._abort_copy:
    #                 break

    #             percent = int((k + 1) / num_chunk * 100)
    #             QtCore.QMetaObject.invokeMethod( self._progress, "setValue", 
    #                 QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(int, percent))
                
    #         if self._abort_copy and os.path.exists(out_file):
    #             os.remove(out_file)
                
    #         QtCore.QMetaObject.invokeMethod(self, "_copy_BIN_finished", QtCore.Qt.ConnectionType.QueuedConnection)

    #     except:
    #         raise
    #     finally:
    #         self._copy_thread.quit()


#############################################################################################################
def excepthook(exctype, value, tb):
    global mainWin
    if isinstance(value, appError.AppError):
        QMessageBox.critical(mainWin, value.title, str(value))
    else:
        sys.__excepthook__(exctype, value, tb)

if __name__ == '__main__':
    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon('.temp/ustcblue.ico'))
    mainWin = DataAnalyzer()
    mainWin.show()
    app.exec_()
