import time
import ctypes
from winusbcdc import WinUSBApi
from winusbcdc import UsbSetupPacket
from winusbcdc.usb_cdc import CDC_CMDS
from winusbcdc import GUID, DIGCF_ALLCLASSES, DIGCF_DEFAULT, DIGCF_PRESENT, DIGCF_PROFILE, DIGCF_DEVICE_INTERFACE, \
    SpDeviceInterfaceData, SpDeviceInterfaceDetailData, SpDevinfoData, GENERIC_WRITE, GENERIC_READ, FILE_SHARE_WRITE, \
    FILE_SHARE_READ, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, FILE_FLAG_OVERLAPPED, INVALID_HANDLE_VALUE, \
    UsbInterfaceDescriptor, PipeInfo, ERROR_IO_INCOMPLETE, ERROR_IO_PENDING, Overlapped
from ctypes import c_byte, byref, sizeof, c_ulong, resize, wstring_at, c_void_p, c_ubyte, create_string_buffer
from ctypes.wintypes import DWORD
from winusbcdc import SetupDiGetClassDevs, SetupDiEnumDeviceInterfaces, SetupDiGetDeviceInterfaceDetail, is_device, \
    CreateFile, WinUsb_Initialize, Close_Handle, WinUsb_Free, GetLastError, WinUsb_QueryDeviceInformation, \
    WinUsb_GetAssociatedInterface, WinUsb_QueryInterfaceSettings, WinUsb_QueryPipe, WinUsb_ControlTransfer, \
    WinUsb_WritePipe, WinUsb_ReadPipe, WinUsb_GetOverlappedResult, SetupDiGetDeviceRegistryProperty, \
    WinUsb_SetPipePolicy, WinUsb_FlushPipe, SPDRP_FRIENDLYNAME

def list_modi_winusb_paths():
    api = ModiWinUsb()
    return api.list_usb_devices()

