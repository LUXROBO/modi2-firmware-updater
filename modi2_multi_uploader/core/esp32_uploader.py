import io
import json
import pathlib
import sys
import threading as th
import time
import zlib
import struct
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

from modi2_multi_uploader.core.esp_tool import ESP32FirmwareUpdater

# STUB_CODE = eval(zlib.decompress(b64decode(b"""
# eNqNWntz3LYR/yoUrXfkDMDjkaDHre8uyunhtJGcRJYyN01JkIwzcTWyfKnOqtzPXuyLAHmXpH9QAkE8dhe7v33g/rO3bFbLvRdRtbdYKeMetVi16avFStvgBRrdS5kuVk3lXmoY5r9kU2huuXbpnnaxsiqCHlg1\
# cd/aote97/6kUbRcrAq3VZO418w9Y7+bUjBrTLOMdv+z3gqOFFjbkWMMUV9Cn3JLNsqzo6q4BRJcb+6GwhoprAOU6t6CBQ3TtetVAdcmYtZbE7LqKIf59YAoR4yjAEYatX11Sl9xZPn/jBzuDo9WUXcS0eBM8DFC\
# UQPissJeRUsqS9LwGzOnSFUVCLgYUFgk76jhe1DUV5/WWXErPrneBLiJVRTR0WxiR6kJ0dsIsW6cO5ei9KQ0dSA4OySrGDDUp2rznvxo3zbKz7aKNRoWkAcHptFAvZGaJGb+sq9Aa4ET4zlpSvpajkXAZkbnAKPg\
# v04vRRFzVuTKxEDTiKzK2tEliRMXtaLp8cSN1XrH9Y+Ck1PcBrZwhaCzf+4j96VOel/e2N4pX8Ooq9+I7MkI+ouZic+/Oov7wi1UIDhlJtwygWxx2zR8n0ykdUrdOKdIu6VElystQo3QrB3L1Yg3FhmP+8hQBO0O\
# DAo+YhPqcZUcBDbMkixYk3sjC4AE4xkuFB2cdudqC6Lacl83ySbXPMNRWVQhZiVnQ5MKNkDVLz01spmIFNs5WMCcB6ee84axsoQ2ayPuH5qKRdCpgqm4HqgkrAmwoNQTLQBftFug0XOYFNpRqFO3oVyLxbJbpt9/\
# 25+1JKLrgFBDxrHsCYcF2Tfqi+fgLxhGpqQYbXudXowsWyBoyugaDO3H7y4WiylBP812mtQwphhz7ASW8QmghW0T42i7Cf0XUYUoBTarU+BxBGBXJRHrIttW6IOMfRGTRtr04Pt9mPgiPoB/+ymIyhnYECtNH+jR\
# aO7IUbblq9Nt5B/GxySJktXLUVszdpY14Z0JMNRT9Rc4EISihMTRyAlo0sky8UoP/VoQRDdMh1hc4vVOTGng5EpsRWF/8otY4haTDjrZrmNaKMhSPWOAGzppgGuBbCUQAsvAWSKlCZFB7J3CAGDOTsXNJaGbxh59\
# YJDCFE49Phypl1P2psnBdXHKOoIK/BykaUCapZz0eEjlERHRuT8QAo9VfFoJmyMMa+gI4HtdsUiqDSKRMZZVfNRfG+fKmobXyf9gnZrHpOtj1j0rcfJCwrfEf0P14XddxQxPFXs8oKZNfy/ckfZ1+OJAqUbMnwBq\
# fMkGAMjVdYObBH7dS7a1RTTUmlU3CMF6tpl5bLv07qNC47n4yq1oa/bmckKBlwlXau2hH1yx8a2RMBpOPI/Jx15ZiibRDthcq2A2IHFZMuw3Gw4Q+osgXqhkzo7XUlKPrB8IKYU6a3//gL16WObD2j9Tj/fh4b0L\
# X+7Cl2X4sgpfQKI/M/jVqjMe2O8dm9FW6aPWMILVZXtGfGpEtcqLEe03PVrc3sBCs5aHbDzTS58jIM+1rP4DeKXxW3dAhrU8y1lONe2L4zeYqw9uPwTHhUQ+XiJJ851gJB7b5CPJXTNCS75DOna3Eh3NIVASP2Q3\
# +iE3qfxAnV1qMH6Dru3xAwOIDXIJDCnceVW4di3oj4e/49Mz2l4o+ie4VCajMkMyHuPH45xQtWY2a5T8xXIzmyYHd5yTXMUrKDrKW+B4/p6X0aE44cu+F6V89IRccazVUDxUMqUIXNl7Wqaq3Nec9wPgwrAT2M++\
# Xix/BMHAjNeCcz9wijny9lu2vEdOwYM17ddAwptd2AIkAUlv8pZEAlSAJReoI06SFUgSFBdtn5kp2g32P/ZpE65gNmEBnWsjKDSWwzxCB6bpCP/IsDHWta++PZ2eEbVcDICYETClAhxOeT68KF9KwBQhfTXIsDak\
# Z6CopucSJr38cRiMIkkEvN2Lk9lesEIa1DBEiYSEgA3JLHmRyqc4T+9464ZR6Vpiysn7Q/RGJmGnpB2+UMtaan1D/yDAHPMygKAFsbMib6YoAHLe67pDu2/IkwPauSmak9C66ez3Ni4RyDi6Ub/nIGAWwo0mh4nT\
# O0cwA6+pXsc5oEa+Q2dJO7wmk7A64vASg4dGQAQ2A41vtqQxlQTz8NmwtlJ1huhGAyrDOqgg+Px45j1svabiU0HgN6TgQHlYTXIqfBH7GPOAA3r9380oXJsNIrLZWpUqoaOqSjIlm04gDQaXiRDbJfQR1cYgOlVs\
# cptxh5xKxfzV+py3DDoRjyyJB0LtUoeIt9n/OuorG8L64QhCIDhz0O06+aLHFgTR2f0atyNhp+sFpzSaTYHnGTs7jYP2sFPfXy6WN5e7lMODE9A2f6AVwFegjiGBMnt0zw2sFR3DGnfHUYuN07jbF0L09Oxy3o9V\
# tN2eXULEBtAldQygGLSJ9BQobSg5b9s/3vQDWY1zcXcADSeE0joJ4x1YKvWuATqbZkc6d8iLte3cq6xS9z1BoeEVOT1IQEYQrtRD8ff2ZwkhSCdRQbKHqOXBNvsgnScgyhZhLZm/ZaFku9BoT7BT8KV96xetEPrm\
# cadCWEAL6QGtx7ajB7d48P3ondScnICCHItmzUm3ZMmqt+RcUIuDsEIOb7Cxyma062FLoqddv5XhiyUSxAAB0R14OCj79MXJqT3QqztFoX37273ttOgk7P5Xlwug3UpZBvOhZCirRASlw2GKhuh8O+jU0qmJOJX2\
# PVc3cDTk6CxIxGFAOhxwylEayuNe9HhOMYecis6vto8AMJabcukloRVwjaFdR9guFe2QWlyFjrFE0cxAkZJ7+Du6A6uPfK2qSq9IFQC4wFmUGALfHZM7xzJTyYGcCfwvPJCJG/1uLUp7Ad73nv0O5A4le3kHgXs+\
# 2O7yzq5UdkVVnbaZe8GX/LRYOVxLB68OKUc1+rUUVB8k5znnUJi2fzBUFrJByj1g5XojK8U6K1cU3oLMbHbH+EHgIyfBoGFseOpsGTlRYUo+OrB34M9mNlhLaf7UrZVJASYmFkpsJAStle5ChC493rRSKP5Co/dE\
# BUkvYJ1IGElOSC9oymfe2YAnh7I3aRnrDFVvfyPltNkqUGcAzSo9OoVoRx+xfEMLoI1K2QhJXyV+q7slIRMgYMM10xK9yJRwHw4BIudG39QzsLsvPm3T0gWozOgziiP7tase37OX5hNxiy3DE8ywangLer+6gaXj\
# GbsOiAELLiCH2XWhHt2fkTh7QQCIDM2wxlKSuaPJV6TuUJfGfrwoUSeHXMaUcsxYPCKXlWGs1hNoRDN/pp2Gka9kxU67ITm7UaxxqOOoY4YDUXDDBZbfEWG+C+/z6gDGE7HNvsCWFEAUJpV+c0XlRw1QmRzjwX4P\
# tH4TBgc0JjQPzaipU8FvQU6MPw2YIyiHhRC6wqoZXsRostoharqlbzv1nM9CqN09lh1eSVoRc0o89kYyXBD9YxtkNiXIo6/UgBBo3s0E9H9K0U6R/G1x+0S1XdSMJtAMEIMoORgenAd431oHpcSmTwrpPeXsVq8O\
# uMhdYFzCVVwAKryfSrYW97ukCBgiSWG3SZ5jjecJ2oCeGoGuDIu/LnC4B009JgWw7EurPKWgWnV19vY4iJjMJoNX82e9Q/DQZLOIta7OxbDfrGK+PwQpYt2h+QRvn1ljMn/3XclNWeM1CQO0qjNhytOx9ojeeQSB\
# wG/QuKNt9NBF2+zqxisERvGNfCrwesYdx8nL8wn16TTUAfSdjlSp3LfdVcsjSbIwv7x+wJ1vmbT2EZz7HaX5Vp3kRI/ODihexRiuolIUZr7Zo4+pNVQ+wP/ofMqVgWbF0IGfO+O8CaKFcioxwB0BuhnddHSTMO7k\
# oj4pQRMAhQ3XwhpQLNJLN6SRDw0BcNteSaWpS0bELbWYdUxO0NhJceafMGatfThLtZzdwA82nGeZwBCdCuw9cEaDwz5CP6yMMIu8B99V9oKDZMqAAzyrE6TqW3lN8fXjnK9Qmn48SPgjBZ4GlFWMF9SlXDPaLQqq\
# UDxSNWqG6SvZc3QMMQHkrRqxGbPYaDsiVwEuBDeX86kqskXDRewhWKDLGvFFYUfxOrZh/huwWWOUAaTIHboPQEwM59BwIGutn1mJ+xrNwjyOyET3VVURDcOqKxNo+W61Gd/6igfm+M2fJIa/gp8K7RzvUNSx3C+m\
# VNgDTNJc2ANtKOROKbwOKZKSQLIZ38hl1FZ3w7PHtwuZ2DfC7h5BLZgnZO/N+HLDFSRNBu5tKtwzx3j1teHYdHbeFfzxOvItXEfm53gdme/nE+BZnXFMWQo+kajYX3fSehBdeoC4gLZ2g23O5ULLYJrJbS6G983W\
# rxwE0CX8fUkm3WBNRWE9K9vfFTQBHjE1xGT6hXdrJVtGg26teePvZa3e+olzkIImgpaCJpb6H1yN5XsaKyUDS3EStg1dg1Ep6ud1IVoMAiqzC9t98I6zZIW0eOMNXyV9qMiBlnDbbLgQCyMBTkDIlDZEdIHOr1gK\
# jPyKWDAsySfhrZ6IuKH0s2z4blR+HRHcKorMKATY+YnVkOm2KJ0D/DmS/hIOZ98QxIMOYlDaam5wxFpnB1xDB62Dq5Oa9YXqawdsP6hl+dn1PPg9iH1JqEWY/ETy1WwwRTvdhrmioebge0BxAQKjt8KvxcH1/N/y\
# dT++SggDyy7oOt6AXOCUEfH1X9e/Gj0dds5vux1AxaEAAL/p8Ju8/DN4zNYHYLurkbCS9W/Qut+ZiS52WQJX6uinIHTzbTFw4vt8DAdzHxcptLTRE3kdHyzu0nCV78Z0AmaQzq7dJKuDZ7IvWmgsC7dQ9KE94+5G\
# es//WItIw9HP+V5n0211LT8iE9ay3tTYk9KX1d5RhD9m/OnjsryHnzRqlafjxAkxdV+a2+X9p65Tp0XmOutyWQa/feSa/x5/CRcaZWo8TtPP/wO9arcm\
# """)))

