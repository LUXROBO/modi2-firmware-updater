import io
import json
import pathlib
import sys
import threading as th
import time
from base64 import b64decode, b64encode
from io import open
from os import path

import serial
import serial.tools.list_ports as stl

from modi2_multi_uploader.util.connection_util import list_modi_ports
from modi2_multi_uploader.util.message_util import (decode_message,
                                                     parse_message,
                                                     unpack_data)
from modi2_multi_uploader.util.module_util import (Module,
                                                    get_module_type_from_uuid)

def retry(exception_to_catch):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_to_catch:
                return wrapper(*args, **kwargs)

        return wrapper

    return decorator


class ESP32FirmwareUpdater(serial.Serial):
    DEVICE_READY = 0x2B
    DEVICE_SYNC = 0x08
    SPI_ATTACH_REQ = 0xD
    SPI_FLASH_SET = 0xB
    ESP_FLASH_BEGIN = 0x02
    ESP_FLASH_DATA = 0x03
    ESP_FLASH_END = 0x04

    ESP_FLASH_BLOCK = 0x200
    ESP_FLASH_CHUNK = 0x4000
    ESP_CHECKSUM_MAGIC = 0xEF

    def __init__(self, device=None):
        self.print = True
        if device != None:
            super().__init__(
                device, timeout = 0.1, baudrate = 921600
            )
        else:
            modi_ports = list_modi_ports()
            if not modi_ports:
                raise serial.SerialException("No MODI port is connected")
            for modi_port in modi_ports:
                try:
                    super().__init__(
                        modi_port.device, timeout=0.1, baudrate=921600
                    )
                except Exception:
                    self.__print('Next network module')
                    continue
                else:
                    break
            self.__print(f"Connecting to MODI network module at {modi_port.device}")

        self.__address = [0x1000, 0x8000, 0xD000, 0x10000, 0xD0000]
        self.file_path = [
            "bootloader.bin",
            "partitions.bin",
            "ota_data_initial.bin",
            "modi_ota_factory.bin",
            "esp32.bin",
        ]
        self.version = None
        self.__version_to_update = None

        self.update_in_progress = False
        self.ui = None

        self.current_sequence = 0
        self.total_sequence = 0

        self.raise_error_message = True
        self.update_error = 0
        self.update_error_message = ""

        self.network_uuid = None

    def set_ui(self, ui):
        self.ui = ui

    def set_print(self, print):
        self.print = print

    def set_raise_error(self, raise_error_message):
        self.raise_error_message = raise_error_message

    def update_firmware(self, update_interpreter=False, force=False):
        if update_interpreter:
            self.current_sequence = 0
            self.total_sequence = 1
            self.__print("get network uuid")
            self.network_uuid = self.get_network_uuid()

            self.__print("Reset interpreter...")
            self.update_in_progress = True

            self.write(b'{"c":160,"s":0,"d":18,"b":"AAMAAAAA","l":6}')
            self.__print("ESP interpreter reset is complete!!")

            self.current_sequence = 1
            self.total_sequence = 1

            time.sleep(1)
            self.update_in_progress = False
            self.flushInput()
            self.flushOutput()
            self.close()
            self.update_error = 1

            if self.ui:
                self.ui.update_stm32_modules.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_stm32_modules.setEnabled(True)
                self.ui.update_network_stm32.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_stm32.setEnabled(True)
                self.ui.update_network_esp32.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_esp32.setEnabled(True)
                if self.ui.is_english:
                    self.ui.update_network_esp32_interpreter.setText("Update Network ESP32 Interpreter")
                else:
                    self.ui.update_network_esp32_interpreter.setText("네트워크 모듈 인터프리터 초기화")
        else:
            self.__print("get network uuid")
            self.network_uuid = self.get_network_uuid()

            self.__print("Turning interpreter off...")
            self.write(b'{"c":160,"s":0,"d":18,"b":"AAMAAAAA","l":6}')

            self.update_in_progress = True
            self.__boot_to_app()
            self.__version_to_update = self.__get_latest_version()
            self.version = self.__get_esp_version()
            if self.version and self.version == self.__version_to_update:
                if not force and not self.ui:
                    response = input(f"ESP version already up to date (v{self.version}). Do you still want to proceed? [y/n]: ")
                    if "y" not in response:
                        return

            self.__print(f"Updating v{self.version} to v{self.__version_to_update}")
            firmware_buffer = self.__compose_binary_firmware()

            self.__device_ready()
            self.__device_sync()
            self.__flash_attach()
            self.__set_flash_param()
            manager = None

            self.__write_binary_firmware(firmware_buffer, manager)
            self.__print("Booting to application...")
            self.__wait_for_json()
            self.__boot_to_app()
            time.sleep(1)
            self.__set_esp_version(self.__version_to_update)
            self.__print("ESP firmware update is complete!!")

            self.current_sequence = 100
            self.total_sequence = 100
            if self.ui:
                if self.ui.is_english:
                    self.ui.update_network_esp32.setText("Network ESP32 update is in progress. (100%)")
                else:
                    self.ui.update_network_esp32.setText("네트워크 모듈 업데이트가 진행중입니다. (100%)")

            time.sleep(1.5)
            self.flushInput()
            self.flushOutput()
            self.close()
            self.update_in_progress = False
            self.update_error = 1

            if self.ui:
                self.ui.update_stm32_modules.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_stm32_modules.setEnabled(True)
                self.ui.update_network_stm32.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_stm32.setEnabled(True)
                self.ui.update_network_esp32_interpreter.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_esp32_interpreter.setEnabled(True)
                if self.ui.is_english:
                    self.ui.update_network_esp32.setText("Update Network ESP32")
                else:
                    self.ui.update_network_esp32.setText("네트워크 모듈 업데이트")

    def get_network_uuid(self):
        init_time = time.time()
        while True:
            get_uuid_pkt = b'{"c":40,"s":4095,"d":4095,"b":"//8AAAAAAAA=","l":8}'
            self.write(get_uuid_pkt)
            try:
                json_msg = json.loads(self.__wait_for_json())
                if json_msg["c"] == 0x05 or json_msg["c"] == 0x0A:
                    module_uuid = unpack_data(json_msg["b"], (6, 2))[0]
                    module_type = get_module_type_from_uuid(module_uuid)
                    if module_type == "network":
                        return module_uuid
            except json.decoder.JSONDecodeError as jde:
                self.__print("json parse error: " + str(jde))

            if time.time() - init_time > 5:
                return None

            time.sleep(0.2)

    def __device_ready(self):
        self.__print("Redirecting connection to esp device...")
        self.write(b'{"c":43,"s":0,"d":4095,"b":"AA==","l":1}')

    def __device_sync(self):
        self.__print("Syncing the esp device...")
        sync_pkt = self.__parse_pkt(
            [0x0, self.DEVICE_SYNC, 0x24, 0, 0, 0, 0, 0, 0x7, 0x7, 0x12, 0x20]
            + 32 * [0x55]
        )
        self.__send_pkt(sync_pkt, timeout=10, continuous=True)
        self.__print("Sync Complete")

    def __flash_attach(self):
        self.__print("Attaching flash to esp device..")
        attach_pkt = self.__parse_pkt(
            [0x0, self.SPI_ATTACH_REQ, 0x8] + 13 * [0]
        )
        self.__send_pkt(attach_pkt, timeout=10)
        self.__print("Flash attach Complete")

    def __set_flash_param(self):
        self.__print("Setting esp flash parameter...")
        param_data = [0] * 32
        fl_id, total_size, block_size, sector_size, page_size, status_mask = (
            0,
            2 * 1024 * 1024,
            64 * 1024,
            4 * 1024,
            256,
            0xFFFF,
        )
        param_data[1] = self.SPI_FLASH_SET
        param_data[2] = 0x18
        param_data[8:12] = int.to_bytes(fl_id, length=4, byteorder="little")
        param_data[12:16] = int.to_bytes(total_size, length=4, byteorder="little")
        param_data[16:20] = int.to_bytes(block_size, length=4, byteorder="little")
        param_data[20:24] = int.to_bytes(sector_size, length=4, byteorder="little")
        param_data[24:28] = int.to_bytes(page_size, length=4, byteorder="little")
        param_data[28:32] = int.to_bytes(status_mask, length=4, byteorder="little")
        param_pkt = self.__parse_pkt(param_data)
        self.__send_pkt(param_pkt, timeout=10)
        self.__print("Parameter set complete")

    @staticmethod
    def __parse_pkt(data):
        pkt = bytes(data)
        pkt = pkt.replace(b"\xdb", b"\xdb\xdd").replace(b"\xc0", b"\xdb\xdc")
        pkt = b"\xc0" + pkt + b"\xc0"
        return pkt

    @retry(Exception)
    def __send_pkt(self, pkt, wait=True, timeout=None, continuous=False):
        self.write(pkt)
        self.reset_input_buffer()
        if wait:
            cmd = bytearray(pkt)[2]
            init_time = time.time()
            while not timeout or time.time() - init_time < timeout:
                if continuous:
                    time.sleep(0.1)
                else:
                    time.sleep(0.01)
                recv_pkt = self.__read_slip()
                if not recv_pkt:
                    if continuous:
                        self.__send_pkt(pkt, wait=False)
                    continue
                recv_cmd = bytearray(recv_pkt)[2]
                if cmd == recv_cmd:
                    if bytearray(recv_pkt)[1] != 0x01:
                        self.update_error_message = "Packet error"
                        if self.raise_error_message:
                            raise Exception(self.update_error_message)
                        else:
                            self.update_error = -1
                    return True
                elif continuous:
                    self.__send_pkt(pkt, wait=False)
            self.__print("Sending Again...")
            self.update_error_message = "Timeout Expired!"
            if self.raise_error_message:
                raise Exception(self.update_error_message)
            else:
                self.update_error = -1

    def __read_slip(self):
        slip_pkt = b""
        while slip_pkt != b"\xc0":
            slip_pkt = self.read()
            if slip_pkt == b"":
                return b""
        slip_pkt += self.read_until(b"\xc0")
        return slip_pkt

    def __read_json(self):
        json_pkt = b""
        while json_pkt != b"{":
            json_pkt = self.read()
            if json_pkt == b"":
                return ""
            time.sleep(0.1)
        json_pkt += self.read_until(b"}")
        return json_pkt

    def __wait_for_json(self):
        json_msg = self.__read_json()
        while not json_msg:
            json_msg = self.__read_json()
            time.sleep(0.1)
        return json_msg

    def __get_esp_version(self):
        init_time = time.time()

        while True:
            get_version_pkt = b'{"c":160,"s":25,"d":4095,"b":"AAAAAAAAAA==","l":8}'
            self.write(get_version_pkt)

            try:
                json_msg = json.loads(self.__wait_for_json())
                if json_msg["c"] == 0xA1:
                    break
            except json.decoder.JSONDecodeError as jde:
                self.__print("json parse error: " + str(jde))

            if time.time() - init_time > 1:
                return None
        ver = b64decode(json_msg["b"]).lstrip(b"\x00")
        return ver.decode("ascii")

    def __set_esp_version(self, version_text: str):
        self.__print(f"Writing version info (v{version_text})")
        version_byte = version_text.encode("ascii")
        version_byte = b"\x00" * (8 - len(version_byte)) + version_byte
        version_text = b64encode(version_byte).decode("utf8")
        version_msg = (
            "{" + f'"c":160,"s":24,"d":4095,'
            f'"b":"{version_text}","l":8' + "}"
        )
        version_msg_enc = version_msg.encode("utf8")

        while True:
            self.write(version_msg_enc)
            try:
                json_msg = json.loads(self.__wait_for_json())
                if json_msg["c"] == 0xA1:
                    break
                self.__boot_to_app()
            except json.decoder.JSONDecodeError as jde:
                self.__print("json parse error: " + str(jde))

            time.sleep(0.5)

        self.__print("The version info has been set!!")

    def __compose_binary_firmware(self):
        binary_firmware = b""
        for i, bin_path in enumerate(self.file_path):
            if self.ui:
                if sys.platform.startswith("win"):
                    root_path = pathlib.PurePosixPath(pathlib.PurePath(__file__),"..", "..", "assets", "firmware", "latest", "esp32")
                else:
                    root_path = path.join(path.dirname(__file__), "..", "assets", "firmware", "latest", "esp32")

                if sys.platform.startswith("win"):
                    firmware_path = pathlib.PurePosixPath(root_path, bin_path)
                else:
                    firmware_path = path.join(root_path, bin_path)
                with open(firmware_path, "rb") as bin_file:
                    bin_data = bin_file.read()
            else:
                root_path = path.join(path.dirname(__file__), "..", "assets", "firmware", "latest", "esp32")
                firmware_path = path.join(root_path, bin_path)
                with open(firmware_path, "rb") as bin_file:
                    bin_data = bin_file.read()
            binary_firmware += bin_data
            if i < len(self.__address) - 1:
                binary_firmware += b"\xFF" * (self.__address[i + 1] - self.__address[i] - len(bin_data))
        return binary_firmware

    def __get_latest_version(self):
        root_path = path.join(path.dirname(__file__), "..", "assets", "firmware", "latest", "esp32")
        version_path = path.join(root_path, "esp_version.txt")
        with open(version_path, "r") as version_file:
            version_info = version_file.readline().lstrip("v").rstrip("\n")
        return version_info

    def __erase_chunk(self, size, offset):
        num_blocks = size // self.ESP_FLASH_BLOCK + 1
        erase_data = [0] * 24
        erase_data[1] = self.ESP_FLASH_BEGIN
        erase_data[2] = 0x10
        erase_data[8:12] = int.to_bytes(size, length=4, byteorder="little")
        erase_data[12:16] = int.to_bytes(num_blocks, length=4, byteorder="little")
        erase_data[16:20] = int.to_bytes(self.ESP_FLASH_BLOCK, length=4, byteorder="little")
        erase_data[20:24] = int.to_bytes(offset, length=4, byteorder="little")
        erase_pkt = self.__parse_pkt(erase_data)
        self.__send_pkt(erase_pkt, timeout=10)

    def __write_flash_block(self, data, seq_block):
        size = len(data)
        block_data = [0] * (size + 24)
        checksum = self.ESP_CHECKSUM_MAGIC

        block_data[1] = self.ESP_FLASH_DATA
        block_data[2:4] = int.to_bytes(size + 16, length=2, byteorder="little")
        block_data[8:12] = int.to_bytes(size, length=4, byteorder="little")
        block_data[12:16] = int.to_bytes(seq_block, length=4, byteorder="little")
        for i in range(size):
            block_data[24 + i] = data[i]
            checksum ^= 0xFF & data[i]
        block_data[4:8] = int.to_bytes(checksum, length=4, byteorder="little")
        block_pkt = self.__parse_pkt(block_data)
        self.__send_pkt(block_pkt)

    def __write_binary_firmware(self, binary_firmware: bytes, manager):
        chunk_queue = []
        self.total_sequence = len(binary_firmware) // self.ESP_FLASH_BLOCK + 1
        while binary_firmware:
            if self.ESP_FLASH_CHUNK < len(binary_firmware):
                chunk_queue.append(binary_firmware[: self.ESP_FLASH_CHUNK])
                binary_firmware = binary_firmware[self.ESP_FLASH_CHUNK :]
            else:
                chunk_queue.append(binary_firmware[:])
                binary_firmware = b""

        blocks_downloaded = 0
        self.current_sequence = blocks_downloaded
        self.__print("Start uploading firmware data...")
        for seq, chunk in enumerate(chunk_queue):
            self.__erase_chunk(len(chunk), self.__address[0] + seq * self.ESP_FLASH_CHUNK)
            blocks_downloaded += self.__write_chunk(chunk, blocks_downloaded, self.total_sequence, manager)
        if manager:
            manager.quit()
        if self.ui:
            if self.ui.is_english:
                self.ui.update_network_esp32.setText("Network ESP32 update is in progress. (99%)")
            else:
                self.ui.update_network_esp32.setText("네트워크 모듈 업데이트가 진행중입니다. (99%)")
        self.current_sequence = 99
        self.total_sequence = 100
        self.__print(f"\r{self.__progress_bar(99, 100)}")
        self.__print("Firmware Upload Complete")

    def __write_chunk(self, chunk, curr_seq, total_seq, manager):
        block_queue = []
        while chunk:
            if self.ESP_FLASH_BLOCK < len(chunk):
                block_queue.append(chunk[: self.ESP_FLASH_BLOCK])
                chunk = chunk[self.ESP_FLASH_BLOCK :]
            else:
                block_queue.append(chunk[:])
                chunk = b""
        for seq, block in enumerate(block_queue):
            self.current_sequence = curr_seq + seq
            if manager:
                manager.status = self.__progress_bar(curr_seq + seq, total_seq)
            if self.ui:
                if self.ui.is_english:
                    self.ui.update_network_esp32.setText(f"Network ESP32 update is in progress. ({int((curr_seq+seq)/total_seq*100)}%)")
                else:
                    self.ui.update_network_esp32.setText(f"네트워크 모듈 업데이트가 진행중입니다. ({int((curr_seq+seq)/total_seq*100)}%)")
            self.__print(
                f"\r{self.__progress_bar(curr_seq + seq, total_seq)}", end=""
            )
            self.__write_flash_block(block, seq)
        return len(block_queue)

    def __boot_to_app(self):
        self.write(b'{"c":160,"s":0,"d":174,"b":"AAAAAAAAAA==","l":8}')

    def __print(self, data, end="\n"):
        if self.print:
            print(data, end)

    @staticmethod
    def __progress_bar(current: int, total: int) -> str:
        curr_bar = 50 * current // total
        rest_bar = 50 - curr_bar
        return (
            f"Firmware Upload: [{'=' * curr_bar}>{'.' * rest_bar}] "
            f"{100 * current / total:3.1f}%"
        )

