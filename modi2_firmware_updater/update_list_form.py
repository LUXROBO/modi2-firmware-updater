import os

from PyQt5 import QtGui, uic
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QDialog

from modi2_firmware_updater.util.platform_util import is_raspberrypi


class ESP32UpdateListForm(QDialog):
    network_state_signal = pyqtSignal(int, int)
    network_uuid_signal = pyqtSignal(int, str)
    progress_signal = pyqtSignal(int, int)
    total_progress_signal = pyqtSignal(int)
    total_status_signal = pyqtSignal(str)
    error_message_signal = pyqtSignal(int, str)

    def __init__(self, path_dict = {}):
        QDialog.__init__(self)

        self.component_path = path_dict["component"]
        self.ui = uic.loadUi(path_dict["ui"])
        self.ui.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))
        self.ui.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.ui.setWindowFlag(Qt.WindowMaximizeButtonHint, True)

        self.ui_icon_list = [
            self.ui.image_1,
            self.ui.image_2,
            self.ui.image_3,
            self.ui.image_4,
            self.ui.image_5,
            self.ui.image_6,
            self.ui.image_7,
            self.ui.image_8,
            self.ui.image_9,
            self.ui.image_10
        ]

        self.ui_network_id_list = [
            self.ui.network_id_1,
            self.ui.network_id_2,
            self.ui.network_id_3,
            self.ui.network_id_4,
            self.ui.network_id_5,
            self.ui.network_id_6,
            self.ui.network_id_7,
            self.ui.network_id_8,
            self.ui.network_id_9,
            self.ui.network_id_10,
        ]

        self.ui_progress_list = [
            self.ui.progress_bar_1,
            self.ui.progress_bar_2,
            self.ui.progress_bar_3,
            self.ui.progress_bar_4,
            self.ui.progress_bar_5,
            self.ui.progress_bar_6,
            self.ui.progress_bar_7,
            self.ui.progress_bar_8,
            self.ui.progress_bar_9,
            self.ui.progress_bar_10,
        ]

        self.ui_progress_value_list = [
            self.ui.progress_value_1,
            self.ui.progress_value_2,
            self.ui.progress_value_3,
            self.ui.progress_value_4,
            self.ui.progress_value_5,
            self.ui.progress_value_6,
            self.ui.progress_value_7,
            self.ui.progress_value_8,
            self.ui.progress_value_9,
            self.ui.progress_value_10,
        ]

        self.ui_error_message_list = [
            self.ui.error_message_1,
            self.ui.error_message_2,
            self.ui.error_message_3,
            self.ui.error_message_4,
            self.ui.error_message_5,
            self.ui.error_message_6,
            self.ui.error_message_7,
            self.ui.error_message_8,
            self.ui.error_message_9,
            self.ui.error_message_10,
        ]

        self.ui.close_button.clicked.connect(self.ui.close)

        self.network_state_signal.connect(self.set_network_state)
        self.network_uuid_signal.connect(self.set_network_uuid)
        self.progress_signal.connect(self.progress_value_changed)
        self.total_progress_signal.connect(self.total_progress_value_changed)
        self.total_status_signal.connect(self.total_progress_status_changed)
        self.error_message_signal.connect(self.set_error_message)

        self.device_num = 0
        self.device_max_num = 10

        if is_raspberrypi():
            for i in range(0, 10):
                font = self.ui_progress_value_list[i].font()
                font.setPointSize(9)
                self.ui_progress_list[i].setFixedWidth(80)
                self.ui_progress_value_list[i].setFont(font)
                self.ui_error_message_list[i].setFont(font)
                self.ui_network_id_list[i].setFont(font)

    def reset_device_list(self):
        self.device_num = 0
        self.ui.progress_bar_total.setValue(0)
        self.ui.total_status.setText("")

        for i in range(0, 10):
            icon_path = os.path.join(self.component_path, "modules", "network_none.png")
            pixmap = QtGui.QPixmap()
            pixmap.load(icon_path)

            self.ui_icon_list[i].setPixmap(pixmap)
            self.ui_progress_list[i].setValue(0)
            self.ui_progress_value_list[i].setText("0%")
            self.ui_error_message_list[i].setText("")
            self.ui_network_id_list[i].setText("not connected")

    def set_device_num(self, num):
        self.reset_device_list()
        self.device_num = num
        for i in range(0, self.device_num):
            icon_path = os.path.join(self.component_path, "modules", "network.png")
            pixmap = QtGui.QPixmap()
            pixmap.load(icon_path)
            self.ui_icon_list[i].setPixmap(pixmap)

    def set_network_state(self, index, state):
        if index > self.device_num - 1:
            return

        pixmap = QtGui.QPixmap()
        if state == -1:
            icon_path = os.path.join(self.component_path, "modules", "network_error.png")
            pixmap.load(icon_path)
        elif state == 0:
            icon_path = os.path.join(self.component_path, "modules", "network.png")
            pixmap.load(icon_path)
        else:
            icon_path = os.path.join(self.component_path, "modules", "network_reconnect.png")
            pixmap.load(icon_path)

        self.ui_icon_list[index].setPixmap(pixmap)

    def set_network_uuid(self, index, str):
        if index > self.device_num - 1:
            return

        self.ui_network_id_list[index].setText(str)

    def progress_value_changed(self, index, value):
        if index > self.device_num - 1:
            return

        self.ui_progress_list[index].setValue(value)
        self.ui_progress_list[index].repaint()
        self.ui_progress_value_list[index].setText(str(value) + "%")

    def total_progress_value_changed(self, value):
        self.ui.progress_bar_total.setValue(value)
        self.ui.progress_bar_total.repaint()

    def total_progress_status_changed(self, status):
        self.ui.total_status.setText(status)

    def set_error_message(self, index, error_message):
        if index > self.device_num - 1:
            return

        self.ui_error_message_list[index].setText(error_message)


