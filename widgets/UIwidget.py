from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backend_bases import PickEvent, MouseEvent
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtWidgets

from typing import Dict
from pathlib import Path

import sys
import re
import numpy as np
import pandas as pd


# ---------------------------------------------------------------
# MPLwidget -----------------------------------------------------
# ---------------------------------------------------------------

class  MPLwidget(QtWidgets.QWidget):  
    
    def  __init__(self, parent = None): 
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

        self.fig = Figure()
        self.axes = self.fig.add_subplot(111)
        self.axes.grid(True)
        self.fig.tight_layout()
        self.canvas: QtWidgets.QWidget | FigureCanvas
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setMinimumSize(600, 350)
        self.canvas.draw()

        self.bar_widget = QtWidgets.QWidget(self)
        self.bar_widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        self.statusbar = QtWidgets.QLabel("| Ready!", self.bar_widget)
        self.statusbar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        self.statusbar.hide()

        self.toolbar:QtWidgets.QToolBar | NavigationToolbar
        self.toolbar = NavigationToolbar(self.canvas, self.bar_widget)
        self.toolbar.setIconSize(QtCore.QSize(20,20))
        self.toolbar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)

        self.bar_layout = QtWidgets.QHBoxLayout(self.bar_widget)
        self.bar_layout.setContentsMargins(10, 0, 10, 0)
        self.bar_layout.addWidget(self.toolbar)
        self.bar_layout.addWidget(self.statusbar)

        self.vlayout = QtWidgets.QVBoxLayout(self)
        self.vlayout.setContentsMargins(0, 0, 0, 0)
        self.vlayout.addWidget(self.bar_widget)
        self.vlayout.addWidget(self.canvas)

        self._picked = False
        self.canvas.mpl_connect("pick_event", self.on_pick)
        self.canvas.mpl_connect("button_press_event", self.on_click)

    def clear_axes(self):
        self.axes.clear()
        self.axes.grid(True)

    def after_draw(self):
        self.fig.tight_layout()
        self.toolbar.update()
        self.toolbar.push_current()
        self.canvas.draw()
        
    def set_message(self, text: str):
        self.statusbar.setText(f"| {text}")
        self.statusbar.show()
    
    def clear_message(self):
        self.statusbar.setText("| Ready!")
        self.statusbar.hide()

    # 显示图像信息 ----------
    def on_pick(self, event: PickEvent):
        """点中某个图形"""
        self._picked = True
        artist = event.artist

        if hasattr(artist, "get_label"):
            label = artist.get_label()
        else:
            label = artist.__class__.__name__

        self.set_message(f"{label}")

    def on_click(self, _ ):
        """点击空白处"""
        if not self._picked:
            self.clear_message()
        self._picked = False

# ----------------------------------------------------------------
# ObjectBrowserDialog --------------------------------------------
# ----------------------------------------------------------------

