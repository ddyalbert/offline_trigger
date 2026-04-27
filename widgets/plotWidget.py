from PyQt5.QtWidgets import *
from PyQt5 import uic
from PyQt5 import QtGui, QtCore
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from widgets.UIwidget import MPLwidget, MyPlainTextEdit
from classes.events import EventsTree
import pandas as pd
import numpy as np


class PlotWidget(QWidget):

    is_df: bool = None

    df: pd.DataFrame = None
    tree: EventsTree = None

    x_name: str = None
    y_name: str = None

    _colorbar = None

    def __init__(self):
        super().__init__()
        uic.loadUi('./widgets/plotWidget.ui', self)
        self.setToolTip("")
        for w in self.findChildren(QWidget):
            w:QWidget
            w.setToolTip("")
        self.setFocus()

        self.mpl_widget: MPLwidget
        self.CoB_x: QComboBox
        self.CoB_y: QComboBox
        self.PB_plot: QPushButton
        self.CB_lock: QCheckBox
        self.tabWidget: QTabWidget
        # tab name: [0: Tab_graph, 1: Tab_hist, 2: Tab_hist_2d]

        self.PTE_cut: MyPlainTextEdit
        self.PTE_cut.set_placeholder("Please input cut condition here, for example: \n\nAmp_raw > 0\n1 < DT < 2\ncos(pk_time) < 0.5")
        
        self._init_slider()
        
        self.mpl_widget.clear_axes()
        
        self.tabWidget.currentChanged.connect(self._change_tab)
        self.CB_lock.stateChanged.connect(self._lock_plot)
        self.PB_plot.clicked.connect(self.plot)
        self.CoB_x.currentIndexChanged.connect(self._change_xy_axis)
        self.CoB_y.currentIndexChanged.connect(self._change_xy_axis)

    def _init_slider(self):
        self.Sli_nbin: QSlider
        self.Sli_nbinX: QSlider
        self.Sli_nbinY: QSlider
        self.Sli_point_size: QSlider

        self.SB_nbin: QSlider
        self.SB_nbinX: QSpinBox
        self.SB_nbinY: QSpinBox
        self.SB_point_size: QSpinBox

        self.__pair_slider_spinbox(self.SB_nbin, self.Sli_nbin)
        self.__pair_slider_spinbox(self.SB_nbinX, self.Sli_nbinX)
        self.__pair_slider_spinbox(self.SB_nbinY, self.Sli_nbinY)
        self.__pair_slider_spinbox(self.SB_point_size, self.Sli_point_size)

        self.Sli_nbin.valueChanged.connect(self.plot)
        self.Sli_nbinX.valueChanged.connect(self.plot)
        self.Sli_nbinY.valueChanged.connect(self.plot)
        self.Sli_point_size.valueChanged.connect(self.plot)

    def __pair_slider_spinbox(self, spinbox: QSpinBox, slider: QSlider):
        slider.sliderMoved.connect(spinbox.setValue)
        spinbox.editingFinished.connect(lambda: slider.setValue(spinbox.value()))

        spinbox.setMinimum(slider.minimum())
        spinbox.setMaximum(slider.maximum())
        spinbox.setValue(slider.value())
        spinbox.setSingleStep(slider.singleStep())


    def load_data_df(self, data: pd.DataFrame):
        self.is_df = True
        self.df = data
        self.tree = None
        
        self.CoB_x.clear()
        self.CoB_y.clear()
        self.CoB_x.addItems(self.df.columns)
        self.CoB_y.addItems(self.df.columns)

        if self.x_name is not None and self.x_name in self.df.columns:
            self.CoB_x.setCurrentText(self.x_name)
        else:
            self.CoB_x.setCurrentIndex(0)
        if self.y_name is not None and self.y_name in self.df.columns:
            self.CoB_y.setCurrentText(self.y_name)
        else:
            self.CoB_y.setCurrentIndex(0)

        self._change_xy_axis()
        
    # def load_data_tree(self, data: EventsTree):
    #     self.is_df = False
    #     self.tree = data
    #     self.df = None

    def _change_tab(self):
        if self.tabWidget.currentIndex() == 1:
            self.CoB_y.setEnabled(False)
        else:
            self.CoB_y.setEnabled(True)

    def _lock_plot(self):
        if self.CB_lock.isChecked():
            self.PB_plot.setEnabled(False)
        else:
            self.PB_plot.setEnabled(True)

    def _change_xy_axis(self):
        self.x_name = self.CoB_x.currentText()
        self.y_name = self.CoB_y.currentText()
        

    def plot(self):
        if self._colorbar is not None:
            self._colorbar.remove()
            self._colorbar = None
        if self.is_df is None:
            return

        if self.tabWidget.currentIndex() == 0:
            self.__plot_graph()
        elif self.tabWidget.currentIndex() == 1:
            self.__plot_hist()
        elif self.tabWidget.currentIndex() == 2:
            self.__plot_hist_2d()

    def __plot_graph(self):

        x_data = self.df[self.x_name]
        y_data = self.df[self.y_name]

        self.mpl_widget.clear_axes()
        self.mpl_widget.axes.plot(x_data, y_data, marker="o", linestyle="None", 
            markersize=self.Sli_point_size.value())
        self.mpl_widget.axes.set_xlabel(self.x_name)
        self.mpl_widget.axes.set_ylabel(self.y_name)
        self.mpl_widget.after_draw()
        
    def __plot_hist(self):

        x_data = self.df[self.x_name]

        self.mpl_widget.clear_axes()
        self.mpl_widget.axes.hist(x_data, bins=self.Sli_nbin.value(), color="blue", edgecolor="black")
        self.mpl_widget.axes.set_xlabel(self.x_name)
        self.mpl_widget.after_draw()
        
    def __plot_hist_2d(self):

        x_data = self.df[self.x_name]
        y_data = self.df[self.y_name]

        self.mpl_widget.clear_axes()
        hist = self.mpl_widget.axes.hist2d(x_data, y_data, 
            bins=(self.Sli_nbinX.value(), self.Sli_nbinY.value()), cmap="Blues")
        self._colorbar = self.mpl_widget.fig.colorbar(hist[3], ax=self.mpl_widget.axes)
        self.mpl_widget.axes.set_xlabel(self.x_name)
        self.mpl_widget.axes.set_ylabel(self.y_name)
        self.mpl_widget.after_draw()
        
        
    
if __name__ == '__main__':

    app = QApplication(sys.argv)
    mainWin = PlotWidget()
    
    x = np.random.normal(0, 1, 100)
    df = pd.DataFrame({'x': x, 'y': 2 * x + 1})   
    mainWin.load_data_df(df)

    mainWin.show()
    app.exec_()