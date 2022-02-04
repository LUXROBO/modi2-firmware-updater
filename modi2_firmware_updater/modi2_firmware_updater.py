import os
import io
import sys
import time
import pathlib
import threading as th
import traceback as tb

from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QDialog, QMessageBox

from modi2_firmware_updater.firmware_manager import FirmwareManagerForm
from modi2_firmware_updater.update_list_form import ESP32UpdateListForm, ModuleUpdateListForm
from modi2_firmware_updater.core.esp32_updater import ESP32FirmwareMultiUploder
from modi2_firmware_updater.core.module_updater import ModuleFirmwareMultiUpdater
from modi2_firmware_updater.core.network_updater import NetworkFirmwareMultiUpdater
from modi2_firmware_updater.util.modi_winusb.modi_serialport import list_modi_serialports
from modi2_firmware_updater.util.platform_util import is_raspberrypi, set_delay_option

class StdoutRedirect(QObject):
    printOccur = pyqtSignal(str, str, name="print")

    def __init__(self):
        QObject.__init__(self, None)
        self.daemon = True
        self.sysstdout = sys.stdout.write
        self.sysstderr = sys.stderr.write

    def stop(self):
        sys.stdout.write = self.sysstdout
        sys.stderr.write = self.sysstderr

    def start(self):
        sys.stdout.write = self.write
        sys.stderr.write = lambda msg: self.write(msg, color="red")

    def write(self, s, color="black"):
        sys.stdout.flush()
        self.printOccur.emit(s, color)

class PopupMessageBox(QtWidgets.QMessageBox):
    def __init__(self, main_window, level):
        QtWidgets.QMessageBox.__init__(self)
        self.window = main_window
        self.setSizeGripEnabled(True)
        self.setWindowTitle("System Message")

        def error_popup():
            self.setIcon(self.Icon.Warning)
            self.setText("ERROR")

        def warning_popup():
            self.setIcon(self.Icon.Information)
            self.setText("WARNING")
            self.addButton("Ok", self.ActionRole)

        func = {
            "error": error_popup,
            "warning": warning_popup,
        }.get(level)
        func()

        close_btn = self.addButton("Exit", self.ActionRole)
        close_btn.clicked.connect(self.close_btn)
        self.show()

    def event(self, e):
        MAXSIZE = 16_777_215
        MINHEIGHT = 100
        MINWIDTH = 200
        MINWIDTH_CHANGE = 500
        result = QtWidgets.QMessageBox.event(self, e)

        self.setMinimumHeight(MINHEIGHT)
        self.setMaximumHeight(MAXSIZE)
        self.setMinimumWidth(MINWIDTH)
        self.setMaximumWidth(MAXSIZE)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

        textEdit = self.findChild(QtWidgets.QTextEdit)
        if textEdit is not None:
            textEdit.setMinimumHeight(MINHEIGHT)
            textEdit.setMaximumHeight(MAXSIZE)
            textEdit.setMinimumWidth(MINWIDTH_CHANGE)
            textEdit.setMaximumWidth(MAXSIZE)
            textEdit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding,)

        return result

    def close_btn(self):
        self.window.close()


class ThreadSignal(QObject):
    thread_error = pyqtSignal(object)
    thread_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()

