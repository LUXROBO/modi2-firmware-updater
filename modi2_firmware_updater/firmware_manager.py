import http.client as httplib
import json
import os
import shutil
import stat
from functools import cmp_to_key

from PyQt5 import QtGui, uic
from PyQt5.QtCore import QSignalMapper
from PyQt5.QtWidgets import QDialog, QMessageBox


class FirmwareManagerForm(QDialog):

    def __init__(self, path_dict={}):
        QDialog.__init__(self)

        self.component_path = path_dict["component"]
        self.assets_firmware_path = path_dict["assets_firmware"]
        self.local_firmware_path = path_dict["local_firmware"]
        self.module_firmware_directory = path_dict["firmware_directory"]

        self.local_firmware_binary_path = os.path.join(self.local_firmware_path, self.module_firmware_directory)
        self.local_firmware_version_path = os.path.join(self.local_firmware_path, "firmware_version.json")

        self.ui = uic.loadUi(path_dict["ui"])
        self.ui.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))
        self.ui.close_button.clicked.connect(self.ui.close)

        self.ui.download_button.clicked.connect(self.download_button_clicked)
        self.ui.refresh_button.clicked.connect(self.refresh_button_clicked)
        self.ui.apply_button.clicked.connect(self.apply_button_clicked)

        self.module_list = [
            "battery",
            "button",
            "dial",
            "display",
            "env",
            "imu",
            "joystick",
            "led",
            "motor",
            "speaker",
            "tof",
            "network"
        ]

        self.module_ui_dic = {
            "button": {
                "icon": self.ui.button_image,
                "app": self.ui.button_app_combobox,
                "os": self.ui.button_os_text,
                "bootloader": self.ui.button_bootloader_combobox
            },
            "dial": {
                "icon": self.ui.dial_image,
                "app": self.ui.dial_app_combobox,
                "os": self.ui.dial_os_text,
                "bootloader": self.ui.dial_bootloader_combobox
            },
            "env": {
                "icon": self.ui.env_image,
                "app": self.ui.env_app_combobox,
                "os": self.ui.env_os_text,
                "bootloader": self.ui.env_bootloader_combobox
            },
            "imu": {
                "icon": self.ui.imu_image,
                "app": self.ui.imu_app_combobox,
                "os": self.ui.imu_os_text,
                "bootloader": self.ui.imu_bootloader_combobox
            },
            "joystick": {
                "icon": self.ui.joystick_image,
                "app": self.ui.joystick_app_combobox,
                "os": self.ui.joystick_os_text,
                "bootloader": self.ui.joystick_bootloader_combobox
            },
            "tof": {
                "icon": self.ui.tof_image,
                "app": self.ui.tof_app_combobox,
                "os": self.ui.tof_os_text,
                "bootloader": self.ui.tof_bootloader_combobox
            },
            "led": {
                "icon": self.ui.led_image,
                "app": self.ui.led_app_combobox,
                "os": self.ui.led_os_text,
                "bootloader": self.ui.led_bootloader_combobox
            },
            "display": {
                "icon": self.ui.display_image,
                "app": self.ui.display_app_combobox,
                "os": self.ui.display_os_text,
                "bootloader": self.ui.display_bootloader_combobox
            },
            "motor": {
                "icon": self.ui.motor_image,
                "app": self.ui.motor_app_combobox,
                "os": self.ui.motor_os_text,
                "bootloader": self.ui.motor_bootloader_combobox
            },
            "speaker": {
                "icon": self.ui.speaker_image,
                "app": self.ui.speaker_app_combobox,
                "os": self.ui.speaker_os_text,
                "bootloader": self.ui.speaker_bootloader_combobox
            },
            "battery": {
                "icon": self.ui.battery_image,
                "app": self.ui.battery_app_combobox,
                "os": self.ui.battery_os_text,
                "bootloader": self.ui.battery_bootloader_combobox
            },
            "network": {
                "icon": self.ui.network_image,
                "app": self.ui.network_app_combobox
            },
            "esp32_app": {
                "icon": self.ui.esp32_app_image,
                "app": self.ui.esp32_app_combobox
            },
            "esp32_ota": {
                "icon": self.ui.esp32_ota_image,
                "app": self.ui.esp32_ota_combobox
            },
        }

        mapper = QSignalMapper(self)
        for key in self.module_ui_dic.keys():
            if key in ["network", "esp32_app", "esp32_ota"]:
                icon_path = os.path.join(self.component_path, "modules", "network_28.png")
                pixmap = QtGui.QPixmap()
                pixmap.load(icon_path)
                self.module_ui_dic[key]["icon"].setPixmap(pixmap)
            else:
                module_type = key
                icon_path = os.path.join(self.component_path, "modules", module_type + "_28.png")
                pixmap = QtGui.QPixmap()
                pixmap.load(icon_path)
                self.module_ui_dic[key]["icon"].setPixmap(pixmap)
                mapper.setMapping(self.module_ui_dic[key]["app"], str(module_type))
                self.module_ui_dic[key]["app"].currentTextChanged.connect(mapper.map)
        mapper.mapped["QString"].connect(self.app_version_combobox_changed)

        self.module_firmware_version = self.get_config_firmware_version_info()["version"]

    def download_button_clicked(self):
        download_success = self.download_firmware()
        msg = QMessageBox()
        msg.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))
        msg.setWindowTitle("download firmware")
        msg.setStandardButtons(QMessageBox.Ok)
        if download_success:
            self.refresh_firmware_info()
            self.apply_firmware(show_message=False)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("download successful.")
        else:
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("check internet connection.")
        msg.exec_()

    def refresh_button_clicked(self):
        refresh_success = self.refresh_firmware_info()
        msg = QMessageBox()
        msg.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))
        msg.setWindowTitle("refresh firmware")
        msg.setStandardButtons(QMessageBox.Ok)
        if refresh_success:
            self.apply_firmware(show_message=False)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("refresh successful.")
        else:
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("download firmware first.")
        msg.exec_()

    def apply_button_clicked(self):
        self.apply_firmware(show_message=True)

    def download_firmware(self):
        connection = self.__check_internet_connection()
        if not connection:
            self.copy_assets_firmware()
            return True

        try:
            if os.path.exists(self.local_firmware_binary_path):
                self.__rmtree(self.local_firmware_binary_path)

            import requests
            release_url = "https://api.github.com/repos/LUXROBO/modi-v2-module-binary/releases/latest"
            response = requests.get(release_url).json()
            download_url = response["zipball_url"]
            version_name = response["name"]
            content = requests.get(download_url)

            # unzip the content
            from io import BytesIO
            from zipfile import ZipFile
            zip = ZipFile(BytesIO(content.content))
            root_dir_name = zip.infolist()[0].filename.split("/")[0]
            zip.extractall(self.local_firmware_path)
            os.rename(os.path.join(self.local_firmware_path, root_dir_name), self.local_firmware_binary_path)

            self.module_firmware_version = version_name

        except Exception as e:
            print(e)
            self.copy_assets_firmware()

        return True

    def copy_assets_firmware(self):
        if os.path.exists(self.local_firmware_path):
            self.__rmtree(self.local_firmware_path)

        os.mkdir(self.local_firmware_path)

        shutil.copytree(self.assets_firmware_path, self.local_firmware_path, dirs_exist_ok=True)

    def check_firmware(self):
        if not os.path.exists(self.local_firmware_binary_path):
            return {}

        file_list = os.listdir(self.local_firmware_binary_path)
        firmware_list = {}
        for ele in file_list:
            if not os.path.isfile(ele) and ele != ".git":
                if ele in self.module_list:
                    # modules - barrey, button, ...., network
                    module_type = ele
                    version_dir = os.path.join(self.local_firmware_binary_path, module_type)
                    version_list = os.listdir(version_dir)
                    if len(version_list):
                        firmware_list[module_type] = []
                        for version in version_list:
                            module_path = os.path.join(version_dir, version, module_type + ".bin")
                            if os.path.exists(module_path):
                                firmware_list[module_type].append(version)
                elif ele == "bootloader":
                    # check e230
                    bootloader_e230_version_dir = os.path.join(self.local_firmware_binary_path, ele, "e230")
                    bootloader_e230_version_list = os.listdir(bootloader_e230_version_dir)
                    if len(bootloader_e230_version_list):
                        firmware_list["bootloader_e230"] = []
                        for version in bootloader_e230_version_list:
                            bootloader_path = os.path.join(bootloader_e230_version_dir, version, "bootloader_e230.bin")
                            second_bootloader_path = os.path.join(bootloader_e230_version_dir, version, "second_bootloader_e230.bin")
                            if os.path.exists(bootloader_path) and os.path.exists(second_bootloader_path):
                                firmware_list["bootloader_e230"].append(version)
                    # check e103
                    bootloader_e103_version_dir = os.path.join(self.local_firmware_binary_path, ele, "e103")
                    bootloader_e103_version_list = os.listdir(bootloader_e103_version_dir)
                    if len(bootloader_e103_version_list):
                        firmware_list["bootloader_e103"] = []
                        for version in bootloader_e103_version_list:
                            bootloader_path = os.path.join(bootloader_e103_version_dir, version, "bootloader_e103.bin")
                            second_bootloader_path = os.path.join(bootloader_e103_version_dir, version, "second_bootloader_e103.bin")
                            if os.path.exists(bootloader_path) and os.path.exists(second_bootloader_path):
                                firmware_list["bootloader_e103"].append(version)
                elif ele == "esp32":
                    # check esp32 app
                    esp32_app_version_dir = os.path.join(self.local_firmware_binary_path, ele, "app")
                    esp32_app_version_list = os.listdir(esp32_app_version_dir)
                    if len(esp32_app_version_list):
                        firmware_list["esp32_app"] = []
                        for version in esp32_app_version_list:
                            bootloader_path = os.path.join(esp32_app_version_dir, version, "bootloader.bin")
                            eps32_path = os.path.join(esp32_app_version_dir, version, "esp32.bin")
                            ota_data_initial_path = os.path.join(esp32_app_version_dir, version, "ota_data_initial.bin")
                            partitions_path = os.path.join(esp32_app_version_dir, version, "partitions.bin")
                            if os.path.exists(bootloader_path) and os.path.exists(eps32_path) and os.path.exists(ota_data_initial_path) and os.path.exists(partitions_path):
                                firmware_list["esp32_app"].append(version)
                    # check esp32 ota
                    esp32_ota_version_dir = os.path.join(self.local_firmware_binary_path, ele, "ota")
                    esp32_ota_version_list = os.listdir(esp32_ota_version_dir)
                    if len(esp32_ota_version_list):
                        firmware_list["esp32_ota"] = []
                        for version in esp32_ota_version_list:
                            modi_ota_factory_path = os.path.join(esp32_ota_version_dir, version, "modi_ota_factory.bin")
                            if os.path.exists(modi_ota_factory_path):
                                firmware_list["esp32_ota"].append(version)
        return firmware_list

    def refresh_firmware_info(self):
        firmware_list = self.check_firmware()
        if len(firmware_list) == 0:
            return False

        try:
            for key in firmware_list.keys():
                if key in ["bootloader_e103", "bootloader_e230"]:
                    continue

                # app version
                version_list = firmware_list[key]
                version_list = sorted(version_list, key=cmp_to_key(self.__compare_version), reverse=True)
                self.module_ui_dic[key]["app"].clear()
                for version in version_list:
                    self.module_ui_dic[key]["app"].addItem(version)

                if key in ["network", "esp32_app", "esp32_ota"]:
                    continue

                # bootloader version
                bootloader_name = "bootloader_e230"
                if key in ["env", "speaker", "display"]:
                    bootloader_name = "bootloader_e103"

                version_list = firmware_list[bootloader_name]
                version_list = sorted(version_list, key=cmp_to_key(self.__compare_version), reverse=True)
                self.module_ui_dic[key]["bootloader"].clear()
                for version in version_list:
                    self.module_ui_dic[key]["bootloader"].addItem(version)

        except Exception as e:
            print(e)
            return False

        return True

    def apply_firmware(self, show_message):
        firmware_version_info = self.get_selected_firmware_version_info()
        with open(self.local_firmware_version_path, "w") as config_file:
            firmware_version_info["version"] = self.module_firmware_version
            json_msg = json.dumps(firmware_version_info, indent=4)
            config_file.write(str(json_msg))

        if show_message:
            msg = QMessageBox()
            msg.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))
            msg.setWindowTitle("apply firmware")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("apply successful.")
            msg.exec_()

    def check_firmware_version_update(self):
        connection = self.__check_internet_connection()
        if not connection:
            return False

        try:
            import requests
            response = requests.get("https://api.github.com/repos/LUXROBO/modi-v2-module-binary/releases/latest").json()

            current_version = self.module_firmware_version
            latest_version = response["name"]

            from packaging import version
            if version.parse(latest_version) > version.parse(current_version):
                self.download_firmware()
                self.refresh_firmware_info()
                self.apply_firmware(show_message=False)

                msg = QMessageBox()
                msg.setWindowIcon(QtGui.QIcon(os.path.join(self.component_path, "network_module.ico")))
                msg.setWindowTitle("Module firmware update")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText(f"module firmware updated to {latest_version}")
                msg.exec_()

        except Exception as e:
            print(str(e))
            return False

        return True

    def get_selected_firmware_version_info(self):
        module_version_dic = {}
        for key in self.module_ui_dic.keys():
            module_version_dic[key] = {}
            module_version_dic[key]["app"] = self.module_ui_dic[key]["app"].currentText()

            if key in ["network", "esp32_app", "esp32_ota"]:
                continue

            module_version_dic[key]["os"] = self.module_ui_dic[key]["os"].text()
            module_version_dic[key]["bootloader"] = self.module_ui_dic[key]["bootloader"].currentText()
        return module_version_dic

    def get_config_firmware_version_info(self):
        if os.path.isfile(self.local_firmware_version_path):
            firmware_version_path = self.local_firmware_version_path
        else:
            firmware_version_path = os.path.join(self.assets_firmware_path, "firmware_version.json")

        with open(firmware_version_path, "r") as config_file:
            config_info = config_file.read()
            return json.loads(config_info)

    def app_version_combobox_changed(self, module_type):
        selected_app_version = self.module_ui_dic[module_type]["app"].currentText()
        if len(selected_app_version) == 0:
            return

        self.module_ui_dic[module_type]["os"].clear()
        version_text_path = os.path.join(self.local_firmware_binary_path, module_type, selected_app_version, "version.txt")
        with open(version_text_path, "r") as version_text_file:
            version_text = version_text_file.read()
            version_info = json.loads(version_text)
            self.module_ui_dic[module_type]["os"].setText(version_info["os"])

    @staticmethod
    def __check_internet_connection():
        conn = httplib.HTTPConnection("www.google.com", timeout=3)
        try:
            conn.request("HEAD", "/")
            conn.close()
            return True
        except Exception as e:
            print(e)
            return False

    @staticmethod
    def __rmtree(top):
        for root, dirs, files in os.walk(top, topdown=False):
            for name in files:
                filename = os.path.join(root, name)
                os.chmod(filename, stat.S_IWUSR)
                os.remove(filename)
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(top)

    @staticmethod
    def __compare_version(left, right):
        from packaging import version

        if version.parse(left) > version.parse(right):
            return 1
        elif version.parse(left) == version.parse(right):
            return 0
        else:
            return -1
