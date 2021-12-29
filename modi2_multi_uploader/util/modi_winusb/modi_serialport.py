import sys
import time
import serial
import serial.tools.list_ports as stl
from modi_winusb import ModiWinUsbComPort, list_modi_winusb_paths


SERIAL_MODE_COMPORT = 1
SERIAL_MODI_WINUSB = 2

class ModiSerialPortInfo(object):
    def __init__(self, type=None, port=None):
        self.type = type
        self.port = port

    def __eq__(self, other):
        return isinstance(other, ModiSerialPortInfo) and self.port == other.port

    def __str__(self):
         return '{} - {}'.format("comport" if self.type == SERIAL_MODE_COMPORT else "winusb", self.port)

def list_modi_serialport_info():
    info_list = []

    def __is_modi_port(port):
        return (port.vid == 0x2FDE and port.pid == 0x0003)
    modi_ports = [port for port in stl.comports() if __is_modi_port(port)]
    for modi_port in modi_ports:
        info = ModiSerialPortInfo(SERIAL_MODE_COMPORT, modi_port.device)
        info_list.append(info)

    if sys.platform.startswith("win"):
        path_list = list_modi_winusb_paths()
        for index, value in enumerate(path_list):
            info = ModiSerialPortInfo(SERIAL_MODI_WINUSB, value)
            info_list.append(info)

    return info_list

class ModiTimeout(object):
    """\
    Abstraction for timeout operations. Using time.monotonic() if available
    or time.time() in all other cases.

    The class can also be initialized with 0 or None, in order to support
    non-blocking and fully blocking I/O operations. The attributes
    is_non_blocking and is_infinite are set accordingly.
    """
    if hasattr(time, 'monotonic'):
        # Timeout implementation with time.monotonic(). This function is only
        # supported by Python 3.3 and above. It returns a time in seconds
        # (float) just as time.time(), but is not affected by system clock
        # adjustments.
        TIME = time.monotonic
    else:
        # Timeout implementation with time.time(). This is compatible with all
        # Python versions but has issues if the clock is adjusted while the
        # timeout is running.
        TIME = time.time

    def __init__(self, duration):
        """Initialize a timeout with given duration"""
        self.is_infinite = (duration is None)
        self.is_non_blocking = (duration == 0)
        self.duration = duration
        if duration is not None:
            self.target_time = self.TIME() + duration
        else:
            self.target_time = None

    def expired(self):
        """Return a boolean, telling if the timeout has expired"""
        return self.target_time is not None and self.time_left() <= 0

    def time_left(self):
        """Return how many seconds are left until the timeout expires"""
        if self.is_non_blocking:
            return 0
        elif self.is_infinite:
            return None
        else:
            delta = self.target_time - self.TIME()
            if delta > self.duration:
                # clock jumped, recalculate
                self.target_time = self.TIME() + self.duration
                return self.duration
            else:
                return max(0, delta)

    def restart(self, duration):
        """\
        Restart a timeout, only supported if a timeout was already set up
        before.
        """
        self.duration = duration
        self.target_time = self.TIME() + duration

class ModiSerialPort():
    def __init__(self, info = None, baudrate = 921600, timeout = 2, write_timeout = None):
        self.info = info
        self.port = None
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout

        self.serial_port = None

        if info is not None:
            self.open(self.info)

    def open(self, info):
        self.info = info
        self.port = info.port

        if self.info.type == SERIAL_MODI_WINUSB:
            winusb = ModiWinUsbComPort(path = self.info.port, baudrate=self.baudrate)
            self.serial_port = winusb
        else:
            ser = serial.Serial(port = self.info.port, baudrate=self.baudrate, exclusive=True)
            self.serial_port = ser

    def close(self):
        if self.serial_port is not None:
            self.serial_port.close()

    def write(self, data):
        if self.serial_port == None:
            raise Exception("serialport is not opened")
        self.serial_port.write(data)

    def read(self, size=1):
        if self.serial_port == None:
            raise Exception("serialport is not opened")
        return self.serial_port.read(size)

    def read_until(self, expected=b"\x0A", size=None):
        if self.serial_port == None:
            raise Exception("serialport is not opened")

        lenterm = len(expected)
        line = bytearray()
        modi_timeout = ModiTimeout(self.timeout)
        while True:
            c = self.read(1)
            if c:
                line += c
                if line[-lenterm:] == expected:
                    break
                if size is not None and len(line) >= size:
                    break
            else:
                break
            if modi_timeout.expired():
                break
        return bytes(line)

    def read_all(self):
        if self.serial_port == None:
            raise Exception("serialport is not opened")

        if self.info.type == SERIAL_MODI_WINUSB:
            return self.serial_port.read()
        else:
            return self.serial_port.read_all()

    def flush(self):
        if self.serial_port == None:
            raise Exception("serialport is not opened")
        self.serial_port.flush()

    def flushInput(self):
        if self.serial_port == None:
            raise Exception("serialport is not opened")

        if self.info.type == SERIAL_MODI_WINUSB:
            return self.serial_port.reset_input_buffer()
        else:
            return self.serial_port.flushInput()

    def flushOutput(self):
        if self.serial_port == None:
            raise Exception("serialport is not opened")

        if self.info.type == SERIAL_MODI_WINUSB:
            return self.serial_port.reset_output_buffer()
        else:
            return self.serial_port.flushOutput()

    def inWaiting(self):
        if self.serial_port == None:
            raise Exception("serialport is not opened")

        if self.info.type == SERIAL_MODI_WINUSB:
            return self.serial_port.reset_output_buffer()
        else:
            return self.serial_port.inWaiting()



# main
if __name__ == "__main__":
    stop = False

    def handle_received(serialport):
        global stop

        while not stop:
            init = time.time()
            recv = serialport.read_until(b"}")
            dt = time.time() - init
            if recv == None:
                print("disconnected")
                stop = True
                break

            print(f"dt: {int(dt * 1000.0)}ms - {recv}")
            time.sleep(0.001)

        serialport.close()

    import threading
    info_list = list_modi_serialport_info()

    if len(info_list) == 0:
        raise Exception("No MODI is connected")

    serialport = ModiSerialPort(info_list[0])
    threading.Thread(target=handle_received, daemon=True, args=(serialport, )).start()

    print("To exit the program, enter 'exit'.")
    while not stop:
        input_data = input()

        if input_data == "exit":
            stop = True
            break

    serialport.close()