class ModiWinUsb(object):

    def __init__(self):
        self.api = WinUSBApi()
        byte_array = c_byte * 8
        self.usb_device_guid = GUID(0xA5DCBF10, 0x6530, 0x11D2, byte_array(0x90, 0x1F, 0x00, 0xC0, 0x4F, 0xB9, 0x51, 0xED))
        self.usb_winusb_guid = GUID(0xDEE824EF, 0x729b, 0x4A0E, byte_array(0x9C, 0x14, 0xB7, 0x11, 0x7D, 0x33, 0xA8, 0x17))
        self.usb_composite_guid = GUID(0x36FC9E60, 0xC465, 0x11CF, byte_array(0x80, 0x56, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00))
        self.handle_file = INVALID_HANDLE_VALUE
        self.handle_winusb = [c_void_p()]
        self._index = -1
        self.vid = 0x2FDE
        self.pid = 0x0003

    def list_usb_devices(self):
        device_paths = []
        value = 0x00000000
        value |= DIGCF_PRESENT
        value |= DIGCF_DEVICE_INTERFACE

        flags = DWORD(value)
        self.handle = self.api.exec_function_setupapi(SetupDiGetClassDevs, byref(self.usb_winusb_guid), None, None, flags)

        sp_device_interface_data = SpDeviceInterfaceData()
        sp_device_interface_data.cb_size = sizeof(sp_device_interface_data)
        sp_device_interface_detail_data = SpDeviceInterfaceDetailData()
        sp_device_info_data = SpDevinfoData()
        sp_device_info_data.cb_size = sizeof(sp_device_info_data)

        i = 0
        required_size = DWORD(0)
        member_index = DWORD(i)
        cb_sizes = (8, 6, 5)  # different on 64 bit / 32 bit etc

        while self.api.exec_function_setupapi(SetupDiEnumDeviceInterfaces, self.handle, None, byref(self.usb_winusb_guid), member_index, byref(sp_device_interface_data)):
            self.api.exec_function_setupapi(SetupDiGetDeviceInterfaceDetail, self.handle, byref(sp_device_interface_data), None, 0, byref(required_size), None)
            resize(sp_device_interface_detail_data, required_size.value)

            path = None
            for cb_size in cb_sizes:
                sp_device_interface_detail_data.cb_size = cb_size
                ret = self.api.exec_function_setupapi(SetupDiGetDeviceInterfaceDetail, self.handle, byref(sp_device_interface_data), byref(sp_device_interface_detail_data), required_size, byref(required_size), byref(sp_device_info_data))
                if ret:
                    cb_sizes = (cb_size, )
                    path = wstring_at(byref(sp_device_interface_detail_data, sizeof(DWORD)))
                    break
            if path is None:
                raise ctypes.WinError()

            if self.find_device(path) and not path in device_paths:
                device_paths.append(path)

            i += 1
            member_index = DWORD(i)
            required_size = c_ulong(0)
            resize(sp_device_interface_detail_data, sizeof(SpDeviceInterfaceDetailData))

        return device_paths

    def find_device(self, path):
        return is_device(None, self.vid, self.pid, path)

    def init_winusb_device(self, path):

        self.handle_file = self.api.exec_function_kernel32(CreateFile, path, GENERIC_WRITE | GENERIC_READ,
                                                           FILE_SHARE_WRITE | FILE_SHARE_READ, None, OPEN_EXISTING,
                                                           FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OVERLAPPED, None)

        if self.handle_file == INVALID_HANDLE_VALUE:
            return False
        result = self.api.exec_function_winusb(WinUsb_Initialize, self.handle_file, byref(self.handle_winusb[0]))
        if result == 0:
            err = self.get_last_error_code()
            raise ctypes.WinError()
            # return False
        else:
            self._index = 0
            return True

    def close_winusb_device(self):
        result_file = 1
        if self.handle_file:
            result_file = self.api.exec_function_kernel32(Close_Handle, self.handle_file)
            if result_file:
                self.handle_file = None

        result_winusb = [self.api.exec_function_winusb(WinUsb_Free, h) for h in self.handle_winusb]
        if 0 in result_winusb:
            raise RuntimeError("Unable to close winusb handle")
        self.handle_winusb = []
        return result_file != 0

    def get_last_error_code(self):
        return self.api.exec_function_kernel32(GetLastError)

    def query_device_info(self, query=1):
        info_type = c_ulong(query)
        buff = (c_void_p * 1)()
        buff_length = c_ulong(sizeof(c_void_p))
        result = self.api.exec_function_winusb(WinUsb_QueryDeviceInformation, self.handle_winusb[self._index], info_type, byref(buff_length), buff)
        if result != 0:
            return buff[0]
        else:
            return -1

    def query_interface_settings(self, index):
        if self._index != -1:
            temp_handle_winusb = self.handle_winusb[self._index]
            interface_descriptor = UsbInterfaceDescriptor()
            result = self.api.exec_function_winusb(WinUsb_QueryInterfaceSettings, temp_handle_winusb, c_ubyte(0), byref(interface_descriptor))
            if result != 0:
                return interface_descriptor
            else:
                return None
        else:
            return None

    def change_interface(self, index, alternate=0):
        new_handle = c_void_p()
        result = self.api.exec_function_winusb(WinUsb_GetAssociatedInterface, self.handle_winusb[self._index], c_ubyte(alternate), byref(new_handle))
        if result != 0:
            self._index = index + 1
            self.handle_winusb.append(new_handle)
            return True
        else:
            return False

    def query_pipe(self, pipe_index):
        pipe_info = PipeInfo()
        result = self.api.exec_function_winusb(WinUsb_QueryPipe, self.handle_winusb[self._index], c_ubyte(0), pipe_index, byref(pipe_info))
        if result != 0:
            return pipe_info
        else:
            return None

    def control_transfer(self, setup_packet, buff=None):
        if buff != None:
            if setup_packet.length > 0:  # Host 2 Device
                buff = (c_ubyte * setup_packet.length)(*buff)
                buffer_length = setup_packet.length
            else:  # Device 2 Host
                buff = (c_ubyte * setup_packet.length)()
                buffer_length = setup_packet.length
        else:
            buff = c_ubyte()
            buffer_length = 0

        result = self.api.exec_function_winusb(WinUsb_ControlTransfer, self.handle_winusb[0], setup_packet, byref(buff), c_ulong(buffer_length), byref(c_ulong(0)), None)
        return {"result": result != 0, "buffer": [buff]}

    def write(self, pipe_id, write_buffer):
        write_buffer = create_string_buffer(write_buffer)
        written = c_ulong(0)
        self.api.exec_function_winusb(WinUsb_WritePipe, self.handle_winusb[self._index], c_ubyte(pipe_id), write_buffer, c_ulong(len(write_buffer) - 1), byref(written), None)
        return written.value

    def read(self, pipe_id, length_buffer):
        read_buffer = create_string_buffer(length_buffer)
        read = c_ulong(0)
        result = self.api.exec_function_winusb(WinUsb_ReadPipe, self.handle_winusb[self._index], c_ubyte(pipe_id), read_buffer, c_ulong(length_buffer), byref(read), None)
        if result != 0:
            if read.value != length_buffer:
                return read_buffer[:read.value]
            else:
                return read_buffer
        else:
            return None

    def set_timeout(self, pipe_id, timeout):
        class POLICY_TYPE:
            SHORT_PACKET_TERMINATE = 1
            AUTO_CLEAR_STALL = 2
            PIPE_TRANSFER_TIMEOUT = 3
            IGNORE_SHORT_PACKETS = 4
            ALLOW_PARTIAL_READS = 5
            AUTO_FLUSH = 6
            RAW_IO = 7

        policy_type = c_ulong(POLICY_TYPE.PIPE_TRANSFER_TIMEOUT)
        value_length = c_ulong(4)
        value = c_ulong(int(timeout * 1000))  # in ms
        result = self.api.exec_function_winusb(WinUsb_SetPipePolicy, self.handle_winusb[self._index], c_ubyte(pipe_id), policy_type, value_length, byref(value))
        return result

    def flush(self, pipe_id):
        result = self.api.exec_function_winusb(WinUsb_FlushPipe, self.handle_winusb[self._index], c_ubyte(pipe_id))
        return result

    def _overlapped_read_do(self,pipe_id):
        self.olread_ol.Internal = 0
        self.olread_ol.InternalHigh = 0
        self.olread_ol.Offset = 0
        self.olread_ol.OffsetHigh = 0
        self.olread_ol.Pointer = 0
        self.olread_ol.hEvent = 0
        result = self.api.exec_function_winusb(WinUsb_ReadPipe, self.handle_winusb[self._index], c_ubyte(pipe_id), self.olread_buf, c_ulong(self.olread_buflen), byref(c_ulong(0)), byref(self.olread_ol))
        if result != 0:
            return True
        else:
            return False

    def overlapped_read_init(self, pipe_id, length_buffer):
        self.olread_ol = Overlapped()
        self.olread_buf = create_string_buffer(length_buffer)
        self.olread_buflen = length_buffer
        return self._overlapped_read_do(pipe_id)

    def overlapped_read(self, pipe_id):
        """ keep on reading overlapped, return bytearray, empty if nothing to read, None if err"""
        rl = c_ulong(0)
        result = self.api.exec_function_winusb(WinUsb_GetOverlappedResult, self.handle_winusb[self._index], byref(self.olread_ol),byref(rl),False)
        if result == 0:
            if self.get_last_error_code() == ERROR_IO_PENDING or self.get_last_error_code() == ERROR_IO_INCOMPLETE:
                return ""
            else:
                return None
        else:
            ret = str(self.olread_buf[0:rl.value])
            self._overlapped_read_do(pipe_id)
            return ret