class ObjectBrowserDialog(QtWidgets.QDialog):
    def __init__(self, obj, parent=None):
        super().__init__(parent)

        self.obj = obj
        self.setModal(False)
        self.resize(900, 1000)
        self.setWindowTitle("Object Browser")

        layout = QtWidgets.QVBoxLayout(self)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type", "Memory", "Value"])
        self.tree.setSortingEnabled(True)

        self.tree.setAnimated(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)  

        self.btn_refresh = QtWidgets.QToolButton()
        self.btn_refresh.setText("Refresh")
        self.btn_refresh.clicked.connect(self.populate_tree)

        layout.addWidget(self.btn_refresh)
        layout.addWidget(self.tree)

        self._visited: Dict[int, tuple[int, QtWidgets.QTreeWidgetItem]] = {}
        self.populate_tree()

        header = self.tree.header()

        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # Name
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # Memory
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # Value

    def populate_tree(self):
        self.tree.clear()
        self._visited = {}
        self._add_children(self.tree, self.obj, key="root", depth=0, max_depth=5)
        self._fill_memory()
        self.tree.sortItems(0, QtCore.Qt.SortOrder.AscendingOrder)


    def _add_children(self, parent_item, obj, key, depth=0, max_depth=5):

        if depth > max_depth:
            return
        if isinstance(obj, QtCore.QObject) and depth != 0:
            return
        if re.fullmatch(r"_\S+_cut", key):
            return
        
        # 处理此项 ----------
        item_type = type(obj).__name__
        item_name = ObjectBrowserDialog._short_repr(obj)

        is_has_child = True
        if isinstance(obj, np.ndarray):
            item_type = f"np.ndarray({obj.size}, {obj.dtype})"
            is_has_child = False
        if isinstance(obj, pd.DataFrame):
            item_type = f"pd.DataFrame({obj.shape[0]}, {obj.shape[1]})"
            item_name = ObjectBrowserDialog._short_repr(f"DataFrame({obj.columns.tolist()})")
        if isinstance(obj, pd.Series):
            item_type = f"pd.Series({obj.shape[0]}, {obj.dtype})"
            item_name = ObjectBrowserDialog._short_repr(f"Series({obj.tolist()})")
            is_has_child = False
        if isinstance(obj, pd.Index):
            item_type = f"pd.Index({obj.size})"
            is_has_child = False
        if isinstance(obj, (int, float, complex, bool, str, bytes, bytearray, type(None))) :
            is_has_child = False
        

        root_item = QtWidgets.QTreeWidgetItem(parent_item, [key, item_type, "", item_name])
        setattr(root_item, "_obj_ref", obj)
        
        if depth == 0:
            root_item.setExpanded(True)

        # 避免重复添加
        obj_id = id(obj)
        if obj_id in self._visited:
            if self._visited[obj_id][0] <= depth:
                return 0 
            self._visited[obj_id][1].takeChildren()
        self._visited[obj_id] = (depth, root_item)


        # 递归添加子项
        if not is_has_child:
            return
        try:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    self._add_children(root_item, v, repr(k), depth=depth + 1)
            elif isinstance(obj, (list, tuple)):
                for i, v in enumerate(obj):
                    self._add_children(root_item, v, f"[{i}]", depth=depth + 1)
            elif isinstance(obj, pd.DataFrame):
                self._add_children(root_item, obj.index, "index", depth=depth + 1)
                for col in obj.columns:
                    self._add_children(root_item, obj[col], col, depth=depth + 1)
            elif hasattr(obj, "__dict__"):
                for name, v in vars(obj).items():
                    self._add_children(root_item, v, name, depth=depth + 1)

        except Exception as e:
            QtWidgets.QTreeWidgetItem(parent_item,["<error>", "Exception", str(e)])
        
    
    def _fill_memory(self):
        def memory_of_value(obj):
            try:
                if isinstance(obj, np.ndarray):
                    return obj.nbytes
                if isinstance(obj, np.generic):  # numpy scalar
                    return obj.itemsize
                if isinstance(obj, pd.Series) or isinstance(obj, pd.Index):
                    return int(obj.memory_usage(deep=True))
                if isinstance(obj, pd.DataFrame):
                    return int(obj.memory_usage(deep=True).sum())
                if obj is None:
                    return 0
                return sys.getsizeof(obj)
            except Exception:
                return 0
            
        def format_bytes(n: int) -> str:
            for unit in ["B", "KB", "MB", "GB"]:
                if n < 1024:
                    return f"{n:.2f} {unit}"
                n /= 1024
            return f"{n:.2f} TB"

        def recursive_fill(item: QtWidgets.QTreeWidgetItem):
            obj = getattr(item, "_obj_ref", None)
            if item.childCount() == 0:
                mem = memory_of_value(obj)
            else:
                mem = 0
                for i in range(item.childCount()):
                    mem += recursive_fill(item.child(i))
            item.setText(2, format_bytes(mem))
            return mem

        root_count = self.tree.topLevelItemCount()
        for i in range(root_count):
            recursive_fill(self.tree.topLevelItem(i))
        
    @staticmethod
    def _short_repr(obj, max_len=80) -> str:
        if isinstance(obj, str):
            r = obj
        else:
            r = repr(obj)
        return r if len(r) <= max_len else r[:max_len] + "..."


# ----------------------------------------------------------------
# StatusBarWithProgress ------------------------------------------
# ----------------------------------------------------------------