# def hexify(s, uppercase=True):
#     format_str = '%02X' if uppercase else '%02x'
#     return ''.join(format_str % c for c in s)

# class FatalError(RuntimeError):
#     """
#     Wrapper class for runtime errors that aren't caused by internal bugs, but by
#     ESP8266 responses or input content.
#     """
#     def __init__(self, message):
#         RuntimeError.__init__(self, message)

#     @staticmethod
#     def WithResult(message, result):
#         """
#         Return a fatal error object that appends the hex values of
#         'result' as a string formatted argument.
#         """
#         message += " (result was %s)" % hexify(result)
#         return FatalError(message)

def retry(exception_to_catch):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_to_catch:
                return wrapper(*args, **kwargs)

        return wrapper

    return decorator


# class ESP32FirmwareUpdater(serial.Serial):
#     DEVICE_READY = 0x2B
#     DEVICE_SYNC = 0x08
#     SPI_ATTACH_REQ = 0xD
#     SPI_FLASH_SET = 0xB
#     ESP_FLASH_BEGIN = 0x02
#     ESP_FLASH_DATA = 0x03
#     ESP_FLASH_END = 0x04
#     ESP_MEM_BEGIN = 0x05
#     ESP_MEM_END = 0x06
#     ESP_MEM_DATA = 0x07
#     ESP_CHANGE_BAUDRATE = 0x0F