class ModiWinUsbComPort:
    def __init__(self, path=None, baudrate=921600, start=True):
        self.device = None
        self.path = path
        self._rxremaining = b''
        self.baudrate = baudrate
        self.parity = 0
        self.stopbits = 1
        self.databits = 8
        self.maximum_packet_size = 0

        self._timeout = 0

        self.is_open = False
        if start:
            self.open()

    def open(self):
        # Control interface
        api = self._select_device(self.path)
        if not api:
            return False

        # Data Interface
        api.change_interface(0)
        interface2_descriptor = api.query_interface_settings(0)

        pipe_info_list = map(api.query_pipe, range(interface2_descriptor.b_num_endpoints))
        for item in pipe_info_list:
            if item.pipe_id & 0x80:
                self._ep_in = item.pipe_id
            else:
                self._ep_out = item.pipe_id
            self.maximum_packet_size = min(item.maximum_packet_size, self.maximum_packet_size) or item.maximum_packet_size

        self.device = api

        self.is_open = True

        self.setControlLineState(True, True)
        self.setLineCoding()
        self.device.set_timeout(self._ep_in, 2)
        self.reset_input_buffer()

    @property
    def in_waiting(self):
        return False

    @property
    def timeout(self):
        return self._timeout

    def settimeout(self, timeout):
        self._timeout = timeout
        if self.is_open:
            self.device.set_timeout(self._ep_in, timeout)

    @timeout.setter
    def timeout(self, timeout):
        self.settimeout(timeout)

    def readinto(self, buf):
        if not self.is_open:
            return None
        orig_size = len(buf)
        read = 0
        if self._rxremaining:
            l = len(self._rxremaining)
            read = min(l, orig_size)
            buf[0:read] = self._rxremaining[0:read]
            self._rxremaining = self._rxremaining[read:]
        end_timeout = time.time() + (self.timeout or 0.2)
        self.device.set_timeout(self._ep_in, 2)
        while read < orig_size:
            remaining = orig_size-read
            c = self.device.read(self._ep_in, min(remaining, 1024*4))
            if c is not None and len(c):
                if len(c) > remaining:
                    end_timeout += 0.2
                    buf[read:] = c[0:remaining]
                    self._rxremaining = c[remaining:]
                    return orig_size
                else:
                    buf[read:] = c
                read += len(c)
            if time.time() > end_timeout:
                break
        return read

    def read(self, size=None):
        if not self.is_open:
            return None
        rx = [self._rxremaining]
        length = len(self._rxremaining)
        self._rxremaining = b''
        end_timeout = time.time() + (self.timeout or 0.2)
        if size:
            self.device.set_timeout(self._ep_in, 2)
            while length < size:
                c = self.device.read(self._ep_in, size-length)
                if c is not None and len(c):
                    end_timeout += 0.2
                    rx.append(c)
                    length += len(c)
                if time.time() > end_timeout:
                    break
        else:
            self.device.set_timeout(self._ep_in, 0.2)
            while True:
                c = self.device.read(self._ep_in, self.maximum_packet_size)
                if c is not None and len(c):
                    end_timeout += 0.2
                    rx.append(c)
                    length += len(c)
                else:
                    break
                if time.time() > end_timeout:
                    break
        chunk = b''.join(rx)
        if size and len(chunk) >= size:
            if self._rxremaining:
                self._rxremaining = chunk[size:] + self._rxremaining
            else:
                self._rxremaining = chunk[size:]
            chunk = chunk[0:size]
        return chunk

    def readline(self, size=64*1024):
        if not self.is_open:
            return None
        rx = [self._rxremaining]
        length = len(self._rxremaining)
        self._rxremaining = b''
        end_timeout = time.time() + self.timeout
        self.device.set_timeout(self._ep_in, 0.2)
        while b'\n' not in rx[-1]:  # 10 == b'\n'
            c = self.device.read(self._ep_in, size-length)
            if c is not None and len(c):
                end_timeout += 0.2
                length += len(c)
                rx.append(c)
            if time.time() > end_timeout:
                break
        line = b''.join(rx)
        i = line.find(b'\n')+1
        self._rxremaining = line[i:]
        return line[0:i]

    def read_all(self):
        return self.read()

    def write(self, data):
        if not self.is_open:
            return None
        try:
            ret = self.device.write(self._ep_out, data)
        except Exception as e:
            # print("USB Error on write {}".format(e))
            return

        # if len(data) != ret:
        #     print("Bytes written mismatch {0} vs {1}".format(len(data), ret))
        # else:
        #     print("{} bytes written to ep".format(ret))

    def setControlLineState(self, RTS=None, DTR=None):
        if not self.is_open:
            return None
        ctrlstate = (2 if RTS else 0) + (1 if DTR else 0)

        txdir = 0           # 0:OUT, 1:IN
        req_type = 1     # 0:std, 1:class, 2:vendor
        # 0:device, 1:interface, 2:endpoint, 3:other
        recipient = 1
        req_type = (txdir << 7) + (req_type << 5) + recipient

        pkt = UsbSetupPacket(
            request_type=req_type,
            request=CDC_CMDS["SET_CONTROL_LINE_STATE"],
            value=ctrlstate,
            index=0x00,
            length=0x00
        )
        # buff = [0xc0, 0x12, 0x00, 0x00, 0x00, 0x00, 0x08]
        buff = None

        wlen = self.device.control_transfer(pkt, buff)
        # print("Linecoding set, {}b sent".format(wlen))

    def setLineCoding(self, baudrate=None, parity=None, databits=None, stopbits=None):
        if not self.is_open:
            return None

        sbits = {1: 0, 1.5: 1, 2: 2}
        dbits = {5, 6, 7, 8, 16}
        pmodes = {0, 1, 2, 3, 4}
        brates = {300, 600, 1200, 2400, 4800, 9600, 14400,
                  19200, 28800, 38400, 57600, 115200, 230400}

        if stopbits is not None:
            if stopbits not in sbits.keys():
                valid = ", ".join(str(k) for k in sorted(sbits.keys()))
                raise ValueError("Valid stopbits are " + valid)
            self.stopbits = stopbits

        if databits is not None:
            if databits not in dbits:
                valid = ", ".join(str(d) for d in sorted(dbits))
                raise ValueError("Valid databits are " + valid)
            self.databits = databits

        if parity is not None:
            if parity not in pmodes:
                valid = ", ".join(str(pm) for pm in sorted(pmodes))
                raise ValueError("Valid parity modes are " + valid)
            self.parity = parity

        if baudrate is not None:
            if baudrate not in brates:
                brs = sorted(brates)
                dif = [abs(br - baudrate) for br in brs]
                best = brs[dif.index(min(dif))]
                raise ValueError(
                    "Invalid baudrates, nearest valid is {}".format(best))
            self.baudrate = baudrate

        linecode = [
            self.baudrate & 0xff,
            (self.baudrate >> 8) & 0xff,
            (self.baudrate >> 16) & 0xff,
            (self.baudrate >> 24) & 0xff,
            sbits[self.stopbits],
            self.parity,
            self.databits]

        txdir = 0           # 0:OUT, 1:IN
        req_type = 1        # 0:std, 1:class, 2:vendor
        recipient = 1       # 0:device, 1:interface, 2:endpoint, 3:other
        req_type = (txdir << 7) + (req_type << 5) + recipient

        pkt = UsbSetupPacket(
            request_type=req_type,
            request=CDC_CMDS["SET_LINE_CODING"],
            value=0x0000,
            index=0x00,
            length=len(linecode)
        )
        # buff = [0xc0, 0x12, 0x00, 0x00, 0x00, 0x00, 0x08]
        buff = linecode


        wlen = self.device.control_transfer(pkt, buff)
        # print("Linecoding set, {}b sent".format(wlen))

    def disconnect(self):
        if not self.is_open:
            return None
        self.device.close_winusb_device()
        self.is_open = False

    def __del__(self):
        self.disconnect()

    def reset_input_buffer(self):
        if self.is_open:
            self.device.flush(self._ep_in)
            while self.read():
                pass
        self._rxremaining = b''

    def reset_output_buffer(self):
        pass

    def flush(self):
        if not self.is_open:
            return None
        self.device.flush(self._ep_in)

    def close(self):
        self.disconnect()

    def flushInput(self):
        self.reset_input_buffer()

    def flushOutput(self):
        self.reset_output_buffer()

    def _select_device(self, path):
        api = ModiWinUsb()

        if not api.init_winusb_device(path):
            return None

        return api

# main
if __name__ == "__main__":
    paths = list_modi_winusb_paths()
    for index, value in enumerate(paths):
        print(index, value)