class StatusBarWithProgress(QtWidgets.QStatusBar):
    _text_type: str = ""
    _repeat_num: int = 0
    def __init__(self, parent=None):
        super().__init__(parent)

        # 标签容器
        self._container_label = QtWidgets.QWidget(self)

        self._hlayout_label = QtWidgets.QHBoxLayout(self._container_label)
        self._hlayout_label.setContentsMargins(0, 0, 0, 0)

        self._label = QtWidgets.QLabel("Data Analysis Ready!")
        self._label.setMinimumWidth(200)

        self._spacer_label = QtWidgets.QSpacerItem(5,0)

        self._hlayout_label.addSpacerItem(self._spacer_label)
        self._hlayout_label.addWidget(self._label)

        self.addPermanentWidget(self._container_label, 1)

        # 进度条容器
        self._container_progress = QtWidgets.QWidget(self)
        self._container_progress.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

        self._hlayout_progress = QtWidgets.QHBoxLayout(self._container_progress)
        self._hlayout_progress.setContentsMargins(0, 0, 0, 0)

        self._progress = QtWidgets.QProgressBar()
        self._progress.setFixedWidth(120)
        self._progress.setFixedHeight(15)
        self._progress.setTextVisible(True)

        self._spacer_progress = QtWidgets.QSpacerItem(5,0)

        self._hlayout_progress.addWidget(self._progress)
        self._hlayout_progress.addSpacerItem(self._spacer_progress)

        self._progress.hide()

        self.addPermanentWidget(self._container_progress)

    # ========= 进度条相关 =========
    def set_text(self, text: str, type_str: str = None):
        if type_str is None:
            self._text_type = ""
            self._repeat_num = 0
        elif type_str == self._text_type:
            self._repeat_num += 1
        else:
            self._repeat_num = 0
            self._text_type = type_str  

        if self._repeat_num > 0:
            text = f" {self._repeat_num} | {text}"

        self._label.setText(text)

    def start(self, text: str = "Processing...", minimum=0, maximum=100):
        self._progress.setRange(minimum, maximum)
        self._progress.setValue(minimum)
        self._progress.show()
        self.set_text(text)
        QtWidgets.QApplication.processEvents()

    def set_value(self, value: int):
        self._progress.setValue(value)

    def finish(self, text: str = "Done"):
        self._progress.hide()
        self.set_text(text)

# ----------------------------------------------------------------
# FileComboBox ---------------------------------------------------
# ----------------------------------------------------------------

class FileComboBox(QtWidgets.QComboBox):
    
    fileChanged = QtCore.pyqtSignal(str)  # 发出选中文件路径

    def __init__(self, parent=None):
        super().__init__(parent)

        self._folder = ""
        self._suffix = ""

        self.currentIndexChanged.connect(self._emit_file_changed)

    def setFolder(self, folder: str, suffix: str = ".json"):
        self._folder = Path(folder)
        self._suffix = suffix

    def showPopup(self):
        self._refresh_files()
        super().showPopup()

    # ---------- 内部方法 ----------
    def _refresh_files(self):
        self.clear()
        try:
            self._folder.mkdir(exist_ok=True)
        except:
            self.addItem("No this Folder")
            self.setItemData(0, 0 , QtCore.Qt.ItemDataRole.UserRole - 1)
            return

        files = self._folder.iterdir()

        if self._suffix == "":
            files = [f for f in files if f.is_file()]
        else:
            files = [f for f in files if f.is_file() and f.suffix == self._suffix]

        if not files:
            self.addItem("No this File")
            self.setItemData(0, 0 , QtCore.Qt.ItemDataRole.UserRole - 1)
            return

        for f in sorted(files):
            self.addItem(f.name, str(f))

    def _emit_file_changed(self, index):
        path = self.itemData(index)
        if path:
            self.fileChanged.emit(path)
        else:
            self.fileChanged.emit("")


class MyPlainTextEdit(QtWidgets.QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.placeholder = "第一行提示\n第二行提示\n第三行提示"

        # self._show_placeholder()

        QtCore.QTimer.singleShot(0, self._show_placeholder)

    def set_placeholder(self, placeholder: str):
        self.placeholder = placeholder
        self._show_placeholder()

    def _show_placeholder(self):
        self.setPlainText(self.placeholder)
        self.setStyleSheet("color: gray;")
        self._is_placeholder = True

    def focusInEvent(self, event):
        super().focusInEvent(event)

        if self._is_placeholder:
            self.clear()
            self.setStyleSheet("color: black;")
            self._is_placeholder = False

    def focusOutEvent(self, event):
        super().focusOutEvent(event)

        if not self.toPlainText().strip():
            self._show_placeholder()