class Form(QDialog):
    """
    GUI Form of MODI+ Firmware Updater
    """

    def __init__(self, debug=False, multi=True):
        QDialog.__init__(self)
        self.__excepthook = sys.excepthook
        sys.excepthook = self.__popup_excepthook
        th.excepthook = self.__popup_thread_excepthook
        self.err_list = list()
        self.is_popup = False
        self.is_debug = debug
        self.is_multi = multi

        ui_path = os.path.join(os.path.dirname(__file__), "assets", "main.ui")
        firmware_manager_ui_path = os.path.join(os.path.dirname(__file__), "assets", "firmware_manager.ui")
        esp32_update_list_ui_path = os.path.join(os.path.dirname(__file__), "assets", "esp32_update_list.ui")
        module_update_list_ui_path = os.path.join(os.path.dirname(__file__), "assets", "module_update_list.ui")
        if sys.platform.startswith("win"):
            self.component_path = pathlib.PurePosixPath(pathlib.PurePath(__file__), "..", "assets", "component")
        else:
            self.component_path = os.path.join(os.path.dirname(__file__), "assets", "component")
        self.ui = uic.loadUi(ui_path)
        self.assets_firmware_path = os.path.join(os.path.dirname(__file__), "assets", "firmware")
        self.local_firmware_path = os.path.join(os.path.expanduser("~"), "Documents", "modi+ firmware updater")
        self.module_firmware_directory = "module_firmware"
        self.module_firmware_path = os.path.join(self.local_firmware_path, self.module_firmware_directory)

        self.ui.setStyleSheet("background-color: white")

        # Set LUXROBO logo image
        logo_path = os.path.join(self.component_path, "luxrobo_logo.png")
        qPixmapVar = QtGui.QPixmap()
        qPixmapVar.load(logo_path)
        self.ui.lux_logo.setPixmap(qPixmapVar)

        self.firmware_manage_form = FirmwareManagerForm(path_dict={
            "ui": firmware_manager_ui_path,
            "component": self.component_path,
            "assets_firmware": self.assets_firmware_path,
            "local_firmware": self.local_firmware_path,
            "firmware_directory": self.module_firmware_directory
        })
        self.esp32_update_list_form = ESP32UpdateListForm(path_dict={
            "ui": esp32_update_list_ui_path,
            "component": self.component_path,
        })
        self.module_update_list_form = ModuleUpdateListForm(path_dict={
            "ui": module_update_list_ui_path,
            "component": self.component_path,
        })

        # Buttons image
        self.active_path = pathlib.PurePosixPath(self.component_path, "btn_frame_active.png")
        self.inactive_path = pathlib.PurePosixPath(self.component_path, "btn_frame_inactive.png")
        self.pressed_path = pathlib.PurePosixPath(self.component_path, "btn_frame_pressed.png")
        self.language_frame_path = pathlib.PurePosixPath(self.component_path, "lang_frame.png")
        self.language_frame_pressed_path = pathlib.PurePosixPath(self.component_path, "lang_frame_pressed.png")

        self.ui.update_network_module_button.setStyleSheet(f"border-image: url({self.active_path})")
        self.ui.update_network_submodule_button.setStyleSheet(f"border-image: url({self.active_path})")
        self.ui.delete_user_code_button.setStyleSheet(f"border-image: url({self.active_path})")
        self.ui.update_general_modules_button.setStyleSheet(f"border-image: url({self.active_path})")
        self.ui.manage_firmware_version_button.setStyleSheet(f"border-image: url({self.active_path})")
        self.ui.translate_button.setStyleSheet(f"border-image: url({self.language_frame_path})")
        self.ui.devmode_button.setStyleSheet(f"border-image: url({self.language_frame_path})")

        version_path = os.path.join(os.path.dirname(__file__), "..", "version.txt")
        with io.open(version_path, "r") as version_file:
            self.version_info = version_file.readline().rstrip("\n")

        if self.is_multi:
            self.ui.setWindowTitle("MODI+ Firmware Multi Updater - " + self.version_info)
        else:
            self.ui.setWindowTitle("MODI+ Firmware Updater - " + self.version_info)

        self.ui.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))
        self.ui.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.ui.setWindowFlag(Qt.WindowMaximizeButtonHint, True)

        # Redirect stdout to text browser (i.e. console in our UI)
        if not self.is_debug:
            self.stdout = StdoutRedirect()
            self.stdout.start()
            self.stdout.printOccur.connect(lambda line: self.__append_text_line(line))

        # Set signal for thread communication
        self.stream = ThreadSignal()

        # Connect up the buttons
        self.ui.update_network_module_button.clicked.connect(self.update_network_module_button_clicked)
        self.ui.update_network_submodule_button.clicked.connect(self.update_network_submodule_button_clicked)
        self.ui.delete_user_code_button.clicked.connect(self.delete_user_code_button_clicked)
        self.ui.update_general_modules_button.clicked.connect(self.update_general_modules_button_clicked)
        self.ui.manage_firmware_version_button.clicked.connect(self.manage_firmware_version_button_clicked)
        self.ui.devmode_button.clicked.connect(self.devmode_button_clicked)
        self.ui.translate_button.clicked.connect(self.translate_button_clicked)

        self.buttons = [
            self.ui.update_network_module_button,
            self.ui.update_network_submodule_button,
            self.ui.delete_user_code_button,
            self.ui.update_general_modules_button,
            self.ui.manage_firmware_version_button,
            self.ui.devmode_button,
            self.ui.translate_button,
        ]

        self.button_en = [
            "Update Network Module",
            "Update Network Submodule",
            "Delete User Code",
            "Update General Modules",
            "Manage Module Firmware Version",
            "Show Detail",
            "한국어",
        ]

        self.button_kr = [
            "네트워크 모듈 업데이트",
            "네트워크 서브 모듈 업데이트",
            "시용자 코드 삭제",
            "일반 모듈 업데이트",
            "펌웨어 관리",
            "자세히 보기",
            "English",
        ]

        # Disable the first button to be focused when UI is loaded
        self.ui.update_network_module_button.setAutoDefault(False)
        self.ui.update_network_module_button.setDefault(False)

        # Set up field variables
        self.firmware_updater = None
        self.button_in_english = False
        self.console = False

        # Set up ui field variables
        self.ui.is_english = False
        self.ui.active_path = self.active_path
        self.ui.pressed_path = self.pressed_path
        self.ui.language_frame_path = self.language_frame_path
        self.ui.language_frame_pressed_path = self.language_frame_pressed_path
        self.ui.stream = self.stream

        # check module firmware
        self.check_module_firmware()

        # Set Button Status
        self.refresh_button_text()
        self.refresh_console()

        # Set delay option
        delay_option = (self.is_multi==True)
        set_delay_option(delay_option)

        # check app update
        self.check_app_update()

        if is_raspberrypi():
            self.ui.setMinimumSize(0, 0)
            self.ui.setWindowState(Qt.WindowMaximized)

        self.ui.show()

    #
    # Main methods
    #
    def update_network_module_button_clicked(self):
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            if self.is_multi:
                self.module_update_list_form.ui.show()
            return
        self.ui.update_network_module_button.setStyleSheet(f"border-image: url({self.pressed_path})")
        self.ui.console.clear()
        print("Network Firmware Updater has been initialized for base update!")
        th.Thread(
            target=self.__click_motion, args=(0, button_start), daemon=True
        ).start()

        modi_ports = list_modi_serialports()
        if not modi_ports:
            raise Exception("No MODI+ port is connected")

        if self.is_multi:
            self.module_update_list_form.ui.setWindowTitle("Update Network Modules")
            self.module_update_list_form.reset_device_list()

        firmware_version_info = self.firmware_manage_form.get_config_firmware_version_info()

        def run_task(self, modi_ports, firmware_version_info):
            self.firmware_updater = NetworkFirmwareMultiUpdater(self.module_firmware_path)
            self.firmware_updater.set_task_end_callback(self.__reset_ui)
            if self.is_multi:
                self.firmware_updater.set_ui(self.ui, self.module_update_list_form)
                self.firmware_updater.update_module_firmware(modi_ports, firmware_version_info)
            else:
                self.firmware_updater.set_ui(self.ui, None)
                self.firmware_updater.update_module_firmware([modi_ports[0]], firmware_version_info)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, firmware_version_info),
            daemon=True
        ).start()

        if self.is_multi:
            if is_raspberrypi():
                self.module_update_list_form.ui.setWindowState(Qt.WindowMaximized)
            self.module_update_list_form.ui.exec_()

    def update_network_submodule_button_clicked(self):
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            if self.is_multi:
                self.esp32_update_list_form.ui.show()
            return
        self.ui.update_network_submodule_button.setStyleSheet(f"border-image: url({self.pressed_path})")
        self.ui.console.clear()
        print("ESP32 Firmware Updater has been initialized for esp update!")
        th.Thread(
            target=self.__click_motion, args=(1, button_start), daemon=True
        ).start()

        modi_ports = list_modi_serialports()
        if not modi_ports:
            raise Exception("No MODI+ port is connected")

        if self.is_multi:
            self.esp32_update_list_form.ui.setWindowTitle("Update Network Submodules")
            self.esp32_update_list_form.reset_device_list()

        firmware_version_info = self.firmware_manage_form.get_config_firmware_version_info()

        def run_task(self, modi_ports, firmware_version_info):
            self.firmware_updater = ESP32FirmwareMultiUploder(self.module_firmware_path)
            self.firmware_updater.set_task_end_callback(self.__reset_ui)
            if self.is_multi:
                self.firmware_updater.set_ui(self.ui, self.esp32_update_list_form)
                self.firmware_updater.update_firmware(modi_ports, False, firmware_version_info)
            else:
                self.firmware_updater.set_ui(self.ui, None)
                self.firmware_updater.update_firmware([modi_ports[0]], False, firmware_version_info)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, firmware_version_info),
            daemon=True
        ).start()

        if self.is_multi:
            if is_raspberrypi():
                self.esp32_update_list_form.ui.setWindowState(Qt.WindowMaximized)
            self.esp32_update_list_form.ui.exec_()

    def delete_user_code_button_clicked(self):
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            if self.is_multi:
                self.esp32_update_list_form.ui.show()
            return
        self.ui.delete_user_code_button.setStyleSheet(f"border-image: url({self.pressed_path})")
        self.ui.console.clear()
        print("ESP32 Firmware Updater has been initialized for esp interpreter update!")
        th.Thread(
            target=self.__click_motion, args=(2, button_start), daemon=True
        ).start()

        modi_ports = list_modi_serialports()
        if not modi_ports:
            raise Exception("No MODI+ port is connected")

        if self.is_multi:
            self.esp32_update_list_form.ui.setWindowTitle("Delete User Code")
            self.esp32_update_list_form.reset_device_list()

        firmware_version_info = self.firmware_manage_form.get_config_firmware_version_info()

        def run_task(self, modi_ports, firmware_version_info):
            self.firmware_updater = ESP32FirmwareMultiUploder(self.module_firmware_path)
            self.firmware_updater.set_task_end_callback(self.__reset_ui)
            if self.is_multi:
                self.firmware_updater.set_ui(self.ui, self.esp32_update_list_form)
                self.firmware_updater.update_firmware(modi_ports, True, firmware_version_info)
            else:
                self.firmware_updater.set_ui(self.ui, None)
                self.firmware_updater.update_firmware([modi_ports[0]], True, firmware_version_info)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, firmware_version_info),
            daemon=True
        ).start()

        if self.is_multi:
            if is_raspberrypi():
                self.esp32_update_list_form.ui.setWindowState(Qt.WindowMaximized)
            self.esp32_update_list_form.ui.exec_()

    def update_general_modules_button_clicked(self):
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            if self.is_multi:
                self.module_update_list_form.ui.show()
            return
        self.ui.update_general_modules_button.setStyleSheet(f"border-image: url({self.pressed_path})")
        self.ui.console.clear()
        print("Module Firmware Updater has been initialized for module update!")
        th.Thread(
            target=self.__click_motion, args=(3, button_start), daemon=True
        ).start()

        modi_ports = list_modi_serialports()
        if not modi_ports:
            self.__reset_ui(self.module_update_list_form)
            raise Exception("No MODI+ port is connected")

        if self.is_multi:
            self.module_update_list_form.ui.setWindowTitle("Update General Modules")
            self.module_update_list_form.reset_device_list()

        firmware_version_info = self.firmware_manage_form.get_config_firmware_version_info()

        def run_task(self, modi_ports, firmware_version_info):
            self.firmware_updater = ModuleFirmwareMultiUpdater(self.module_firmware_path)
            self.firmware_updater.set_task_end_callback(self.__reset_ui)

            if self.is_multi:
                self.firmware_updater.set_ui(self.ui, self.module_update_list_form)
                self.firmware_updater.update_module_firmware(modi_ports, firmware_version_info)
            else:
                self.firmware_updater.set_ui(self.ui, None)
                self.firmware_updater.update_module_firmware([modi_ports[0]], firmware_version_info)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, firmware_version_info),
            daemon=True
        ).start()

        if self.is_multi:
            if is_raspberrypi():
                self.module_update_list_form.ui.setWindowState(Qt.WindowMaximized)
            self.module_update_list_form.ui.exec_()

    def manage_firmware_version_button_clicked(self):
        button_start = time.time()
        self.ui.manage_firmware_version_button.setStyleSheet(f"border-image: url({self.pressed_path})")
        self.ui.console.clear()
        th.Thread(
            target=self.__click_motion, args=(4, button_start), daemon=True
        ).start()

        self.firmware_manage_form.refresh_firmware_info()
        self.firmware_manage_form.ui.exec_()

        self.__reset_ui()

    def devmode_button_clicked(self):
        button_start = time.time()
        self.ui.devmode_button.setStyleSheet(f"border-image: url({self.language_frame_pressed_path});font-size: 13px")
        th.Thread(
            target=self.__click_motion, args=(5, button_start), daemon=True
        ).start()
        self.console = not self.console
        self.refresh_console()

    def translate_button_clicked(self):
        button_start = time.time()
        self.ui.translate_button.setStyleSheet(f"border-image: url({self.language_frame_pressed_path}); font-size: 13px")
        th.Thread(
            target=self.__click_motion, args=(6, button_start), daemon=True
        ).start()

        self.button_in_english = not self.button_in_english
        self.ui.is_english = not self.ui.is_english
        self.refresh_button_text()

    def refresh_console(self):
        if is_raspberrypi():
            self.ui.console.hide()
            self.ui.manage_firmware_version_button.setVisible(False)
            self.ui.setWindowState(Qt.WindowMaximized)
        else:
            if self.console:
                self.ui.console.show()
                self.ui.manage_firmware_version_button.setVisible(True)
            else:
                self.ui.console.hide()
                self.ui.manage_firmware_version_button.setVisible(False)

            self.ui.adjustSize()

    def refresh_button_text(self):
        appropriate_translation = (self.button_en if self.button_in_english else self.button_kr)
        for i, button in enumerate(self.buttons):
            button.setText(appropriate_translation[i])

    def check_module_firmware(self):
        check_success = True
        firmware_list = self.firmware_manage_form.check_firmware()
        if len(firmware_list) == 0:
            download_success = self.firmware_manage_form.download_firmware()
            if download_success:
                refresh_success = self.firmware_manage_form.refresh_firmware_info()
                if refresh_success:
                    self.firmware_manage_form.apply_firmware(show_message=False)
                else:
                    check_success = False
            else:
                check_success = False
        else:
            refresh_success = self.firmware_manage_form.refresh_firmware_info()
            self.firmware_manage_form.apply_firmware(show_message=False)

        if not check_success:
            raise Exception("download firmware first,\n and select firmware version")
        else:
            self.firmware_manage_form.check_firmware_version_update()

    def check_app_update(self):
        try:
            import requests
            response = requests.get("https://api.github.com/repos/LUXROBO/modi2-firmware-updater/releases/latest").json()

            current_version = self.version_info
            latest_version = response["name"]

            download_url = response["assets"][0]["browser_download_url"]
            for asset in response["assets"]:
                file_name = asset["name"]
                if not "Multi" in file_name and not "multi" in file_name:
                    # single updater
                    download_url = asset["browser_download_url"]

            from packaging import version
            if version.parse(latest_version) > version.parse(current_version):
                print(f"need to update to {latest_version}\n{download_url}")
                msg = QMessageBox()
                msg.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))
                msg.setWindowTitle("App update")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText(f"need to update to {latest_version}")
                msg.setDetailedText(download_url)
                msg.exec_()

        except:
            pass

    #
    # Helper functions
    #
    def __popup_excepthook(self, exctype, value, traceback):
        self.__excepthook(exctype, value, traceback)
        if self.is_popup:
            return
        self.popup = PopupMessageBox(self.ui, level="error")
        self.popup.setInformativeText(str(value))
        self.popup.setDetailedText(str(tb.extract_tb(traceback)))
        self.is_popup = True

    def __popup_thread_excepthook(self, err_msg):
        if err_msg.exc_type in self.err_list:
            return
        self.err_list.append(err_msg.exc_type)
        self.stream.thread_error.connect(self.__thread_error_hook)
        self.stream.thread_error.emit(err_msg)

    @pyqtSlot(object)
    def __thread_error_hook(self, err_msg):
        self.__popup_excepthook(err_msg.exc_type, err_msg.exc_value, err_msg.exc_traceback)

    def __click_motion(self, button_type, start_time):
        # Busy wait for 0.2 seconds
        while time.time() - start_time < 0.2:
            pass

        if button_type in [5, 6]:
            self.buttons[button_type].setStyleSheet(f"border-image: url({self.language_frame_path}); font-size: 13px")
        else:
            self.buttons[button_type].setStyleSheet(f"border-image: url({self.active_path})")
            for i, q_button in enumerate(self.buttons):
                if i in [button_type, 5, 6]:
                    continue
                q_button.setStyleSheet(f"border-image: url({self.inactive_path})")
                q_button.setEnabled(False)

    def __reset_ui(self, list_ui = None):
        for i, q_button in enumerate(self.buttons):
            if i in [5, 6]:
                continue
            q_button.setStyleSheet(f"border-image: url({self.active_path})")
            q_button.setEnabled(True)

        # refresh language
        self.refresh_button_text()

        # reset list ui
        if list_ui == self.module_update_list_form:
            self.module_update_list_form.ui.close_button.setEnabled(True)
            self.module_update_list_form.total_status_signal.emit("Complete")
            self.module_update_list_form.total_progress_signal.emit(100)
        elif list_ui == self.esp32_update_list_form:
            self.esp32_update_list_form.ui.close_button.setEnabled(True)
            self.esp32_update_list_form.total_status_signal.emit("Complete")

    def __append_text_line(self, line):
        self.ui.console.moveCursor(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor)
        self.ui.console.moveCursor(QtGui.QTextCursor.StartOfLine, QtGui.QTextCursor.MoveAnchor)
        self.ui.console.moveCursor(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)

        # Remove new line character if current line represents update_progress
        if self.__is_update_progress_line(line):
            self.ui.console.textCursor().removeSelectedText()
            self.ui.console.textCursor().deletePreviousChar()

        # Display user text input
        self.ui.console.moveCursor(QtGui.QTextCursor.End)
        self.ui.console.insertPlainText(line)

    @staticmethod
    def __is_update_progress_line(line):
        return line.startswith("\r")