#     ESP_FLASH_BLOCK = 0x200
#     ESP_FLASH_CHUNK = 0x4000
#     ESP_CHECKSUM_MAGIC = 0xEF

#     ESP_RAM_BLOCK = 0x1800

#     def __init__(self, device=None):
#         self.print = True
#         if device != None:
#             super().__init__(
#                 device, timeout = 0.1, baudrate = 921600
#             )
#         else:
#             modi_ports = list_modi_ports()
#             if not modi_ports:
#                 raise serial.SerialException("No MODI port is connected")
#             for modi_port in modi_ports:
#                 try:
#                     super().__init__(
#                         modi_port.device, timeout=0.1, baudrate=921600
#                     )
#                 except Exception:
#                     self.__print('Next network module')
#                     continue
#                 else:
#                     break
#             self.__print(f"Connecting to MODI network module at {modi_port.device}")

#         self.__address = [0xD000, 0x1000, 0x8000, 0x00220000, 0x00010000]
#         self.file_path = [
#             "ota_data_initial.bin",
#             "bootloader.bin",
#             "partitions.bin",
#             "modi_ota_factory.bin",
#             "esp32.bin",
#         ]
#         self.version = None
#         self.__version_to_update = None

#         self.update_in_progress = False
#         self.ui = None

#         self.current_sequence = 0
#         self.total_sequence = 0

