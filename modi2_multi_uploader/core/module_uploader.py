import json
import sys
import threading as th
import time
from base64 import b64decode, b64encode
from io import open
from os import path

import serial
import serial.tools.list_ports as stl

from modi2_multi_uploader.util.connection_util import SerTask
from modi2_multi_uploader.util.message_util import (decode_message, parse_message, unpack_data)
from modi2_multi_uploader.util.module_util import (Module, get_module_type_from_uuid)
from modi2_multi_uploader.util.module_util import (Module, get_module_uuid_from_type)


def retry(exception_to_catch):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_to_catch:
                return wrapper(*args, **kwargs)

        return wrapper

    return decorator


class ModuleFirmwareUpdater:
    """Module Firmware Updater: Updates a firmware of given module"""

    NO_ERROR = 0
    UPDATE_READY = 1
    WRITE_FAIL = 2
    VERIFY_FAIL = 3
    CRC_ERROR = 4
    CRC_COMPLETE = 5
    ERASE_ERROR = 6
    ERASE_COMPLETE = 7

    UPDATE_FIRMWARE_MODE = 0
    CHNAGE_TYPE_MODE = 1

    def __init__(self, port=None, is_os_update=True, target_ids=(0xFFF,), conn_type="ser", local_firmware_path=None):
        self.print = True
        self.conn_type = conn_type
        self.__target_ids = target_ids
        self.response_flag = False
        self.response_error_flag = False
        self.response_error_count = 0
        self.__running = True
        self.__is_os_update = is_os_update
        self.update_in_progress = False
        self.update_module_num = 0

        self.modules_to_update_all = []
        self.modules_to_update = []
        self.modules_to_update_second_bootloader = []
        self.modules_to_update_bootloader = []

        self.modules_updated = []
        self.network_id = None
        self.network_version = None
        self.ui = None
        self.module_type = None
        self.progress = None
        self.popup_reconnect = False
        self.raise_error_message = False
        self.update_error = 0
        self.update_error_message = ""
        self.has_update_error = False
        self.update_index = 0
        self.update_mode = 0
        self.current_module_id = 0
        self.change_type_target = 0
        self.change_type_success_flag = False

        self.local_firmware_path = local_firmware_path

        self.open(port)

        self.network_uuid = None
        self.request_network_id()

        th.Thread(
            target=self.module_firmware_upload_manager, daemon=True
        ).start()

    def __del__(self):
        try:
            self.close()
        except serial.SerialException:
            self.__print("Magic del is called with an exception")

    def module_firmware_upload_manager(self):
        timeout = 0
        while timeout < 30 or len(self.modules_updated) != len(self.modules_to_update_all):
            if self.update_in_progress == True:
                timeout = 0
                time.sleep(0.1)
                continue
            if len(self.modules_to_update_second_bootloader) != 0:
                self.__conn.send_nowait(parse_message(0x2C, 0x0, 0xFFF, (1,1))) #SWU LEGACY MODE
                second_bootloader_update_module_id, second_bootloader_update_module_type = self.modules_to_update_second_bootloader[0]
                self.modules_to_update_second_bootloader.pop(0)
                updater_thread = th.Thread(
                    target=self.__update_firmware_second_bootloader,
                    args=(second_bootloader_update_module_id, second_bootloader_update_module_type, 0)
                )
                self.update_in_progress = True
                updater_thread.daemon = True
                timeout = 0
                updater_thread.start()
                time.sleep(0.1)
                continue
            if len(self.modules_to_update_bootloader) != 0:
                self.__conn.send_nowait(parse_message(0x2C, 0x0, 0xFFF, (0,0))) #SWU MODE
                bootloader_update_module_id, bootloader_update_module_type = self.modules_to_update_bootloader[0]
                self.modules_to_update_bootloader.pop(0)
                updater_thread = th.Thread(
                    target=self.__update_firmware_bootloader,
                    args=(bootloader_update_module_id, bootloader_update_module_type, 0)
                )
                self.update_in_progress = True
                updater_thread.daemon = True
                timeout = 0
                updater_thread.start()
                time.sleep(0.1)
                continue
            if len(self.modules_to_update) != 0:
                self.__conn.send_nowait(parse_message(0x2C, 0x0, 0xFFF, (0,0))) #SWU MODE
                update_module_id, update_module_type = self.modules_to_update[0]
                self.modules_to_update.pop(0)
                updater_thread = th.Thread(
                    target=self.__update_firmware,
                    args=(update_module_id, update_module_type, 0)
                )
                self.update_in_progress = True
                updater_thread.daemon = True
                timeout = 0
                updater_thread.start()
                time.sleep(0.1)
                continue
            timeout += 1
            time.sleep(0.1)

        self.modules_to_update.clear()
        self.update_index = 0
        reboot_message = self.__set_module_state(0xFFF, Module.REBOOT, Module.PNP_OFF)
        self.__conn.send_nowait(reboot_message)
        self.__print("Reboot message has been sent to all connected modules")

        time.sleep(1)

        self.__print("Module firmwares have been updated!")
        self.close()

        self.update_in_progress = False
        if self.has_update_error:
            self.update_error = -1
        else:
            self.update_error = 1

        time.sleep(0.5)
        self.reset_state()

        if self.ui:
            self.ui.update_network_esp32_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
            self.ui.update_network_esp32_button.setEnabled(True)
            self.ui.update_network_esp32_interpreter_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
            self.ui.update_network_esp32_interpreter_button.setEnabled(True)
            self.ui.change_modules_type_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
            self.ui.change_modules_type_button.setEnabled(True)
            self.ui.update_network_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
            self.ui.update_network_button.setEnabled(True)
            self.ui.update_network_bootloader_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
            self.ui.update_network_bootloader_button.setEnabled(True)
            if self.ui.is_english:
                self.ui.update_modules_button.setText("Update Modules.")
            else:
                self.ui.update_modules_button.setText("모듈 초기화")
        return

    def set_ui(self, ui):
        self.ui = ui

    def set_print(self, print):
        self.print = print

    def set_raise_error(self, raise_error_message):
        self.raise_error_message = raise_error_message

    def request_network_id(self):
        self.__conn.send_nowait(parse_message(0x28, 0x0, 0xFFF, (0xFF, 0x0F)))

    def __assign_network_id(self, sid, data, length:int):
        unpacked_data = unpack_data(data, (6, 2))
        module_uuid = unpacked_data[0]
        module_version_digits = unpacked_data[1]
        module_type = get_module_type_from_uuid(module_uuid)
        if module_type == "network":
            self.network_uuid = module_uuid
            self.network_id = sid
            module_version = [
                str((module_version_digits & 0xE000) >> 13),  # major
                str((module_version_digits & 0x1F00) >> 8),  # minor
                str(module_version_digits & 0x00FF)   # patch
            ]
            self.network_version = ".".join(module_version)

    def update_module_firmware(self, firmware_version_info = {}):
        self.has_update_error = False
        self.request_network_id()
        self.reset_state()
        self.update_mode = self.UPDATE_FIRMWARE_MODE
        self.firmware_version_info = firmware_version_info
        for target in self.__target_ids:
            self.request_to_update_firmware(target)

    def change_module_type(self, module_type):
        self.has_update_error = False
        self.request_network_id()
        self.reset_state()
        self.update_mode = self.CHNAGE_TYPE_MODE
        for target in self.__target_ids:
            self.request_to_change_module_type(target, module_type)

    def close(self):
        self.__running = False
        time.sleep(2)
        if self.recv_thread:
            self.recv_thread.join()
        self.__conn.close_conn()

    def open(self, port=None):
        self.__conn = SerTask(port=port)
        self.__conn.open_conn()
        self.name = self.__conn._bus.port
        self.__running = True
        self.recv_thread = th.Thread(target=self.__read_conn, daemon=True)
        self.recv_thread.start()

    def reset_state(self, update_in_progress: bool = False) -> None:
        self.response_flag = False
        self.response_error_flag = False
        self.response_error_count = 0
        self.update_in_progress = False

        if not update_in_progress:
            self.__print("Make sure you have connected module(s) to update")
            self.__print("Resetting firmware updater's state")
            self.update_module_num = 0
            self.modules_to_update = []
            self.modules_updated = []

    def request_to_update_firmware(self, module_id) -> None:
        firmware_update_message = self.__set_module_state(module_id, Module.UPDATE_FIRMWARE, Module.PNP_OFF)
        self.__conn.send_nowait(firmware_update_message)
        time.sleep(0.01)
        self.__conn.send_nowait(firmware_update_message)
        time.sleep(0.01)
        self.__conn.send_nowait(firmware_update_message)
        time.sleep(0.01)
        self.__print("Firmware update has been requested")

    def request_to_change_module_type(self, module_id, module_type) -> None:
        self.change_type_target = get_module_uuid_from_type(module_type)
        firmware_update_message = self.__set_module_state(module_id, Module.UPDATE_FIRMWARE, Module.PNP_OFF)
        self.__conn.send_nowait(firmware_update_message)
        time.sleep(0.01)
        self.__conn.send_nowait(firmware_update_message)
        time.sleep(0.01)
        self.__conn.send_nowait(firmware_update_message)
        time.sleep(0.01)
        self.__print("Change module type has been requested")

    def check_to_update_firmware(self, module_id: int) -> None:
        firmware_update_ready_message = self.__set_module_state(module_id, Module.UPDATE_FIRMWARE_READY, Module.PNP_OFF)
        self.__conn.send_nowait(firmware_update_ready_message)

    def add_to_waitlist(self, module_id: int, module_type: str) -> None:
        # Check if input module already exist in the list
        for curr_module_id, curr_module_type in self.modules_to_update:
            if module_id == curr_module_id:
                return

        # Check if module is already updated
        for curr_module_id, curr_module_type in self.modules_updated:
            if module_id == curr_module_id:
                return

        self.__print(f"Adding {module_type} ({module_id}) to waiting list...{' ' * 60}")

        # Add the module to the waiting list
        module_elem = module_id, module_type
        self.modules_to_update.append(module_elem)
        self.update_module_num += 1

    def add_to_module_list(self, module_id: int, module_type: str, module_section: int) -> None:
        modules_update_all_flag = True

        for curr_module_id, curr_module_type in self.modules_to_update_all:
            if module_id == curr_module_id:
                modules_update_all_flag = False
                break
        if modules_update_all_flag == True:
            module_elem = module_id, module_type
            self.modules_to_update_all.append(module_elem)

        for curr_module_id, curr_module_type in self.modules_updated:
            if module_id == curr_module_id:
                return

        if module_section == 0: # module in bootloader
            for curr_module_id, curr_module_type in self.modules_to_update:
                if module_id == curr_module_id:
                    return
            module_elem = module_id, module_type
            self.modules_to_update.append(module_elem)
            print(f"Adding {module_type} ({module_id}) to update waiting list...{' ' * 60}")
        elif module_section == 1: # module in second bootloader
            for curr_module_id, curr_module_type in self.modules_to_update_bootloader:
                if module_id == curr_module_id:
                    return
            module_elem = module_id, module_type
            self.modules_to_update_bootloader.append(module_elem)
            print(f"Adding {module_type} ({module_id}) to bootloader waiting list...{' ' * 60}")
        elif module_section == 2: # this module need to update bootloader
            for curr_module_id, curr_module_type in self.modules_to_update_second_bootloader:
                if module_id == curr_module_id:
                    return
            module_elem = module_id, module_type
            self.modules_to_update_second_bootloader.append(module_elem)
            print(f"Adding {module_type} ({module_id}) to second bootloader waiting list...{' ' * 60}")

    def change_type_module(self, module_id: int, module_type: str) -> None:
        if self.update_in_progress:
            return
        self.update_in_progress = True
        self.current_module_id = module_id
        self.update_index = 0
        updater_thread = th.Thread(
            target=self.__change_type,
            args=(module_id, module_type, 0)
        )
        updater_thread.daemon = True
        updater_thread.start()

    def update_response(self, response: bool, is_error_response: bool = False) -> None:
        if not is_error_response:
            self.response_flag = response
            self.response_error_flag = False
        else:
            self.response_flag = False
            self.response_error_flag = response

    def __update_firmware(self, module_id: int, module_type: str, module_index: int) -> None:
        is_already_updated = False
        # Check if module is already updated
        for curr_module_id, curr_module_type in self.modules_updated:
            if module_id == curr_module_id:
                is_already_updated = True

        if not is_already_updated:
            self.update_in_progress = True
            self.module_type = module_type

            # Init base root_path, utilizing local binary files
            root_path = path.join(self.local_firmware_path, module_type, self.firmware_version_info[module_type]["app"])

            if self.__is_os_update:
                bin_path = path.join(root_path, f"{module_type.lower()}.bin")

                with open(bin_path, "rb") as bin_file:
                    bin_buffer = bin_file.read()

                # Init metadata of the bytes loaded
                flash_memory_addr = 0x08000000
                bin_size = sys.getsizeof(bin_buffer)
                page_size = 0x400
                bin_begin = 0x400
                page_offset = 0x4C00
                erase_page_num = 1
                end_flash_address = 0x0800f800
                if module_type == "speaker" or module_type == "display" or module_type == "env":
                    page_size = 0x800
                    bin_begin = 0x800
                    page_offset = 0x8800
                    end_flash_address = 0x0801f800
                    erase_page_num = 2
                bin_end = bin_size - ((bin_size - bin_begin) % page_size)
                page_begin = bin_begin

                erase_error_limit = 2
                erase_error_count = 0
                crc_error_limit = 2
                crc_error_count = 0
                while page_begin < bin_end :
                    progress = 100 * page_begin // bin_end
                    self.progress = progress

                    if self.ui:
                        update_module_num = len(self.modules_to_update_all)
                        num_updated = len(self.modules_updated)
                        if self.ui.is_english:
                            self.ui.update_modules_button.setText(f"Modules update is in progress. ({num_updated} / {update_module_num})({progress}%)")
                        else:
                            self.ui.update_modules_button.setText(f"모듈 초기화가 진행중입니다. ({num_updated} / {update_module_num})({progress}%)")

                    # self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(page_begin, bin_end)} {progress}%", end="")
                    page_end = page_begin + page_size
                    curr_page = bin_buffer[page_begin:page_end]
                    # Skip current page if empty
                    if not sum(curr_page):
                        page_begin = page_begin + page_size
                        continue
                    if page_begin + page_offset + flash_memory_addr == end_flash_address:
                        page_begin = page_begin + page_size
                        continue

                    # Erase page (send erase request and receive its response)
                    erase_page_success = self.send_firmware_command(
                        oper_type="erase",
                        module_id=module_id,
                        crc_val=erase_page_num, # when page erase, crc value is replaced by data size
                        dest_addr=flash_memory_addr,
                        page_addr=page_begin + page_offset,
                    )

                    if not erase_page_success:
                        erase_error_count = erase_error_count + 1
                        if erase_error_count > erase_error_limit:
                            erase_error_count = 0
                            self.has_update_error = True
                            self.modules_updated.append((module_id, module_type))
                            break
                        continue
                    else:
                        erase_error_count = 0

                    # Copy current page data to the module's memory
                    checksum = 0
                    for curr_ptr in range(0, page_size, 8):
                        if page_begin + curr_ptr >= bin_size:
                            break

                        curr_data = curr_page[curr_ptr : curr_ptr + 8]
                        checksum = self.send_firmware_data(
                            module_id,
                            seq_num=curr_ptr // 8,
                            bin_data=curr_data,
                            crc_val=checksum,
                        )
                        time.sleep(0.001)

                    # CRC on current page (send CRC request / receive CRC response)
                    crc_page_success = self.send_firmware_command(
                        oper_type="crc",
                        module_id=module_id,
                        crc_val=checksum,
                        dest_addr=flash_memory_addr,
                        page_addr=page_begin + page_offset,
                    )

                    if crc_page_success == False:
                        crc_error_count = crc_error_count + 1
                        if crc_error_count > crc_error_limit:
                            crc_error_count = 0
                            self.has_update_error = True
                            self.modules_updated.append((module_id, module_type))
                            break
                        continue
                    else:
                        crc_error_count = 0

                    page_begin = page_begin + page_size
                    time.sleep(0.01)
            self.progress = 99
            
            verify_header = 0xAA
            if self.has_update_error:
                verify_header = 0xFF
            # self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(99, 100)} 99%")

            # Get version info from version_path, using appropriate methods
            os_version_info = self.firmware_version_info[module_type]["os"]
            os_version_info = os_version_info.lstrip("v")
            os_version_digits = [int(digit) for digit in os_version_info.split(".")]
            os_version = (
                os_version_digits[0] << 13
                | os_version_digits[1] << 8
                | os_version_digits[2]
            )

            app_version_info = self.firmware_version_info[module_type]["app"]
            app_version_info = app_version_info.lstrip("v")
            app_version_digits = [int(digit) for digit in app_version_info.split(".")]
            app_version = (
                app_version_digits[0] << 13
                | app_version_digits[1] << 8
                | app_version_digits[2]
            )

            # Set end-flash data to be sent at the end of the firmware update
            end_flash_data = bytearray(16)
            end_flash_data[0] = verify_header
            # appversion
            end_flash_data[6] = os_version & 0xFF
            end_flash_data[7] = (os_version >> 8) & 0xFF
            # app version
            end_flash_data[8] = app_version & 0xFF
            end_flash_data[9] = (app_version >> 8) & 0xFF

            for xxx in range(4):
                end_flash_data[xxx + 12] = ((0x08005000 >> (xxx * 8)) & 0xFF)
            if module_type == "speaker" or module_type == "display" or module_type == "env":
                for xxx in range(4):
                    end_flash_data[xxx + 12] = ((0x08009000 >> (xxx * 8)) & 0xFF)

            success_end_flash = self.send_end_flash_data(module_type, module_id, end_flash_data)
            if not success_end_flash:
                self.has_update_error = True
            self.__print(f"Version info (os: v{os_version_info}, app: v{app_version_info}) has been written to its firmware!")

            # Firmware update flag down, resetting used flags
            self.__print(f"Firmware update is done for {module_type} ({module_id})")
            self.reset_state(update_in_progress=True)

            self.progress = 100
            self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(1, 1)} 100%")
            self.modules_updated.append((module_id, module_type))

    def __update_firmware_bootloader(self, module_id: int, module_type: str, module_index: int) -> None:
        is_already_updated = False
        # Check if module is already updated
        for curr_module_id, curr_module_type in self.modules_updated:
            if module_id == curr_module_id:
                is_already_updated = True

        if not is_already_updated:
            self.__print("bootloader_uploade_start")
            self.update_in_progress = True
            self.module_type = module_type
            # Init base root_path, utilizing local binary files
            root_path = path.join(self.local_firmware_path, "bootloader", "e230", self.firmware_version_info[module_type]["bootloader"])
            bin_path = path.join(root_path, "bootloader_e230.bin")

            if module_type in ["speaker", "display", "env"]:
                root_path = path.join(self.local_firmware_path, "bootloader", "e103", self.firmware_version_info[module_type]["bootloader"])
                bin_path = path.join(root_path, "bootloader_e103.bin")

            if self.__is_os_update:
                # Init metadata of the bytes loaded
                flash_memory_addr = 0x08000000
                page_size = 0x400
                bin_begin = 0x0
                page_offset = 0x1000
                erase_page_num = 1
                end_flash_address = 0x0800f800
                flash_info_memory_addr = 0x08004C00
                if module_type in ["speaker", "display", "env"]:
                    page_size = 0x800
                    bin_begin = 0x0
                    page_offset = 0x1000
                    end_flash_address = 0x0801f800
                    erase_page_num = 2
                    flash_info_memory_addr = 0x08008800

                with open(bin_path, "rb") as bin_file:
                    bin_buffer = bin_file.read()

                bin_size = sys.getsizeof(bin_buffer)
                bin_end = bin_size - ((bin_size - bin_begin) % page_size)
                page_begin = bin_begin

                erase_error_limit = 2
                erase_error_count = 0
                crc_error_limit = 2
                crc_error_count = 0
                self.progress = 1
                self.has_update_error = False
                while page_begin < bin_end :
                    progress = 100 * page_begin // bin_end
                    self.progress = progress

                    if self.ui:
                        update_module_num = len(self.modules_to_update_all)
                        num_updated = len(self.modules_updated)
                        if self.ui.is_english:
                            self.ui.update_modules_button.setText(f"Modules update is in progress. ({num_updated} / {update_module_num})({progress}%)")
                        else:
                            self.ui.update_modules_button.setText(f"모듈 초기화가 진행중입니다. ({num_updated} / {update_module_num})({progress}%)")

                    # self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(page_begin, bin_end)} {progress}%", end="")
                    page_end = page_begin + page_size
                    curr_page = bin_buffer[page_begin:page_end]
                    # Skip current page if empty
                    if not sum(curr_page):
                        page_begin = page_begin + page_size
                        continue
                    if page_begin + page_offset + flash_memory_addr == end_flash_address:
                        page_begin = page_begin + page_size
                        continue
                    if page_begin + page_offset + flash_memory_addr == flash_info_memory_addr:
                        page_begin = page_begin + page_size
                        continue
                    # Erase page (send erase request and receive its response)
                    erase_page_success = self.send_firmware_command(
                        oper_type="erase",
                        module_id=module_id,
                        crc_val=erase_page_num, # when page erase, crc value is replaced by data size
                        dest_addr=flash_memory_addr,
                        page_addr=page_begin + page_offset,
                    )

                    if not erase_page_success:
                        erase_error_count = erase_error_count + 1
                        if erase_error_count > erase_error_limit:
                            erase_error_count = 0
                            self.has_update_error = True
                            break
                        continue
                    else:
                        erase_error_count = 0

                    # Copy current page data to the module's memory
                    checksum = 0
                    for curr_ptr in range(0, page_size, 8):
                        if page_begin + curr_ptr >= bin_size:
                            break

                        curr_data = curr_page[curr_ptr : curr_ptr + 8]
                        checksum = self.send_firmware_data(
                            module_id,
                            seq_num=curr_ptr // 8,
                            bin_data=curr_data,
                            crc_val=checksum,
                        )
                        time.sleep(0.001)

                    # CRC on current page (send CRC request / receive CRC response)
                    crc_page_success = self.send_firmware_command(
                        oper_type="crc",
                        module_id=module_id,
                        crc_val=checksum,
                        dest_addr=flash_memory_addr,
                        page_addr=page_begin + page_offset,
                    )

                    if crc_page_success == False:
                        crc_error_count = crc_error_count + 1
                        if crc_error_count > crc_error_limit:
                            crc_error_count = 0
                            self.has_update_error = True
                            break
                        continue
                    else:
                        crc_error_count = 0

                    page_begin = page_begin + page_size
                    time.sleep(0.01)

            verify_header = 0xAA
            if self.has_update_error:
                verify_header = 0xFF

            self.progress = 99
            # self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(99, 100)} 99%")

            # Get version info from version_path, using appropriate methods
            bootloader_version_info = self.firmware_version_info[module_type]["bootloader"]
            bootloader_version_info = bootloader_version_info.lstrip("v")

            # Set end-flash data to be sent at the end of the firmware update
            end_flash_data = bytearray(16)
            end_flash_data[0] = verify_header
            end_flash_data[6] = 0
            end_flash_data[7] = 0

            for xxx in range(4):
                if module_type in ["speaker", "display", "env"]:
                    end_flash_data[xxx + 12] = ((0x08001000 >> (xxx * 8)) & 0xFF)
                else:
                    end_flash_data[xxx + 12] = ((0x08001000 >> (xxx * 8)) & 0xFF)

            success_end_flash = self.send_end_flash_data(module_type, module_id, end_flash_data)
            if not success_end_flash:
                self.has_update_error = True

            reboot_message = self.__set_module_state(module_id, Module.REBOOT, Module.PNP_OFF)
            self.__conn.send_nowait(reboot_message)

            self.__print(f"Version info (v{bootloader_version_info}) has been written to its firmware!")

            # Firmware update flag down, resetting used flags
            self.__print(f"Firmware update is done for {module_type} ({module_id})")
            self.reset_state(update_in_progress=True)

            self.progress = 100
            self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(1, 1)} 100%")

    def __update_firmware_second_bootloader(self, module_id: int, module_type: str, module_index: int) -> None:
        is_already_updated = False
        # Check if module is already updated
        for curr_module_id, curr_module_type in self.modules_updated:
            if module_id == curr_module_id:
                is_already_updated = True

        if not is_already_updated:
            self.__print("second_bootloader_uploade_start")
            self.update_in_progress = True
            self.module_type = module_type
            # Init base root_path, utilizing local binary files
            root_path = path.join(self.local_firmware_path, "bootloader", "e230", self.firmware_version_info[module_type]["bootloader"])
            bin_path = path.join(root_path, "second_bootloader_e230.bin")

            if module_type in ["speaker", "display", "env"]:
                root_path = path.join(self.local_firmware_path, "bootloader", "e103", self.firmware_version_info[module_type]["bootloader"])
                bin_path = path.join(root_path, "second_bootloader_e103.bin")

            if self.__is_os_update:
                # Init metadata of the bytes loaded
                flash_memory_addr = 0x08000000
                page_size = 0x400
                bin_begin = 0x400
                page_offset = 0x4C00
                erase_page_num = 1
                end_flash_address = 0x0800f800
                flash_info_memory_addr = 0x08004C00
                if module_type in ["speaker", "display", "env"]:
                    page_size = 0x800
                    bin_begin = 0x800
                    page_offset = 0x8800
                    end_flash_address = 0x0801f800
                    erase_page_num = 2
                    flash_info_memory_addr = 0x08008800

                with open(bin_path, "rb") as bin_file:
                    bin_buffer = bin_file.read()

                bin_size = sys.getsizeof(bin_buffer)
                bin_end = bin_size - ((bin_size - bin_begin) % page_size)
                page_begin = bin_begin

                erase_error_limit = 2
                erase_error_count = 0
                crc_error_limit = 2
                crc_error_count = 0
                self.progress = 1
                while page_begin < bin_end :
                    progress = 100 * page_begin // bin_end
                    self.progress = progress

                    if self.ui:
                        update_module_num = len(self.modules_to_update_all)
                        num_updated = len(self.modules_updated)
                        if self.ui.is_english:
                            self.ui.update_modules_button.setText(f"Modules update is in progress. ({num_updated} / {update_module_num})({progress}%)")
                        else:
                            self.ui.update_modules_button.setText(f"모듈 초기화가 진행중입니다. ({num_updated} / {update_module_num})({progress}%)")

                    # self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(page_begin, bin_end)} {progress}%", end="")
                    page_end = page_begin + page_size
                    curr_page = bin_buffer[page_begin:page_end]
                    # Skip current page if empty
                    if not sum(curr_page):
                        page_begin = page_begin + page_size
                        continue
                    if page_begin + page_offset == end_flash_address:
                        page_begin = page_begin + page_size
                        continue
                    if page_begin + page_offset == flash_info_memory_addr:
                        page_begin = page_begin + page_size
                        continue

                    # Erase page (send erase request and receive its response)
                    erase_page_success = self.send_firmware_command(
                        oper_type="erase",
                        module_id=module_id,
                        crc_val=erase_page_num, # when page erase, crc value is replaced by data size
                        dest_addr=flash_memory_addr,
                        page_addr=page_begin + page_offset,
                    )

                    if not erase_page_success:
                        erase_error_count = erase_error_count + 1
                        if erase_error_count > erase_error_limit:
                            erase_error_count = 0
                            self.has_update_error = True
                            break
                        continue
                    else:
                        erase_error_count = 0

                    # Copy current page data to the module's memory
                    checksum = 0
                    for curr_ptr in range(0, page_size, 8):
                        if page_begin + curr_ptr >= bin_size:
                            break

                        curr_data = curr_page[curr_ptr : curr_ptr + 8]
                        checksum = self.send_firmware_data(
                            module_id,
                            seq_num=curr_ptr // 8,
                            bin_data=curr_data,
                            crc_val=checksum,
                        )
                        time.sleep(0.001)

                    # CRC on current page (send CRC request / receive CRC response)
                    crc_page_success = self.send_firmware_command(
                        oper_type="crc",
                        module_id=module_id,
                        crc_val=checksum,
                        dest_addr=flash_memory_addr,
                        page_addr=page_begin + page_offset,
                    )

                    if crc_page_success == False:
                        crc_error_count = crc_error_count + 1
                        if crc_error_count > crc_error_limit:
                            crc_error_count = 0
                            self.has_update_error = True
                            break
                        continue
                    else:
                        crc_error_count = 0

                    page_begin = page_begin + page_size
                    time.sleep(0.01)

            verify_header = 0xAA
            if self.has_update_error:
                verify_header = 0xFF

            self.progress = 99
            # self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(99, 100)} 99%")

            # Get version info from version_path, using appropriate methods
            second_bootloader_version_info = self.firmware_version_info[module_type]["bootloader"]
            second_bootloader_version_info = second_bootloader_version_info.lstrip("v")

            # Set end-flash data to be sent at the end of the firmware update
            end_flash_data = bytearray(16)
            end_flash_data[0] = verify_header
            end_flash_data[6] = 0
            end_flash_data[7] = 0

            for xxx in range(4):
                if module_type in ["speaker", "display", "env"]:
                    end_flash_data[xxx + 12] = ((0x08009000 >> (xxx * 8)) & 0xFF)
                else:
                    end_flash_data[xxx + 12] = ((0x08005000 >> (xxx * 8)) & 0xFF)

            success_end_flash = self.send_end_flash_data(module_type, module_id, end_flash_data)
            if not success_end_flash:
                self.has_update_error = True

            reboot_message = self.__set_module_state(module_id, Module.REBOOT, Module.PNP_OFF)
            self.__conn.send_nowait(reboot_message)

            self.__print(f"Version info (v{second_bootloader_version_info}) has been written to its firmware!")

            # Firmware update flag down, resetting used flags
            self.__print(f"Firmware update is done for {module_type} ({module_id})")
            self.reset_state(update_in_progress=True)

            self.progress = 100
            self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(1, 1)} 100%")

    def __change_type(self, module_id: int, module_type: str, module_index: int) -> None:
        is_already_updated = False
        # Check if module is already updated
        for curr_module_id, curr_module_type in self.modules_updated:
            if module_id == curr_module_id:
                is_already_updated = True

        if not is_already_updated:
            self.update_in_progress = True
            self.module_type = module_type

            self.modules_updated.append((module_id, module_type))

            if self.__is_os_update:
                # Init metadata of the bytes loaded
                progress = 0
                self.progress = progress

                if self.ui:
                    update_module_num = len(self.modules_to_update)
                    num_updated = len(self.modules_updated)
                    if self.ui.is_english:
                        self.ui.change_modules_type_button.setText(f"Changing modules type is in progress. ({num_updated} / {update_module_num})({progress}%)")
                    else:
                        self.ui.change_modules_type_button.setText(f"모듈 타입 변경이 진행중입니다. ({num_updated} / {update_module_num})({progress}%)")

                # send change
                uuid_changed_with_type = self.change_type_target << 32
                self.send_change_type(module_id, uuid_changed_with_type)
                time.sleep(0.5)
                self.progress = 50

                #reboot
                reboot_message = self.__set_module_state(module_id, Module.REBOOT, Module.PNP_ON)
                self.__conn.send_nowait(reboot_message)
                time.sleep(0.5)

                timeout = 0
                while self.change_type_success_flag == False:
                    if ((timeout % 10) == 0) and (timeout != 0):
                        self.send_change_type(module_id, uuid_changed_with_type)
                        time.sleep(0.1)
                        self.__conn.send_nowait(reboot_message)
                    if timeout >= 50:
                        timeout = 0
                        self.update_error_message = "Response timed-out"
                        self.has_update_error = True
                        if self.raise_error_message:
                            raise Exception(self.update_error_message)
                        break
                    timeout += 1
                    time.sleep(0.1)
                self.change_type_success_flag = False

            self.progress = 100
            self.__print(f"\rUpdating {module_type} ({module_id}) {self.__progress_bar(1, 1)} 100%")

        module_index += 1
        if module_index < len(self.modules_to_update):
            next_module_id, next_module_type = self.modules_to_update[module_index]
            self.current_module_id = next_module_id
            self.__change_type(next_module_id, next_module_type, module_index)
        else:
            # Reboot all connected modules
            time.sleep(2)
            if module_index < len(self.modules_to_update):
                next_module_id, next_module_type = self.modules_to_update[module_index]
                self.current_module_id = next_module_id
                self.__change_type(next_module_id, next_module_type, module_index)
            self.modules_to_update.clear()
            self.update_index = 0

            self.__print("Module type change have been updated!")
            self.close()

            self.update_in_progress = False
            if self.has_update_error:
                self.update_error = -1
            else:
                 self.update_error = 1

            time.sleep(0.5)
            self.reset_state()

            if self.ui:
                self.ui.update_network_esp32_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_esp32_button.setEnabled(True)
                self.ui.update_network_esp32_interpreter_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_esp32_interpreter_button.setEnabled(True)
                self.ui.update_modules_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_modules_button.setEnabled(True)
                self.ui.update_network_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_button.setEnabled(True)
                self.ui.update_network_bootloader_button.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_bootloader_button.setEnabled(True)
                if self.ui.is_english:
                    self.ui.change_modules_type_button.setText("Change Modules Type")
                else:
                    self.ui.change_modules_type_button.setText("모듈 타입 변경")

    @staticmethod
    def __set_module_state(destination_id: int, module_state: int, pnp_state: int) -> str:
        message = dict()

        message["c"] = 0x09
        message["s"] = 0
        message["d"] = destination_id

        state_bytes = bytearray(2)
        state_bytes[0] = module_state
        state_bytes[1] = pnp_state

        message["b"] = b64encode(bytes(state_bytes)).decode("utf-8")
        message["l"] = 2

        return json.dumps(message, separators=(",", ":"))

    # TODO: Use retry decorator here
    @retry(Exception)
    def send_end_flash_data(self, module_type: str, module_id: int, end_flash_data: bytearray) -> None:
        # Write end-flash data until success
        end_flash_success = False
        end_flash_address = 0x0800f800
        end_flash_erase_page_num = 1
        if module_type == "speaker" or module_type == "display" or module_type == "env":
            end_flash_address = 0x0801f800
            end_flash_erase_page_num = 2

        erase_error_limit = 2
        erase_error_count = 0
        crc_error_limit = 2
        crc_error_count = 0
        while not end_flash_success:
            # Erase page (send erase request and receive erase response)
            erase_page_success = self.send_firmware_command(
                oper_type="erase",
                module_id=module_id,
                crc_val=end_flash_erase_page_num,
                dest_addr=end_flash_address,
            )
            # TODO: Remove magic number of dest_addr above, try using flash_mem
            if not erase_page_success:
                erase_error_count = erase_error_count + 1
                if erase_error_count > erase_error_limit:
                    erase_error_count = 0
                    self.update_error_message = "Response timed-out"
                    break
                continue
            else:
                erase_error_count = 0

            # Send data
            checksum = 0
            for end_flash_ptr in range(0, len(end_flash_data), 8):
                curr_data = end_flash_data[end_flash_ptr : end_flash_ptr + 8]
                checksum = self.send_firmware_data(
                    module_id,
                    seq_num=end_flash_ptr//8,
                    bin_data=curr_data,
                    crc_val=checksum
                )
                time.sleep(0.001)

            # CRC on current page (send CRC request and receive CRC response)
            crc_page_success = self.send_firmware_command(
                oper_type="crc",
                module_id=module_id,
                crc_val=checksum,
                dest_addr=end_flash_address,
            )
            if not crc_page_success:
                crc_error_count = crc_error_count + 1
                if crc_error_count > crc_error_limit:
                    crc_error_count = 0
                    self.update_error_message = "Response timed-out"
                    break
                continue
            else:
                crc_error_count = 0

            end_flash_success = True
        # self.__print(f"End flash is written for {module_type} ({module_id})")

        return end_flash_success

    def get_firmware_command(self, module_id: int, rot_stype: int, rot_scmd: int, crc32: int, page_addr: int,) -> str:
        message = dict()
        message["c"] = 0x0D

        """ SID is 12-bits length in MODI CAN.
            To fully utilize its capacity, we split 12-bits into 4 and 8 bits.
            First 4 bits include rot_scmd information.
            And the remaining bits represent rot_stype.
        """
        message["s"] = (rot_scmd << 8) | rot_stype
        message["d"] = module_id

        """ The firmware command data to be sent is 8-bytes length.
            Where the first 4 bytes consist of CRC-32 information.
            Last 4 bytes represent page address information.
        """
        crc32_and_page_addr_data = bytearray(8)
        for i in range(4):
            crc32_and_page_addr_data[i] = crc32 & 0xFF
            crc32 >>= 8
            crc32_and_page_addr_data[4 + i] = page_addr & 0xFF
            page_addr >>= 8
        message["b"] = b64encode(bytes(crc32_and_page_addr_data)).decode("utf-8")
        message["l"] = 8

        return json.dumps(message, separators=(",", ":"))

    def get_firmware_data(self, module_id: int, seq_num: int, bin_data: bytes) -> str:
        message = dict()
        message["c"] = 0x0B
        message["s"] = seq_num
        message["d"] = module_id

        message["b"] = b64encode(bytes(bin_data)).decode("utf-8")
        message["l"] = 8

        return json.dumps(message, separators=(",", ":"))

    def change_type_command(self, did: int, changed_uuid: int,) -> str:
        message = dict()
        message["c"] = 0x0E

        message["s"] = 0
        message["d"] = did
        send_data = int.to_bytes(changed_uuid, byteorder="little", length=8)
        message["b"] = b64encode(bytes(send_data)).decode("utf-8")
        message["l"] = 8

        return json.dumps(message, separators=(",", ":"))

    def calc_crc32(self, data: bytes, crc: int) -> int:
        crc ^= int.from_bytes(data, byteorder="little", signed=False)

        for _ in range(32):
            if crc & (1 << 31) != 0:
                crc = (crc << 1) ^ 0x4C11DB7
            else:
                crc <<= 1
            crc &= 0xFFFFFFFF

        return crc

    def calc_crc64(self, data: bytes, checksum: int) -> int:
        checksum = self.calc_crc32(data[:4], checksum)
        checksum = self.calc_crc32(data[4:], checksum)
        return checksum

    def send_change_type(self, module_id: int = 0, changed_uuid_: int = 0,) -> bool:
        # Send firmware command request
        request_message = self.change_type_command(did = module_id, changed_uuid = changed_uuid_)
        self.__conn.send_nowait(request_message)

    def send_firmware_command(self, oper_type: str, module_id: int, crc_val: int, dest_addr: int, page_addr: int = 0,) -> bool:
        rot_scmd = 2 if oper_type == "erase" else 1
        # Send firmware command request
        request_message = self.get_firmware_command(module_id, 1, rot_scmd, crc_val, page_addr=dest_addr + page_addr)
        self.__conn.send_nowait(request_message)

        return self.receive_command_response()

    def receive_command_response(self, response_delay: float = 0.01, response_timeout: float = 0.5, max_response_error_count: int = 10,) -> bool:
        # Receive firmware command response
        response_wait_time = 0
        while not self.response_flag:
            # Calculate timeout at each iteration
            time.sleep(response_delay)
            response_wait_time += response_delay

            # If timed-out
            if response_wait_time > response_timeout:
                self.update_error_message = "Response timed-out"
                if self.raise_error_message:
                    raise Exception(self.update_error_message)
                return False

            # If error is raised
            if self.response_error_flag:
                self.response_error_count += 1
                if self.response_error_count > max_response_error_count:
                    self.update_error_message = "Response Errored"
                    if self.raise_error_message:
                        raise Exception(self.update_error_message)
                self.response_error_flag = False
                return False

        self.response_flag = False
        return True

    def send_firmware_data(self, module_id: int, seq_num: int, bin_data: bytes, crc_val: int) -> int:
        # Send firmware data
        data_message = self.get_firmware_data(module_id, seq_num=seq_num, bin_data=bin_data)
        self.__conn.send_nowait(data_message)

        # Calculate crc32 checksum twice
        checksum = self.calc_crc64(data=bin_data, checksum=crc_val)
        return checksum

    def __progress_bar(self, current: int, total: int) -> str:
        curr_bar = 50 * current // total
        rest_bar = 50 - curr_bar
        return f"[{'=' * curr_bar}>{'.' * rest_bar}]"

    def __read_conn(self):
        self.request_network_id()
        while self.__running:
            self.__handle_message()
            time.sleep(0.001)

    def __handle_message(self):
        try:
            msg = self.__conn.recv()
            if not msg:
                return
            ins, sid, did, data, length = decode_message(msg)
        except:
            return
        # print("received cmd is ", ins)

        command = {
            0x05: self.__assign_network_id,
            0x0A: self.__update_warning,
            0x0C: self.__update_firmware_state,
        }.get(ins)

        if self.update_mode == self.CHNAGE_TYPE_MODE:
            command = {
                0x05: self.__assign_network_id,
                0x0A: self.__update_warning_change_type,
            }.get(ins)

        if command:
            command(sid, data, length)

    def __update_firmware_state(self, sid: int, data: str, length:int):
        message_decoded = unpack_data(data, (4, 1))
        stream_state = message_decoded[1]

        if stream_state == self.CRC_ERROR:
            self.update_response(response=True, is_error_response=True)
        elif stream_state == self.CRC_COMPLETE:
            self.update_response(response=True)
        elif stream_state == self.ERASE_ERROR:
            self.update_response(response=True, is_error_response=True)
        elif stream_state == self.ERASE_COMPLETE:
            self.update_response(response=True)

    def __update_warning(self, sid: int, data: str, length:int) -> None:
        module_uuid = unpack_data(data, (6, 1))[0]
        warning_type = unpack_data(data, (6, 1))[1]

        # If warning shows current module works fine, return immediately
        if not warning_type:
            return

        module_id = sid
        module_type = get_module_type_from_uuid(module_uuid)
        if module_type == "network":
            self.network_uuid = module_uuid
        if warning_type == 1:
            self.check_to_update_firmware(module_id)
        elif warning_type == 2:
            # Note that more than one warning type 2 message can be received
            if length < 10:
                self.add_to_module_list(module_id, module_type, 2)
            else:
                module_section = unpack_data(data, (7, 1))[1]
                boot_version = unpack_data(data, (8, 2))[1]
                # print("bootloader version = ",boot_version, "\tnow section = ",module_section)
                # if module_section == 0 and boot_version != 0:
                #     self.add_to_module_list(module_id, module_type, 2)
                # else :
                self.add_to_module_list(module_id, module_type, module_section)

            # if self.update_in_progress:
            #     self.add_to_waitlist(module_id, module_type)
            # else:
            #     module_elem = module_id, module_type
            #     self.modules_to_update.append(module_elem)
            #     self.update_module(module_id, module_type)

    def __update_warning_change_type(self, sid: int, data: str, length:int) -> None:
        module_uuid = unpack_data(data, (6, 1))[0]
        module_id = sid
        module_type = get_module_type_from_uuid(module_uuid)

        # print("warning!\tuuid = ", hex(module_uuid))

        if module_type == "network":
            self.network_uuid = module_uuid

        if self.update_in_progress:
            same_flag = False
            for temp_module_id, temp_module_type in self.modules_to_update:
                if temp_module_id == module_id:
                    same_flag = True
                    break
            if same_flag == False:
                self.add_to_waitlist(module_id, module_type)
            else:
                if self.current_module_id == sid:
                    sid_module_type = module_uuid >> 32
                    if sid_module_type == self.change_type_target:
                        self.change_type_success_flag = True
        else:
            module_elem = module_id, module_type
            self.modules_to_update.append(module_elem)
            self.change_type_module(module_id, module_type)

    def __print(self, data, end="\n"):
        if self.print:
            print(data, end)

