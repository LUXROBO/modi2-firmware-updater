import os
import io
import sys
import time
import logging
import pathlib
import threading as th
import traceback as tb

from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QDialog

from modi2_multi_uploader.firmware_manager import FirmwareManagerForm
from modi2_multi_uploader.update_list_form import ESP32UpdateListForm, ModuleUpdateListForm
from modi2_multi_uploader.core.esp32_uploader import ESP32FirmwareMultiUploder
from modi2_multi_uploader.core.module_uploader import ModuleFirmwareMultiUpdater
from modi2_multi_uploader.core.network_uploader import NetworkFirmwareMultiUpdater
from modi2_multi_uploader.util.connection_util import list_modi_ports


class StdoutRedirect(QObject):
    printOccur = pyqtSignal(str, str, name="print")

    def __init__(self):
        QObject.__init__(self, None)
        self.daemon = True
        self.sysstdout = sys.stdout.write
        self.sysstderr = sys.stderr.write
        self.logger = None

    def stop(self):
        sys.stdout.write = self.sysstdout
        sys.stderr.write = self.sysstderr

    def start(self):
        sys.stdout.write = self.write
        sys.stderr.write = lambda msg: self.write(msg, color="red")

    def write(self, s, color="black"):
        sys.stdout.flush()
        self.printOccur.emit(s, color)
        if self.logger and not self.__is_redundant_line(s):
            self.logger.info(s)

    @staticmethod
    def __is_redundant_line(line):
        return (
            line.startswith("\rUpdating") or
            line.startswith("\rFirmware Upload: [") or
            len(line) < 3
        )


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
            textEdit.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding,
            )

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
    GUI Form of MODI Firmware Updater
    """

    def __init__(self, debug=False):
        QDialog.__init__(self)
        self.logger = self.__init_logger()
        self.__excepthook = sys.excepthook
        sys.excepthook = self.__popup_excepthook
        th.excepthook = self.__popup_thread_excepthook
        self.err_list = list()
        self.is_popup = False

        ui_path = os.path.join(os.path.dirname(__file__), "assets", "uploader.ui")
        firmware_manager_ui_path = os.path.join(os.path.dirname(__file__), "assets", "firmware_manager.ui")
        esp32_upload_list_ui_path = os.path.join(os.path.dirname(__file__), "assets", "esp32_upload_list.ui")
        module_upload_list_ui_path = os.path.join(os.path.dirname(__file__), "assets", "module_upload_list.ui")
        if sys.platform.startswith("win"):
            self.component_path = pathlib.PurePosixPath(pathlib.PurePath(__file__), "..", "assets", "component")
        else:
            self.component_path = os.path.join(os.path.dirname(__file__), "assets", "component")
        self.ui = uic.loadUi(ui_path)
        self.assets_firmware_path = os.path.join(os.path.dirname(__file__), "assets", "firmware", "binary")
        self.firmware_version_config_path = os.path.join(os.path.dirname(__file__), "assets", "firmware", "firmware_version.json")
        self.local_firmware_path = os.path.join(os.path.expanduser("~"), "Documents", "modi2 multi uploader")

        self.ui.setStyleSheet("background-color: white")
        self.ui.console.hide()
        self.ui.firmware_manage_button.setVisible(False)
        self.ui.setFixedHeight(640)

        # Set LUXROBO logo image
        logo_path = os.path.join(self.component_path, "luxrobo_logo.png")
        qPixmapVar = QtGui.QPixmap()
        qPixmapVar.load(logo_path)
        self.ui.lux_logo.setPixmap(qPixmapVar)

        self.firmware_manage_form = FirmwareManagerForm(path_dict={
            "ui": firmware_manager_ui_path,
            "component": self.component_path,
            "firmware_version_config": self.firmware_version_config_path,
            "assets_firmware": self.assets_firmware_path,
            "local_firmware": self.local_firmware_path,
        })
        self.esp32_upload_list_form = ESP32UpdateListForm(path_dict={
            "ui": esp32_upload_list_ui_path,
            "component": self.component_path,
        })
        self.module_upload_list_form = ModuleUpdateListForm(path_dict={
            "ui": module_upload_list_ui_path,
            "component": self.component_path,
        })

        # Buttons image
        self.active_path = pathlib.PurePosixPath(self.component_path, "btn_frame_active.png")
        self.inactive_path = pathlib.PurePosixPath(self.component_path, "btn_frame_inactive.png")
        self.pressed_path = pathlib.PurePosixPath(self.component_path, "btn_frame_pressed.png")
        self.language_frame_path = pathlib.PurePosixPath(self.component_path, "lang_frame.png")
        self.language_frame_pressed_path = pathlib.PurePosixPath(self.component_path, "lang_frame_pressed.png")

        self.ui.update_network_esp32_button.setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
        self.ui.update_network_esp32_interpreter_button.setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
        self.ui.change_modules_type_button.setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
        self.ui.module_type_combobox.setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
        self.ui.update_modules_button.setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
        self.ui.update_network_button.setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
        self.ui.update_network_bootloader_button.setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
        self.ui.firmware_manage_button.setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
        self.ui.translate_button.setStyleSheet(f"border-image: url({self.language_frame_path}); font-size: 13px")
        self.ui.devmode_button.setStyleSheet(f"border-image: url({self.language_frame_path}); font-size: 13px")
        self.ui.console.setStyleSheet("font-size: 10px")

        version_path = os.path.join(os.path.dirname(__file__), "..", "version.txt")
        with io.open(version_path, "r") as version_file:
            version_info = version_file.readline().lstrip("v").rstrip("\n")

        self.ui.setWindowTitle("MODI+ Multi Uploader - v" + version_info)
        self.ui.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))

        # Redirect stdout to text browser (i.e. console in our UI)
        if not debug:
            self.stdout = StdoutRedirect()
            self.stdout.start()
            self.stdout.printOccur.connect(
                lambda line: self.__append_text_line(line)
            )
            self.stdout.logger = self.logger

        # Set signal for thread communication
        self.stream = ThreadSignal()

        # Connect up the buttons
        self.ui.update_network_esp32_button.clicked.connect(self.update_network_esp32)
        self.ui.update_network_esp32_interpreter_button.clicked.connect(self.update_network_esp32_interpreter)
        self.ui.change_modules_type_button.clicked.connect(self.change_modules_type)
        self.ui.update_modules_button.clicked.connect(self.update_modules)
        self.ui.update_network_button.clicked.connect(self.update_network)
        self.ui.update_network_bootloader_button.clicked.connect(self.update_network_bootloader)
        self.ui.firmware_manage_button.clicked.connect(self.firmware_manage)
        self.ui.translate_button.clicked.connect(self.translate_button_text)
        self.ui.devmode_button.clicked.connect(self.dev_mode_button)

        self.buttons = [
            self.ui.update_network_esp32_button,
            self.ui.update_network_esp32_interpreter_button,
            self.ui.change_modules_type_button,
            self.ui.update_modules_button,
            self.ui.update_network_button,
            self.ui.update_network_bootloader_button,
            self.ui.firmware_manage_button,
            self.ui.devmode_button,
            self.ui.translate_button,
        ]

        self.button_en = [
            "Update Network ESP32",
            "Update Network ESP32 Interpreter",
            "Change Modules Type",
            "Update Modules",
            "Update Network Modules",
            "Set Network Bootloader",
            "Manage Firmware",
            "Dev Mode",
            "한국어",
        ]

        self.button_kr = [
            "네트워크 모듈 업데이트",
            "네트워크 모듈 인터프리터 초기화",
            "모듈 타입 변경",
            "모듈 초기화",
            "네트워크 모듈 초기화",
            "네트워크 모듈 부트로더",
            "펌웨어 관리",
            "개발자 모드",
            "English",
        ]

        # Disable the first button to be focused when UI is loaded
        self.ui.update_network_esp32_button.setAutoDefault(False)
        self.ui.update_network_esp32_button.setDefault(False)

        # Print init status
        time_now_str = time.strftime("[%Y/%m/%d@%X]", time.localtime())
        print(time_now_str + " GUI MODI Firmware Updater has been started!")

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
        self.ui.popup = self._thread_signal_hook

        # check module firmware
        self.check_module_firmware()

        # Set Button Status
        self.refresh_button_text()
        self.refresh_console()
        self.ui.show()

    #
    # Main methods
    #
    def update_network_esp32(self):
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            self.esp32_upload_list_form.ui.show()
            return
        self.ui.update_network_esp32_button.setStyleSheet(f"border-image: url({self.pressed_path}); font-size: 16px")
        self.ui.console.clear()
        print("ESP32 Firmware Updater has been initialized for esp update!")
        th.Thread(
            target=self.__click_motion, args=(0, button_start), daemon=True
        ).start()

        modi_ports = list_modi_ports()
        if not modi_ports:
            raise Exception("No MODI port is connected")

        self.esp32_upload_list_form.ui.setWindowTitle("Update Network ESP32")
        self.esp32_upload_list_form.reset_device_list()
        firmware_version_info = self.firmware_manage_form.get_config_firmware_version_info()

        def run_task(self, modi_ports, firmware_version_info):
            esp32_updater = ESP32FirmwareMultiUploder(self.local_firmware_path)
            esp32_updater.set_ui(self.ui, self.esp32_upload_list_form)
            esp32_updater.set_task_end_callback(self.__reset_ui)
            self.firmware_updater = esp32_updater
            esp32_updater.update_firmware(modi_ports, False, firmware_version_info)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, firmware_version_info),
            daemon=True
        ).start()

        self.esp32_upload_list_form.ui.exec_()

    def update_network_esp32_interpreter(self):
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            self.esp32_upload_list_form.ui.show()
            return
        self.ui.update_network_esp32_interpreter_button.setStyleSheet(f"border-image: url({self.pressed_path}); font-size: 16px")
        self.ui.console.clear()
        print("ESP32 Firmware Updater has been initialized for esp interpreter update!")
        th.Thread(
            target=self.__click_motion, args=(1, button_start), daemon=True
        ).start()

        modi_ports = list_modi_ports()
        if not modi_ports:
            raise Exception("No MODI port is connected")

        self.esp32_upload_list_form.ui.setWindowTitle("Update Network ESP32 Interpreter")
        self.esp32_upload_list_form.reset_device_list()
        firmware_version_info = self.firmware_manage_form.get_config_firmware_version_info()

        def run_task(self, modi_ports, firmware_version_info):
            esp32_updater = ESP32FirmwareMultiUploder(self.local_firmware_path)
            esp32_updater.set_ui(self.ui, self.esp32_upload_list_form)
            esp32_updater.set_task_end_callback(self.__reset_ui)
            self.firmware_updater = esp32_updater
            esp32_updater.update_firmware(modi_ports, True, firmware_version_info)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, firmware_version_info),
            daemon=True
        ).start()

        self.esp32_upload_list_form.ui.exec_()

    def change_modules_type(self):
        module_type = self.ui.module_type_combobox.currentText()
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            self.module_upload_list_form.ui.show()
            return
        self.ui.change_modules_type_button.setStyleSheet(f"border-image: url({self.pressed_path}); font-size: 16px")
        self.ui.console.clear()
        print(f"Module Firmware Updater has been initialized for changing module type to {module_type}")
        th.Thread(
            target=self.__click_motion, args=(2, button_start), daemon=True
        ).start()

        modi_ports = list_modi_ports()
        if not modi_ports:
            raise Exception("No MODI port is connected")

        self.module_upload_list_form.ui.setWindowTitle("Change Modules Type")
        self.module_upload_list_form.reset_device_list()

        def run_task(self, modi_ports, module_type):
            module_updater = ModuleFirmwareMultiUpdater()
            module_updater.set_ui(self.ui, self.module_upload_list_form)
            module_updater.set_task_end_callback(self.__reset_ui)
            self.firmware_updater = module_updater
            module_updater.change_module_type(modi_ports, module_type)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, module_type),
            daemon=True
        ).start()

        self.module_upload_list_form.ui.exec_()

    def update_modules(self):
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            self.module_upload_list_form.ui.show()
            return
        self.ui.update_modules_button.setStyleSheet(f"border-image: url({self.pressed_path}); font-size: 16px")
        self.ui.console.clear()
        print("Module Firmware Updater has been initialized for module update!")
        th.Thread(
            target=self.__click_motion, args=(3, button_start), daemon=True
        ).start()

        modi_ports = list_modi_ports()
        if not modi_ports:
            self.__reset_ui(self.module_upload_list_form)
            raise Exception("No MODI port is connected")

        self.module_upload_list_form.ui.setWindowTitle("Update Modules")
        self.module_upload_list_form.reset_device_list()
        firmware_version_info = self.firmware_manage_form.get_config_firmware_version_info()

        def run_task(self, modi_ports, firmware_version_info):
            module_updater = ModuleFirmwareMultiUpdater(self.local_firmware_path)
            module_updater.set_ui(self.ui, self.module_upload_list_form)
            module_updater.set_task_end_callback(self.__reset_ui)
            self.firmware_updater = module_updater
            module_updater.update_module_firmware(modi_ports, firmware_version_info)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, firmware_version_info),
            daemon=True
        ).start()

        self.module_upload_list_form.ui.exec_()

    def update_network(self):
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            self.module_upload_list_form.ui.show()
            return
        self.ui.update_network_button.setStyleSheet(f"border-image: url({self.pressed_path}); font-size: 16px")
        self.ui.console.clear()
        print("Network Firmware Updater has been initialized for base update!")
        th.Thread(
            target=self.__click_motion, args=(4, button_start), daemon=True
        ).start()

        modi_ports = list_modi_ports()
        if not modi_ports:
            raise Exception("No MODI port is connected")

        self.module_upload_list_form.ui.setWindowTitle("Update Network Modules")
        self.module_upload_list_form.reset_device_list()
        firmware_version_info = self.firmware_manage_form.get_config_firmware_version_info()

        def run_task(self, modi_ports, firmware_version_info):
            network_updater = NetworkFirmwareMultiUpdater(self.local_firmware_path)
            network_updater.set_ui(self.ui, self.module_upload_list_form)
            network_updater.set_task_end_callback(self.__reset_ui)
            self.firmware_updater = network_updater
            network_updater.update_module_firmware(modi_ports, False, firmware_version_info)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, firmware_version_info),
            daemon=True
        ).start()

        self.module_upload_list_form.ui.exec_()

    def update_network_bootloader(self):
        button_start = time.time()
        if self.firmware_updater and self.firmware_updater.update_in_progress:
            self.module_upload_list_form.ui.show()
            return
        self.ui.update_network_bootloader_button.setStyleSheet(f"border-image: url({self.pressed_path}); font-size: 16px")
        self.ui.console.clear()
        print("Network Firmware Updater has been initialized for base update!")
        th.Thread(
            target=self.__click_motion, args=(5, button_start), daemon=True
        ).start()

        modi_ports = list_modi_ports()
        if not modi_ports:
            raise Exception("No MODI port is connected")

        self.module_upload_list_form.ui.setWindowTitle("Set Network Bootloader")
        self.module_upload_list_form.reset_device_list()
        firmware_version_info = self.firmware_manage_form.get_config_firmware_version_info()

        def run_task(self, modi_ports, firmware_version_info):
            network_updater = NetworkFirmwareMultiUpdater(self.local_firmware_path)
            network_updater.set_ui(self.ui, self.module_upload_list_form)
            network_updater.set_task_end_callback(self.__reset_ui)
            self.firmware_updater = network_updater
            network_updater.update_module_firmware(modi_ports, True, firmware_version_info)

        th.Thread(
            target=run_task,
            args=(self, modi_ports, firmware_version_info),
            daemon=True
        ).start()

        self.module_upload_list_form.ui.exec_()

    def firmware_manage(self):
        button_start = time.time()
        self.ui.firmware_manage_button.setStyleSheet(f"border-image: url({self.pressed_path}); font-size: 16px")
        self.ui.console.clear()
        th.Thread(
            target=self.__click_motion, args=(6, button_start), daemon=True
        ).start()

        self.firmware_manage_form.refresh_firmware_info()
        self.firmware_manage_form.ui.exec_()

        self.__reset_ui()

    def dev_mode_button(self):
        button_start = time.time()
        self.ui.devmode_button.setStyleSheet(f"border-image: url({self.language_frame_pressed_path});font-size: 13px")
        th.Thread(
            target=self.__click_motion, args=(7, button_start), daemon=True
        ).start()
        self.console = not self.console
        self.refresh_console()

    def refresh_console(self):
        if self.console:
            self.ui.console.show()
            self.ui.firmware_manage_button.setVisible(True)
            self.ui.setFixedHeight(720)
        else:
            self.ui.console.hide()
            self.ui.firmware_manage_button.setVisible(False)
            self.ui.setFixedHeight(640)

    def translate_button_text(self):
        button_start = time.time()
        self.ui.translate_button.setStyleSheet(f"border-image: url({self.language_frame_pressed_path}); font-size: 13px")
        th.Thread(
            target=self.__click_motion, args=(8, button_start), daemon=True
        ).start()

        self.button_in_english = not self.button_in_english
        self.ui.is_english = not self.ui.is_english
        self.refresh_button_text()

    def refresh_button_text(self):
        appropriate_translation = (
            self.button_en if self.button_in_english else self.button_kr
        )
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
            def error_exception(message):
                time.sleep(1)
                raise Exception(message)

            th.Thread(
                target=error_exception,
                args=("download firmware first,\n and select firmware version"),
                daemon=True
            ).start()
    #
    # Helper functions
    #
    @staticmethod
    def __init_logger():
        logger = logging.getLogger("GUI MODI Firmware Updater Logger")
        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler = logging.FileHandler("gmfu.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        return logger

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
        self.__popup_excepthook(
            err_msg.exc_type, err_msg.exc_value, err_msg.exc_traceback
        )

    @pyqtSlot(object)
    def _thread_signal_hook(self):
        self.thread_popup = PopupMessageBox(self.ui, level="warning")
        if self.button_in_english:
            text = (
                "Reconnect network module and "
                "click the button again please."
            )
        else:
            text = "네트워크 모듈을 재연결 후 버튼을 다시 눌러주십시오."
        self.thread_popup.setInformativeText(text)
        self.is_popup = True

    def __click_motion(self, button_type, start_time):
        # Busy wait for 0.2 seconds
        while time.time() - start_time < 0.2:
            pass

        if button_type in [7, 8]:
            self.buttons[button_type].setStyleSheet(f"border-image: url({self.language_frame_path}); font-size: 13px")
        else:
            self.ui.module_type_combobox.setEnabled(False)
            self.buttons[button_type].setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
            for i, q_button in enumerate(self.buttons):
                if i in [button_type, 7, 8]:
                    continue
                q_button.setStyleSheet(f"border-image: url({self.inactive_path}); font-size: 16px")
                q_button.setEnabled(False)

    def __reset_ui(self, list_ui = None):
        self.ui.module_type_combobox.setEnabled(True)
        for i, q_button in enumerate(self.buttons):
            if i in [7, 8]:
                continue
            q_button.setStyleSheet(f"border-image: url({self.active_path}); font-size: 16px")
            q_button.setEnabled(True)

        # refresh language
        self.refresh_button_text()

        # reset list ui
        if list_ui == self.module_upload_list_form:
            self.module_upload_list_form.ui.close_button.setEnabled(True)
            self.module_upload_list_form.total_status_signal.emit("Complete")
            self.module_upload_list_form.total_progress_signal.emit(100)
        elif list_ui == self.esp32_upload_list_form:
            self.esp32_upload_list_form.ui.close_button.setEnabled(True)
            self.esp32_upload_list_form.total_status_signal.emit("Complete")

    def __append_text_line(self, line):
        self.ui.console.moveCursor(
            QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor
        )
        self.ui.console.moveCursor(
            QtGui.QTextCursor.StartOfLine, QtGui.QTextCursor.MoveAnchor
        )
        self.ui.console.moveCursor(
            QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor
        )

        # Remove new line character if current line represents update_progress
        if self.__is_update_progress_line(line):
            self.ui.console.textCursor().removeSelectedText()
            self.ui.console.textCursor().deletePreviousChar()

        # Display user text input
        self.ui.console.moveCursor(QtGui.QTextCursor.End)
        self.ui.console.insertPlainText(line)
        # QtWidgets.QApplication.processEvents(
        #     QtCore.QEventLoop.ExcludeUserInputEvents
        # )

    @staticmethod
    def __is_update_progress_line(line):
        return line.startswith("\rUpdating") or line.startswith("\rFirmware Upload: [")