#         self.raise_error_message = True
#         self.update_error = 0
#         self.update_error_message = ""

#         self.network_uuid = None

#     def set_ui(self, ui):
#         self.ui = ui

#     def set_print(self, print):
#         self.print = print

#     def set_raise_error(self, raise_error_message):
#         self.raise_error_message = raise_error_message

#     def update_firmware(self, update_interpreter=False, force=False):
#         if update_interpreter:
#             self.current_sequence = 0
#             self.total_sequence = 1
#             self.__print("get network uuid")
#             self.network_uuid = self.get_network_uuid()

#             self.__print("Reset interpreter...")
#             self.update_in_progress = True

#             self.write(b'{"c":160,"s":0,"d":18,"b":"AAMAAAAA","l":6}')
#             self.__print("ESP interpreter reset is complete!!")

#             self.current_sequence = 1
#             self.total_sequence = 1

#             time.sleep(1)
#             self.update_in_progress = False
#             self.flushInput()
#             self.flushOutput()
#             self.close()
#             self.update_error = 1

#             if self.ui:
#                 self.ui.update_stm32_modules.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
#                 self.ui.update_stm32_modules.setEnabled(True)
#                 self.ui.update_network_stm32.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
#                 self.ui.update_network_stm32.setEnabled(True)
#                 self.ui.update_network_esp32.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
#                 self.ui.update_network_esp32.setEnabled(True)
#                 if self.ui.is_english:
#                     self.ui.update_network_esp32_interpreter.setText("Update Network ESP32 Interpreter")
#                 else:
#                     self.ui.update_network_esp32_interpreter.setText("네트워크 모듈 인터프리터 초기화")
#         else:
#             self.__print("get network uuid")
#             self.network_uuid = self.get_network_uuid()

#             self.__print("Turning interpreter off...")
#             self.write(b'{"c":160,"s":0,"d":18,"b":"AAMAAAAA","l":6}')

#             self.update_in_progress = True
#             self.__boot_to_app()
#             self.__version_to_update = self.__get_latest_version()
#             self.version = self.__get_esp_version()
#             if self.version and self.version == self.__version_to_update:
#                 if not force and not self.ui:
#                     response = input(f"ESP version already up to date (v{self.version}). Do you still want to proceed? [y/n]: ")
#                     if "y" not in response:
#                         return

#             self.__print(f"Updating v{self.version} to v{self.__version_to_update}")
#             firmware_buffer = self.__compose_binary_firmware()

#             self.__device_ready()
#             self.__device_sync()
#             # self.__device_stub()
#             # self.__device_baudrate(921600)
#             self.__flash_attach()
#             self.__set_flash_param()
#             manager = None

#             self.__write_binary_firmware(firmware_buffer, manager)
#             self.__print("Booting to application...")
#             self.__wait_for_json()
#             self.__boot_to_app()
#             time.sleep(1)
#             self.__set_esp_version(self.__version_to_update)
#             self.__print("ESP firmware update is complete!!")