class ESP32FirmwareMultiUploder():
    def __init__(self):
        self.update_in_progress = False
        self.ui = None
        self.list_ui = None

    def set_ui(self, ui, list_ui):
        self.ui = ui
        self.list_ui = list_ui

    def update_firmware(self, modi_ports, update_interpreter=False, force=True):
        self.esp32_updaters = []
        self.network_uuid = []
        self.state = []

        for i, modi_port in enumerate(modi_ports):
            if i > 9:
                break
            try:
                esp32_updater = ESP32FirmwareUpdater(modi_port.device)
                esp32_updater.set_print(False)
                esp32_updater.set_raise_error(False)
            except Exception as e:
                print(e)
            else:
                self.esp32_updaters.append(esp32_updater)
                self.state.append(0)
                self.network_uuid.append('')

        if self.list_ui:
            self.list_ui.set_device_num(len(self.esp32_updaters))
            self.list_ui.ui.close_button.setEnabled(False)

        self.update_in_progress = True

        for index, esp32_updater in enumerate(self.esp32_updaters):
            th.Thread(
                target=esp32_updater.update_firmware,
                args=(update_interpreter, force),
                daemon=True
            ).start()

        delay = 0.1
        while True:
            is_done = True
            current_sequence = 0
            total_sequence = 0

            for index, esp32_updater in enumerate(self.esp32_updaters):
                if self.state[index] == 0:
                    # wait for network uuid
                    is_done = False
                    if esp32_updater.update_in_progress:
                        if esp32_updater.network_uuid:
                            self.network_uuid[index] = f'0x{esp32_updater.network_uuid:X}'
                            self.state[index] = 1
                            if self.list_ui:
                                self.list_ui.network_uuid_signal.emit(index, self.network_uuid[index])
                        else:
                            self.state[index] = 2
                            esp32_updater.update_error = -1
                            esp32_updater.update_error_message = "Not response network uuid"
                elif self.state[index] == 1:
                    # update modules
                    if esp32_updater.update_error == 0:
                        is_done = is_done & False
                        current = esp32_updater.current_sequence
                        total = esp32_updater.total_sequence

                        value = 0 if total == 0 else current / total * 100.0

                        current_sequence += current
                        total_sequence += total

                        if self.list_ui:
                            self.list_ui.progress_signal.emit(index, value)
                    else:
                        self.state[index] = 2
                elif self.state[index] == 2:
                    # end
                    current_sequence += esp32_updater.total_sequence
                    total_sequence += esp32_updater.total_sequence
                    if esp32_updater.update_error == 1:
                        if self.list_ui:
                            self.list_ui.network_state_signal.emit(index, 0)
                            self.list_ui.progress_signal.emit(index, 100)
                    else:
                        if self.list_ui:
                            self.list_ui.network_state_signal.emit(index, -1)
                            self.list_ui.error_message_signal.emit(index, esp32_updater.update_error_message)

                    self.state[index] = 3
                elif self.state[index] == 3:
                    total_sequence += 100

            if total_sequence != 0:
                if self.ui:
                    if update_interpreter:
                        if self.ui.is_english:
                            self.ui.update_network_esp32_interpreter.setText(
                                f"Network ESP32 Interpreter reset is in progress. "
                                f"({int(current_sequence/total_sequence*100)}%)"
                            )
                        else:
                            self.ui.update_network_esp32_interpreter.setText(
                                f"네트워크 모듈 인터프리터 초기화가 진행중입니다. "
                                f"({int(current_sequence/total_sequence*100)}%)"
                            )
                    else:
                        if self.ui.is_english:
                            self.ui.update_network_esp32.setText(
                                f"Network ESP32 update is in progress. "
                                f"({int(current_sequence/total_sequence*100)}%)"
                            )
                        else:
                            self.ui.update_network_esp32.setText(
                                f"네트워크 모듈 업데이트가 진행중입니다. "
                                f"({int(current_sequence/total_sequence*100)}%)"
                            )

                if self.list_ui:
                    self.list_ui.total_progress_signal.emit(current_sequence / total_sequence * 100.0)
                    self.list_ui.total_status_signal.emit("Uploading...")

                print(f"\r{self.__progress_bar(current_sequence, total_sequence)}", end="")

            if is_done:
                break

            time.sleep(delay)

        self.update_in_progress = False

        if self.list_ui:
            self.list_ui.ui.close_button.setEnabled(True)
            self.list_ui.total_status_signal.emit("Complete")

        if update_interpreter:
            if self.ui:
                self.ui.update_stm32_modules.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_stm32_modules.setEnabled(True)
                self.ui.update_network_stm32.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_stm32.setEnabled(True)
                self.ui.update_network_stm32_bootloader.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_stm32_bootloader.setEnabled(True)
                self.ui.update_network_esp32.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_esp32.setEnabled(True)
                if self.ui.is_english:
                    self.ui.update_network_esp32_interpreter.setText("Update Network ESP32 Interpreter")
                else:
                    self.ui.update_network_esp32_interpreter.setText("네트워크 모듈 인터프리터 초기화")
        else:
            if self.ui:
                self.ui.update_stm32_modules.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_stm32_modules.setEnabled(True)
                self.ui.update_network_stm32.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_stm32.setEnabled(True)
                self.ui.update_network_stm32_bootloader.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_stm32_bootloader.setEnabled(True)
                self.ui.update_network_esp32_interpreter.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
                self.ui.update_network_esp32_interpreter.setEnabled(True)
                if self.ui.is_english:
                    self.ui.update_network_esp32.setText("Update Network ESP32")
                else:
                    self.ui.update_network_esp32.setText("네트워크 모듈 업데이트")

        print("\nESP firmware update is complete!!")

    @staticmethod
    def __progress_bar(current: int, total: int) -> str:
        curr_bar = int(50 * current // total)
        rest_bar = int(50 - curr_bar)
        return (
            f"Firmware Upload: [{'=' * curr_bar}>{'.' * rest_bar}] "
            f"{100 * current / total:3.1f}%"
        )