class ModuleFirmwareMultiUpdater():
    def __init__(self, local_firmware_path):
        self.update_in_progress = False
        self.ui = None
        self.list_ui = None
        self.task_end_callback = None
        self.local_firmware_path = local_firmware_path

    def set_ui(self, ui, list_ui):
        self.ui = ui
        self.list_ui = list_ui

    def set_task_end_callback(self, task_end_callback):
        self.task_end_callback = task_end_callback

    def update_module_firmware(self, modi_ports, firmware_version_info):
        self.module_uploaders = []
        self.network_uuid = []
        self.state = []
        self.wait_timeout = []
        self.update_module_num = []

        for i, modi_port in enumerate(modi_ports):
            if i > 9:
                break
            try:
                module_uploader = ModuleFirmwareUpdater(
                    port = modi_port,
                    local_firmware_path = self.local_firmware_path
                )
                module_uploader.set_print(False)
                module_uploader.set_raise_error(False)
            except:
                print("open " + modi_port + " error")
            else:
                self.module_uploaders.append(module_uploader)
                self.state.append(-1)
                self.network_uuid.append('')
                self.wait_timeout.append(0)
                self.update_module_num.append(0)

        if self.list_ui:
            self.list_ui.set_device_num(len(self.module_uploaders))
            self.list_ui.ui.close_button.setEnabled(False)

        self.update_in_progress = True

        for index, module_uploader in enumerate(self.module_uploaders):
            th.Thread(
                target=module_uploader.update_module_firmware,
                args=(firmware_version_info, ),
                daemon=True
            ).start()
            if self.list_ui:
                self.list_ui.error_message_signal.emit(index, "Waiting for network uuid")

        delay = 0.1
        while True:
            is_done = True
            total_progress = 0
            for index, module_uploader in enumerate(self.module_uploaders):
                if self.state[index] == -1:
                    if module_uploader.network_uuid is not None:
                        self.network_uuid[index] = f'0x{module_uploader.network_uuid:X}'
                        if self.list_ui:
                            self.list_ui.network_uuid_signal.emit(index, self.network_uuid[index])
                    # wait module list
                    is_done = False
                    if self.list_ui:
                        self.list_ui.error_message_signal.emit(index, "Waiting for module list")
                    if module_uploader.update_in_progress:
                        self.state[index] = 0
                    else:
                        self.wait_timeout[index] += delay
                        if self.wait_timeout[index] > 5:
                            self.wait_timeout[index] = 0
                            self.state[index] = 1
                            module_uploader.update_error = -1
                            module_uploader.update_error_message = "No modules"
                if self.state[index] == 0:
                    # get module update list (only module update)
                    is_done = False
                    if self.list_ui:
                        self.list_ui.error_message_signal.emit(index, "Updating modules")
                    if module_uploader.update_error == 0:
                        current_module_progress = 0
                        total_module_progress = 0

                        if module_uploader.progress != None and len(module_uploader.modules_to_update_all) != 0:
                            current_module_progress = module_uploader.progress
                            if len(module_uploader.modules_updated) == len(module_uploader.modules_to_update_all):
                                total_module_progress = 100
                            else:
                                total_module_progress = (module_uploader.progress + len(module_uploader.modules_updated) * 100) / (len(module_uploader.modules_to_update_all) * 100) * 100

                            total_progress += total_module_progress / len(self.module_uploaders)

                        if self.list_ui:
                            self.list_ui.current_module_changed_signal.emit(index, module_uploader.module_type)
                            self.list_ui.progress_signal.emit(index, current_module_progress, total_module_progress)
                    else:
                        self.state[index] = 1
                elif self.state[index] == 1:
                    # end
                    is_done = False
                    if module_uploader.update_error == 1:
                        total_progress += 100 / len(self.module_uploaders)
                        if self.list_ui:
                            self.list_ui.network_state_signal.emit(index, 0)
                            self.list_ui.error_message_signal.emit(index, "Update success")
                    else:
                        module_uploader.close()
                        if self.list_ui:
                            self.list_ui.network_state_signal.emit(index, -1)
                            self.list_ui.error_message_signal.emit(index, module_uploader.update_error_message)

                    if self.list_ui:
                        self.list_ui.progress_signal.emit(index, 100, 100)
                    self.state[index] = 2
                elif self.state[index] == 2:
                    total_progress += 100 / len(self.module_uploaders)
                time.sleep(0.001)

            if len(self.module_uploaders):
                # print(f"{self.__progress_bar(total_progress, 100)}", end="")
                if self.ui:
                    if self.ui.is_english:
                        self.ui.update_modules_button.setText(f"Modules update is in progress. ({int(total_progress)}%)")
                    else:
                        self.ui.update_modules_button.setText(f"모듈 초기화가 진행중입니다. ({int(total_progress)}%)")
                if self.list_ui:
                    self.list_ui.total_progress_signal.emit(total_progress)
                    self.list_ui.total_status_signal.emit("Uploading...")
            if is_done:
                break
            time.sleep(delay)

        self.update_in_progress = False

        if self.list_ui and self.task_end_callback:
            self.task_end_callback(self.list_ui)

        print("\nFirmware update is complete!!")

    def change_module_type(self, modi_ports, module_type):
        self.module_uploaders = []
        self.network_uuid = []
        self.state = []
        self.wait_timeout = []
        self.update_module_num = []

        for i, modi_port in enumerate(modi_ports):
            if i > 9:
                break
            try:
                module_uploader = ModuleFirmwareUpdater(
                    port = modi_port,
                    local_firmware_path = self.local_firmware_path
                )
                module_uploader.set_print(False)
                module_uploader.set_raise_error(False)
            except:
                print("open " + modi_port + " error")
            else:
                self.module_uploaders.append(module_uploader)
                self.state.append(-1)
                self.network_uuid.append('')
                self.wait_timeout.append(0)
                self.update_module_num.append(0)

        if self.list_ui:
            self.list_ui.set_device_num(len(self.module_uploaders))
            self.list_ui.ui.close_button.setEnabled(False)

        self.update_in_progress = True

        for index, module_uploader in enumerate(self.module_uploaders):
            th.Thread(
                target=module_uploader.change_module_type,
                args=(module_type, ),
                daemon=True
            ).start()
            if self.list_ui:
                self.list_ui.error_message_signal.emit(index, "Waiting for network uuid")

        delay = 0.1
        while True:
            is_done = True
            total_progress = 0
            for index, module_uploader in enumerate(self.module_uploaders):
                if module_uploader.network_uuid is not None:
                    self.network_uuid[index] = f'0x{module_uploader.network_uuid:X}'
                    self.list_ui.network_uuid_signal.emit(index, self.network_uuid[index])
                if self.state[index] == -1:
                    # wait module list
                    is_done = False
                    if self.list_ui:
                        self.list_ui.error_message_signal.emit(index, "Waiting for module list")
                    if module_uploader.update_in_progress:
                        self.state[index] = 0
                    else:
                        self.wait_timeout[index] += delay
                        if self.wait_timeout[index] > 5:
                            self.wait_timeout[index] = 0
                            self.state[index] = 1
                            module_uploader.update_error = -1
                            module_uploader.update_error_message = "No modules"
                if self.state[index] == 0:
                    # get module update list (only module update)
                    is_done = False
                    if self.list_ui:
                        self.list_ui.error_message_signal.emit(index, "Updating modules")
                    if module_uploader.update_error == 0:
                        current_module_progress = 0
                        total_module_progress = 0

                        if module_uploader.progress != None:
                            current_module_progress = module_uploader.progress
                            if len(module_uploader.modules_to_update) == 0:
                                total_module_progress = module_uploader.progress
                            else:
                                total_module_progress = (module_uploader.progress + (len(module_uploader.modules_updated) - 1) * 100) / (len(module_uploader.modules_to_update) * 100) * 100

                            total_progress += total_module_progress / len(self.module_uploaders)

                        if self.list_ui:
                            self.list_ui.current_module_changed_signal.emit(index, module_uploader.module_type)
                            self.list_ui.progress_signal.emit(index, current_module_progress, total_module_progress)
                    else:
                        self.state[index] = 1
                elif self.state[index] == 1:
                    # end
                    is_done = False
                    if module_uploader.update_error == 1:
                        total_progress += 100 / len(self.module_uploaders)
                        if self.list_ui:
                            self.list_ui.network_state_signal.emit(index, 0)
                            self.list_ui.error_message_signal.emit(index, "Update success")
                    else:
                        module_uploader.close()
                        if self.list_ui:
                            self.list_ui.network_state_signal.emit(index, -1)
                            self.list_ui.error_message_signal.emit(index, module_uploader.update_error_message)

                    if self.list_ui:
                        self.list_ui.progress_signal.emit(index, 100, 100)
                    self.state[index] = 2
                elif self.state[index] == 2:
                    total_progress += 100 / len(self.module_uploaders)

                time.sleep(0.001)

            if len(self.module_uploaders):
                # print(f"{self.__progress_bar(total_progress, 100)}", end="")
                if self.ui:
                    if self.ui.is_english:
                        self.ui.change_modules_type_button.setText(f"Changing modules type is in progress. ({int(total_progress)}%)")
                    else:
                        self.ui.change_modules_type_button.setText(f"모듈 타입 변경이 진행중입니다. ({int(total_progress)}%)")

                if self.list_ui:
                    self.list_ui.total_progress_signal.emit(total_progress)
                    self.list_ui.total_status_signal.emit("Uploading...")

            if is_done:
                break

            time.sleep(delay)

        self.update_in_progress = False

        if self.list_ui and self.task_end_callback:
            self.task_end_callback(self.list_ui)

        print("\nFirmware update is complete!!")

    @staticmethod
    def __progress_bar(current: int, total: int) -> str:
        curr_bar = int(50 * current // total)
        rest_bar = int(50 - curr_bar)
        return (
            f"\rFirmware Upload: [{'=' * curr_bar}>{'.' * rest_bar}] "
            f"{100 * current / total:3.1f}%"
        )