#             self.current_sequence = 100
#             self.total_sequence = 100
#             if self.ui:
#                 if self.ui.is_english:
#                     self.ui.update_network_esp32.setText("Network ESP32 update is in progress. (100%)")
#                 else:
#                     self.ui.update_network_esp32.setText("네트워크 모듈 업데이트가 진행중입니다. (100%)")

#             time.sleep(1.5)
#             self.flushInput()
#             self.flushOutput()
#             self.close()
#             self.update_in_progress = False
#             self.update_error = 1

#             if self.ui:
#                 self.ui.update_stm32_modules.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
#                 self.ui.update_stm32_modules.setEnabled(True)
#                 self.ui.update_network_stm32.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
#                 self.ui.update_network_stm32.setEnabled(True)
#                 self.ui.update_network_esp32_interpreter.setStyleSheet(f"border-image: url({self.ui.active_path}); font-size: 16px")
#                 self.ui.update_network_esp32_interpreter.setEnabled(True)
#                 if self.ui.is_english:
#                     self.ui.update_network_esp32.setText("Update Network ESP32")
#                 else:
#                     self.ui.update_network_esp32.setText("네트워크 모듈 업데이트")

#     def get_network_uuid(self):
#         init_time = time.time()
#         while True:
#             get_uuid_pkt = b'{"c":40,"s":0,"d":4095,"b":"//8AAAAAAAA=","l":8}'
#             self.write(get_uuid_pkt)
#             try:
#                 json_msg = json.loads(self.__wait_for_json())
#                 if json_msg["c"] == 0x05 or json_msg["c"] == 0x0A:
#                     module_uuid = unpack_data(json_msg["b"], (6, 2))[0]
#                     module_type = get_module_type_from_uuid(module_uuid)
#                     if module_type == "network":
#                         return module_uuid
#             except json.decoder.JSONDecodeError as jde:
#                 self.__print("json parse error: " + str(jde))

#             if time.time() - init_time > 5:
#                 return None

#             time.sleep(0.2)

#     def __device_ready(self):
#         self.__print("Redirecting connection to esp device...")
#         self.write(b'{"c":43,"s":0,"d":4095,"b":"AA==","l":1}')

#     def __device_sync(self):
#         self.__print("Syncing the esp device...")
#         sync_pkt = self.__parse_pkt(
#             [0x0, self.DEVICE_SYNC, 0x24, 0, 0, 0, 0, 0, 0x7, 0x7, 0x12, 0x20]
#             + 32 * [0x55]
#         )
#         self.__send_pkt(sync_pkt, timeout=10, continuous=True)
#         self.__print("Sync Complete")

#     def __device_stub(self):
#         self.__print("Stubing the esp device...")
#         stub = STUB_CODE

#         self.__print("Uploading stub...")
#         for field in ['text', 'data']:
#             if field in stub:
#                 offs = stub[field + "_start"]
#                 length = len(stub[field])
#                 blocks = (length + self.ESP_RAM_BLOCK - 1) // self.ESP_RAM_BLOCK
#                 self.__print("asdasd")
#                 self.__mem_begin(length, blocks, self.ESP_RAM_BLOCK, offs)
#                 for seq in range(blocks):
#                     from_offs = seq * self.ESP_RAM_BLOCK
#                     to_offs = from_offs + self.ESP_RAM_BLOCK
#                     self.__mem_block(stub[field][from_offs:to_offs], seq)
#         self.__print("Running stub...")
#         self.__mem_finish(stub['entry'])

#         # p = self.read()
#         # if p != b'OHAI':
#         #     raise FatalError("Failed to start stub. Unexpected response: %s" % p)
#         # self.__print("Stub running...")

#     def __device_baudrate(self, baudrate):
#         print("Changing baud rate to %d" % baudrate)
#         # stub takes the new baud rate and the old one
#         op = self.ESP_CHANGE_BAUDRATE
#         block_data = struct.pack('<II', baudrate, 115200)
#         checksum = 0
#         block = struct.pack(b'<BBHI', 0x00, op, len(block_data), checksum) + block_data
#         block_pkt = self.__parse_pkt(block)
#         self.__send_pkt(block_pkt)

#     def __mem_begin(self, size, blocks, blocksize, offset):
#         op = self.ESP_MEM_BEGIN
#         block_data = struct.pack('<IIII', size, blocks, blocksize, offset)
#         checksum = 0
#         block = struct.pack(b'<BBHI', 0x00, op, len(block_data), checksum) + block_data
#         block_pkt = self.__parse_pkt(block)
#         self.__send_pkt(block_pkt)