class ModuleUpdateListForm(QDialog):
    network_state_signal = pyqtSignal(int, int)
    network_uuid_signal = pyqtSignal(int, str)
    current_module_changed_signal = pyqtSignal(int, str)
    progress_signal = pyqtSignal(int, int, int)
    total_progress_signal = pyqtSignal(int)
    total_status_signal = pyqtSignal(str)
    error_message_signal = pyqtSignal(int, str)

    def __init__(self, path_dict = {}):
        QDialog.__init__(self)

        self.component_path = path_dict["component"]
        self.ui = uic.loadUi(path_dict["ui"])
        self.ui.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))

        self.ui_icon_list = [
            self.ui.image_1,
            self.ui.image_2,
            self.ui.image_3,
            self.ui.image_4,
            self.ui.image_5,
            self.ui.image_6,
            self.ui.image_7,
            self.ui.image_8,
            self.ui.image_9,
            self.ui.image_10
        ]

        self.ui_current_icon_list = [
            self.ui.image_current_1,
            self.ui.image_current_2,
            self.ui.image_current_3,
            self.ui.image_current_4,
            self.ui.image_current_5,
            self.ui.image_current_6,
            self.ui.image_current_7,
            self.ui.image_current_8,
            self.ui.image_current_9,
            self.ui.image_current_10,
        ]

        self.ui_network_id_list = [
            self.ui.network_id_1,
            self.ui.network_id_2,
            self.ui.network_id_3,
            self.ui.network_id_4,
            self.ui.network_id_5,
            self.ui.network_id_6,
            self.ui.network_id_7,
            self.ui.network_id_8,
            self.ui.network_id_9,
            self.ui.network_id_10,
        ]

        self.ui_current_progress_list = [
            self.ui.progress_bar_current_1,
            self.ui.progress_bar_current_2,
            self.ui.progress_bar_current_3,
            self.ui.progress_bar_current_4,
            self.ui.progress_bar_current_5,
            self.ui.progress_bar_current_6,
            self.ui.progress_bar_current_7,
            self.ui.progress_bar_current_8,
            self.ui.progress_bar_current_9,
            self.ui.progress_bar_current_10,
        ]

        self.ui_total_progress_list = [
            self.ui.progress_bar_total_1,
            self.ui.progress_bar_total_2,
            self.ui.progress_bar_total_3,
            self.ui.progress_bar_total_4,
            self.ui.progress_bar_total_5,
            self.ui.progress_bar_total_6,
            self.ui.progress_bar_total_7,
            self.ui.progress_bar_total_8,
            self.ui.progress_bar_total_9,
            self.ui.progress_bar_total_10,
        ]

        self.ui_current_progress_value_list = [
            self.ui.progress_current_value_1,
            self.ui.progress_current_value_2,
            self.ui.progress_current_value_3,
            self.ui.progress_current_value_4,
            self.ui.progress_current_value_5,
            self.ui.progress_current_value_6,
            self.ui.progress_current_value_7,
            self.ui.progress_current_value_8,
            self.ui.progress_current_value_9,
            self.ui.progress_current_value_10,
        ]

        self.ui_total_progress_value_list = [
            self.ui.progress_total_value_1,
            self.ui.progress_total_value_2,
            self.ui.progress_total_value_3,
            self.ui.progress_total_value_4,
            self.ui.progress_total_value_5,
            self.ui.progress_total_value_6,
            self.ui.progress_total_value_7,
            self.ui.progress_total_value_8,
            self.ui.progress_total_value_9,
            self.ui.progress_total_value_10,
        ]

        self.ui_error_message_list = [
            self.ui.error_message_1,
            self.ui.error_message_2,
            self.ui.error_message_3,
            self.ui.error_message_4,
            self.ui.error_message_5,
            self.ui.error_message_6,
            self.ui.error_message_7,
            self.ui.error_message_8,
            self.ui.error_message_9,
            self.ui.error_message_10,
        ]

        self.ui.close_button.clicked.connect(self.ui.close)

        self.network_state_signal.connect(self.set_network_state)
        self.network_uuid_signal.connect(self.set_network_uuid)
        self.current_module_changed_signal.connect(self.current_module_changed)
        self.progress_signal.connect(self.progress_value_changed)
        self.total_progress_signal.connect(self.total_progress_value_changed)
        self.total_status_signal.connect(self.total_progress_status_changed)
        self.error_message_signal.connect(self.set_error_message)

        self.device_num = 0
        self.device_max_num = 10

        if is_raspberrypi():
            for i in range(0, 10):
                font = self.ui_current_progress_list[i].font()
                font.setPointSize(9)
                self.ui_current_progress_list[i].setFixedWidth(80)
                self.ui_total_progress_list[i].setFixedWidth(80)
                self.ui_current_progress_value_list[i].setFont(font)
                self.ui_total_progress_value_list[i].setFont(font)
                self.ui_error_message_list[i].setFont(font)
                self.ui_network_id_list[i].setFont(font)

    def reset_device_list(self):
        self.device_num = 0
        self.ui.progress_bar_total.setValue(0)
        self.ui.total_status.setText("")

        for i in range(0, 10):
            if is_raspberrypi():
                icon_path = os.path.join(self.component_path, "modules", "network_none_28.png")
            else:
                icon_path = os.path.join(self.component_path, "modules", "network_none.png")

            icon_pixmap = QtGui.QPixmap()
            icon_pixmap.load(icon_path)
            self.ui_icon_list[i].setPixmap(icon_pixmap)

            current_icon_path = os.path.join(self.component_path, "modules", "network_none_28.png")
            current_icon_pixmap = QtGui.QPixmap()
            current_icon_pixmap.load(current_icon_path)
            self.ui_current_icon_list[i].setPixmap(current_icon_pixmap)

            self.ui_current_progress_list[i].setValue(0)
            self.ui_total_progress_list[i].setValue(0)
            self.ui_current_progress_value_list[i].setText("0%")
            self.ui_total_progress_value_list[i].setText("0%")
            self.ui_error_message_list[i].setText("")
            self.ui_network_id_list[i].setText("not connected")

    def set_device_num(self, num):
        self.reset_device_list()
        self.device_num = num
        for i in range(0, self.device_num):
            if is_raspberrypi():
                icon_path = os.path.join(self.component_path, "modules", "network_28.png")
            else:
                icon_path = os.path.join(self.component_path, "modules", "network.png")

            pixmap = QtGui.QPixmap()
            pixmap.load(icon_path)
            self.ui_icon_list[i].setPixmap(pixmap)

    def set_network_state(self, index, state):
        if index > self.device_num - 1:
            return

        pixmap = QtGui.QPixmap()
        if state == -1:
            if is_raspberrypi():
                icon_path = os.path.join(self.component_path, "modules", "network_none_28.png")
            else:
                icon_path = os.path.join(self.component_path, "modules", "network_error.png")
            pixmap.load(icon_path)
        elif state == 0:
            if is_raspberrypi():
                icon_path = os.path.join(self.component_path, "modules", "network_28.png")
            else:
                icon_path = os.path.join(self.component_path, "modules", "network.png")
            pixmap.load(icon_path)
        elif state == 1:
            if is_raspberrypi():
                icon_path = os.path.join(self.component_path, "modules", "network_none_28.png")
            else:
                icon_path = os.path.join(self.component_path, "modules", "network_disconnect.png")
            pixmap.load(icon_path)
        elif state == 2:
            if is_raspberrypi():
                icon_path = os.path.join(self.component_path, "modules", "network_none_28.png")
            else:
                icon_path = os.path.join(self.component_path, "modules", "network_reconnect.png")
            pixmap.load(icon_path)

        self.ui_icon_list[index].setPixmap(pixmap)

    def set_network_uuid(self, index, str):
        if index > self.device_num - 1:
            return

        self.ui_network_id_list[index].setText(str)

    def current_module_changed(self, index, module_type):
        if index > self.device_num - 1:
            return

        if module_type:
            icon_path = os.path.join(self.component_path, "modules", module_type + "_28.png")
            pixmap = QtGui.QPixmap()
            pixmap.load(icon_path)
            self.ui_current_icon_list[index].setPixmap(pixmap)

    def progress_value_changed(self, index, current, total):
        if index > self.device_num - 1:
            return

        self.ui_current_progress_list[index].setValue(current)
        self.ui_current_progress_list[index].repaint()
        self.ui_current_progress_value_list[index].setText(str(current) + "%")
        self.ui_total_progress_list[index].setValue(total)
        self.ui_total_progress_list[index].repaint()
        self.ui_total_progress_value_list[index].setText(str(total) + "%")

    def total_progress_value_changed(self, value):
        self.ui.progress_bar_total.setValue(value)
        self.ui.progress_bar_total.repaint()

    def total_progress_status_changed(self, status):
        self.ui.total_status.setText(status)

    def set_error_message(self, index, error_message):
        if index > self.device_num - 1:
            return

        self.ui_error_message_list[index].setText(error_message)