#     def __mem_block(self, data, seq):
#         op = self.ESP_MEM_DATA
#         block_data = struct.pack('<IIII', len(data), seq, 0, 0) + data
#         checksum = self.ESP_CHECKSUM_MAGIC
#         for i in range(len(data)):
#             checksum ^= 0xFF & data[i]
#         block = struct.pack(b'<BBHI', 0x00, op, len(block_data), checksum) + block_data
#         block_pkt = self.__parse_pkt(block)
#         self.__send_pkt(block_pkt)

#     def __mem_finish(self, entrypoint=0):
#         op = self.ESP_MEM_END
#         block_data = struct.pack('<II', int(entrypoint == 0), entrypoint)
#         checksum = 0
#         block = struct.pack(b'<BBHI', 0x00, op, len(block_data), checksum) + block_data
#         block_pkt = self.__parse_pkt(block)
#         self.__send_pkt(block_pkt, timeout=3)

#     def __flash_attach(self):
#         self.__print("Attaching flash to esp device..")
#         attach_pkt = self.__parse_pkt(
#             [0x0, self.SPI_ATTACH_REQ, 0x8] + 13 * [0]
#         )
#         self.__send_pkt(attach_pkt, timeout=10)
#         self.__print("Flash attach Complete")

#     def __set_flash_param(self):
#         self.__print("Setting esp flash parameter...")
#         param_data = [0] * 32
#         fl_id, total_size, block_size, sector_size, page_size, status_mask = (
#             0,
#             2 * 1024 * 1024,
#             64 * 1024,
#             4 * 1024,
#             256,
#             0xFFFF,
#         )
#         param_data[1] = self.SPI_FLASH_SET
#         param_data[2] = 0x18
#         param_data[8:12] = int.to_bytes(fl_id, length=4, byteorder="little")
#         param_data[12:16] = int.to_bytes(total_size, length=4, byteorder="little")
#         param_data[16:20] = int.to_bytes(block_size, length=4, byteorder="little")
#         param_data[20:24] = int.to_bytes(sector_size, length=4, byteorder="little")
#         param_data[24:28] = int.to_bytes(page_size, length=4, byteorder="little")
#         param_data[28:32] = int.to_bytes(status_mask, length=4, byteorder="little")
#         param_pkt = self.__parse_pkt(param_data)
#         self.__send_pkt(param_pkt, timeout=10)
#         self.__print("Parameter set complete")

#     @staticmethod
#     def __parse_pkt(data):
#         pkt = bytes(data)
#         pkt = pkt.replace(b"\xdb", b"\xdb\xdd").replace(b"\xc0", b"\xdb\xdc")
#         pkt = b"\xc0" + pkt + b"\xc0"
#         return pkt

#     @retry(Exception)
#     def __send_pkt(self, pkt, wait=True, timeout=None, continuous=False):
#         self.write(pkt)
#         self.reset_input_buffer()
#         if wait:
#             cmd = bytearray(pkt)[2]
#             init_time = time.time()
#             while not timeout or time.time() - init_time < timeout:
#                 if continuous:
#                     time.sleep(0.1)
#                 else:
#                     time.sleep(0.01)
#                 recv_pkt = self.__read_slip()
#                 if not recv_pkt:
#                     if continuous:
#                         self.__send_pkt(pkt, wait=False)
#                     continue
#                 recv_cmd = bytearray(recv_pkt)[2]
#                 if cmd == recv_cmd:
#                     if bytearray(recv_pkt)[1] != 0x01:
#                         self.update_error_message = "Packet error"
#                         if self.raise_error_message:
#                             raise Exception(self.update_error_message)
#                         else:
#                             self.update_error = -1
#                     return True
#                 elif continuous:
#                     self.__send_pkt(pkt, wait=False)
#             self.__print("Sending Again...")
#             self.update_error_message = "Timeout Expired!"
#             if self.raise_error_message:
#                 raise Exception(self.update_error_message)
#             else:
#                 self.update_error = -1

#     def __read_slip(self):
#         slip_pkt = b""
#         while slip_pkt != b"\xc0":
#             slip_pkt = self.read()
#             if slip_pkt == b"":
#                 return b""
#         slip_pkt += self.read_until(b"\xc0")
#         return slip_pkt

#     def __read_json(self):
#         json_pkt = b""
#         while json_pkt != b"{":
#             json_pkt = self.read()
#             if json_pkt == b"":
#                 return ""
#             time.sleep(0.1)
#         json_pkt += self.read_until(b"}")
#         return json_pkt

#     def __wait_for_json(self, timeout = 1):
#         json_msg = self.__read_json()
#         init_time = time.time()
#         while not json_msg:
#             json_msg = self.__read_json()
#             time.sleep(0.1)
#             if time.time() - init_time > timeout:
#                 return ""
#         return json_msg

#     def __get_esp_version(self):
#         init_time = time.time()

#         while True:
#             get_version_pkt = b'{"c":160,"s":25,"d":4095,"b":"AAAAAAAAAA==","l":8}'
#             self.write(get_version_pkt)

#             try:
#                 json_msg = json.loads(self.__wait_for_json())
#                 if json_msg["c"] == 0xA1 and json_msg["s"] == 0x09 :
#                     break
#             except json.decoder.JSONDecodeError as jde:
#                 self.__print("json parse error: " + str(jde))

#             if time.time() - init_time > 1:
#                 return None
#         ver = b64decode(json_msg["b"]).lstrip(b"\x00")
#         return ver.decode("ascii")

#     def __set_esp_version(self, version_text: str, retry = 5):
#         self.__print(f"Writing version info (v{version_text})")
#         version_byte = version_text.encode("ascii")
#         version_byte = b"\x00" * (8 - len(version_byte)) + version_byte
#         version_text = b64encode(version_byte).decode("utf8")
#         version_msg = (
#             "{" + f'"c":160,"s":24,"d":4095,'
#             f'"b":"{version_text}","l":8' + "}"
#         )
#         version_msg_enc = version_msg.encode("utf8")

#         for _ in range(0, retry):
#             self.write(version_msg_enc)
#             try:
#                 json_msg = json.loads(self.__wait_for_json())
#                 if json_msg["c"] == 0xA1:
#                     break
#                 # self.__boot_to_app()
#             except json.decoder.JSONDecodeError as jde:
#                 self.__print("json parse error: " + str(jde))

#             time.sleep(0.5)

#         self.__print("The version info has been set!!")

#     def __compose_binary_firmware(self):
#         binary_firmware = b""
#         for i, bin_path in enumerate(self.file_path):
#             if self.ui:
#                 if sys.platform.startswith("win"):
#                     root_path = pathlib.PurePosixPath(pathlib.PurePath(__file__),"..", "..", "assets", "firmware", "esp32")
#                 else:
#                     root_path = path.join(path.dirname(__file__), "..", "assets", "firmware", "esp32")

#                 if sys.platform.startswith("win"):
#                     firmware_path = pathlib.PurePosixPath(root_path, bin_path)
#                 else:
#                     firmware_path = path.join(root_path, bin_path)
#                 with open(firmware_path, "rb") as bin_file:
#                     bin_data = bin_file.read()
#             else:
#                 root_path = path.join(path.dirname(__file__), "..", "assets", "firmware", "esp32")
#                 firmware_path = path.join(root_path, bin_path)
#                 with open(firmware_path, "rb") as bin_file:
#                     bin_data = bin_file.read()
#             binary_firmware += bin_data
#             if i < len(self.__address) - 1:
#                 binary_firmware += b"\xFF" * (self.__address[i + 1] - self.__address[i] - len(bin_data))
#         return binary_firmware

#     def __get_latest_version(self):
#         root_path = path.join(path.dirname(__file__), "..", "assets", "firmware", "esp32")
#         version_path = path.join(root_path, "esp_version.txt")
#         with open(version_path, "r") as version_file:
#             version_info = version_file.readline().lstrip("v").rstrip("\n")
#         return version_info

#     def __erase_chunk(self, size, offset):
#         num_blocks = size // self.ESP_FLASH_BLOCK + 1
#         erase_data = [0] * 24
#         erase_data[1] = self.ESP_FLASH_BEGIN
#         erase_data[2] = 0x10
#         erase_data[8:12] = int.to_bytes(size, length=4, byteorder="little")
#         erase_data[12:16] = int.to_bytes(num_blocks, length=4, byteorder="little")
#         erase_data[16:20] = int.to_bytes(self.ESP_FLASH_BLOCK, length=4, byteorder="little")
#         erase_data[20:24] = int.to_bytes(offset, length=4, byteorder="little")
#         erase_pkt = self.__parse_pkt(erase_data)
#         self.__send_pkt(erase_pkt, timeout=10)

#     def __write_flash_block(self, data, seq_block):
#         size = len(data)
#         block_data = [0] * (size + 24)
#         checksum = self.ESP_CHECKSUM_MAGIC

#         block_data[1] = self.ESP_FLASH_DATA
#         block_data[2:4] = int.to_bytes(size + 16, length=2, byteorder="little")
#         block_data[8:12] = int.to_bytes(size, length=4, byteorder="little")
#         block_data[12:16] = int.to_bytes(seq_block, length=4, byteorder="little")
#         for i in range(size):
#             block_data[24 + i] = data[i]
#             checksum ^= 0xFF & data[i]
#         block_data[4:8] = int.to_bytes(checksum, length=4, byteorder="little")
#         block_pkt = self.__parse_pkt(block_data)
#         self.__send_pkt(block_pkt)

#     def __write_binary_firmware(self, binary_firmware: bytes, manager):
#         chunk_queue = []
#         self.total_sequence = len(binary_firmware) // self.ESP_FLASH_BLOCK + 1
#         while binary_firmware:
#             if self.ESP_FLASH_CHUNK < len(binary_firmware):
#                 chunk_queue.append(binary_firmware[: self.ESP_FLASH_CHUNK])
#                 binary_firmware = binary_firmware[self.ESP_FLASH_CHUNK :]
#             else:
#                 chunk_queue.append(binary_firmware[:])
#                 binary_firmware = b""

#         blocks_downloaded = 0
#         self.current_sequence = blocks_downloaded
#         self.__print("Start uploading firmware data...")
#         for seq, chunk in enumerate(chunk_queue):
#             self.__erase_chunk(len(chunk), self.__address[0] + seq * self.ESP_FLASH_CHUNK)
#             blocks_downloaded += self.__write_chunk(chunk, blocks_downloaded, self.total_sequence, manager)
#         if manager:
#             manager.quit()
#         if self.ui:
#             if self.ui.is_english:
#                 self.ui.update_network_esp32.setText("Network ESP32 update is in progress. (99%)")
#             else:
#                 self.ui.update_network_esp32.setText("네트워크 모듈 업데이트가 진행중입니다. (99%)")
#         self.current_sequence = 99
#         self.total_sequence = 100
#         self.__print(f"\r{self.__progress_bar(99, 100)}")
#         self.__print("Firmware Upload Complete")

#     def __write_chunk(self, chunk, curr_seq, total_seq, manager):
#         block_queue = []
#         while chunk:
#             if self.ESP_FLASH_BLOCK < len(chunk):
#                 block_queue.append(chunk[: self.ESP_FLASH_BLOCK])
#                 chunk = chunk[self.ESP_FLASH_BLOCK :]
#             else:
#                 block_queue.append(chunk[:])
#                 chunk = b""
#         for seq, block in enumerate(block_queue):
#             self.current_sequence = curr_seq + seq
#             if manager:
#                 manager.status = self.__progress_bar(curr_seq + seq, total_seq)
#             if self.ui:
#                 if self.ui.is_english:
#                     self.ui.update_network_esp32.setText(f"Network ESP32 update is in progress. ({int((curr_seq+seq)/total_seq*100)}%)")
#                 else:
#                     self.ui.update_network_esp32.setText(f"네트워크 모듈 업데이트가 진행중입니다. ({int((curr_seq+seq)/total_seq*100)}%)")
#             self.__print(
#                 f"\r{self.__progress_bar(curr_seq + seq, total_seq)}", end=""
#             )
#             self.__write_flash_block(block, seq)
#         return len(block_queue)

#     def __boot_to_app(self):
#         self.write(b'{"c":160,"s":0,"d":174,"b":"AAAAAAAAAA==","l":8}')

#     def __print(self, data, end="\n"):
#         if self.print:
#             print(data, end)

#     @staticmethod
#     def __progress_bar(current: int, total: int) -> str:
#         curr_bar = 50 * current // total
#         rest_bar = 50 - curr_bar
#         return (
#             f"Firmware Upload: [{'=' * curr_bar}>{'.' * rest_bar}] "
#             f"{100 * current / total:3.1f}%"
#         )

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
                        if esp32_updater.esp is not None and esp32_updater.network_uuid is not None:
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
                        current = esp32_updater.esp.firmware_progress + esp32_updater.esp.firmware_cnt * 100
                        total = 100 * esp32_updater.esp.firmware_num

                        value = 0 if total == 0 else current / total * 100.0

                        current_sequence += current
                        total_sequence += total

                        if self.list_ui:
                            self.list_ui.progress_signal.emit(index, value)
                    else:
                        self.state[index] = 2
                elif self.state[index] == 2:
                    # end
                    current_sequence += 100 * esp32_updater.esp.firmware_num
                    total_sequence += 100 * esp32_updater.esp.firmware_num
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
                    total_sequence += 100 * esp32_updater.esp.firmware_num

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

                # print(f"\r{self.__progress_bar(current_sequence, total_sequence)}", end="")

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