import os
import time
from abc import ABC, abstractmethod
from typing import List, Optional

from serial.serialutil import SerialException
from modi2_multi_uploader.util.modi_winusb.modi_serialport import ModiSerialPort, list_modi_serialport


class ConnTask(ABC):
    def __init__(self, verbose=False):
        self._bus = None
        self.verbose = verbose

    @property
    def bus(self):
        return self._bus

    @bus.setter
    def bus(self, new_bus):
        if not isinstance(new_bus, type(self._bus)):
            raise ValueError()
        else:
            self._bus = new_bus

    #
    # Abstract Methods
    #
    @abstractmethod
    def close_conn(self):
        pass

    @abstractmethod
    def open_conn(self):
        pass

    @abstractmethod
    def recv(self) -> Optional[str]:
        pass

    @abstractmethod
    def send(self, pkt: str) -> None:
        pass

    @staticmethod
    def wait(func):
        """Wait decorator
        Make sure this is attached to inherited send method
        """

        def decorator(self, pkt: str) -> None:
            init_time = time.perf_counter()
            func(self, pkt)
            while time.perf_counter() - init_time < 0.04:
                pass

        return decorator


class SerTask(ConnTask):
    def __init__(self, verbose=False, port=None):
        if verbose:
            print("Initiating serial connection...")
        super().__init__(verbose)
        self.__port = port

    #
    # Inherited Methods
    #
    def open_conn(self) -> None:
        """Open serial port

        :return: None
        """
        modi_ports = list_modi_ports()
        if not modi_ports:
            raise SerialException("No MODI network module is available")

        if self.__port:
            if self.__port not in map(lambda info: info, modi_ports):
                raise SerialException(
                    f"{self.__port} is not connected "
                    f"to a MODI network module."
                )
            else:
                try:
                    self._bus = self.__init_serial(self.__port)
                    return
                except SerialException:
                    raise SerialException(f"{self.__port} is not available.")

        for modi_port in modi_ports:
            self._bus = self.__init_serial(modi_port)
            try:
                if self.verbose:
                    print(f'Serial is open at "{modi_port}"')
                return
            except SerialException:
                continue
        raise SerialException("No MODI port is available now")

    @staticmethod
    def __init_serial(port):
        ser = ModiSerialPort(port)
        return ser

    def close_conn(self) -> None:
        """Close serial port

        :return: None
        """
        self._bus.close()

    def recv(self, verbose=False) -> Optional[str]:
        """Read serial message and put message to serial read queue

        :return: str
        """
        json_pkt = self.__wait_for_json()
        if self.verbose or verbose:
            print(f"recv: {json_pkt}")
        return json_pkt

    def __read_json(self) -> Optional[str]:
        json_pkt = b""
        while json_pkt != b"{":
            if not self._bus.is_open:
                return None
            json_pkt = self._bus.read()
            if json_pkt == b"":
                return None
            time.sleep(0.1)
        json_pkt += self._bus.read_until(b"}")
        return json_pkt.decode("utf8")

    def __wait_for_json(self, timeout=2):
        json_msg = self.__read_json()
        init_time = time.time()
        while not json_msg:
            json_msg = self.__read_json()
            time.sleep(0.1)
            if time.time() - init_time > timeout:
                return None
        return json_msg

    @ConnTask.wait
    def send(self, pkt: str, verbose=False) -> None:
        """Send json pkt

        :param pkt: Json pkt to send
        :type pkt: str
        :param verbose: Verbosity parameter
        :type verbose: bool
        :return: None
        """
        self._bus.write(pkt.encode("utf8"))
        if self.verbose or verbose:
            print(f"send: {pkt}")

    def send_nowait(self, pkt: str, verbose=False) -> None:
        """Send json pkt

        :param pkt: Json pkt to send
        :type pkt: str
        :param verbose: Verbosity parameter
        :type verbose: bool
        :return: None
        """
        self._bus.write(pkt.encode("utf8"))
        if self.verbose or verbose:
            print(f"send: {pkt}")


def list_modi_ports() -> List[str]:
    """Returns a list of connected MODI ports

    :return: List[str]
    """
    modi_ports = list_modi_serialport()
    # print(f'{len(modi_ports)} number of network module(s) exist(s)')
    return modi_ports


def is_on_pi() -> bool:
    """Returns whether connected to pi

    :return: true if connected to pi
    :rtype: bool
    """
    return os.name != "nt" and os.uname()[4][:3] == "arm"


def is_network_module_connected() -> bool:
    """Returns whether network module is connected

    :return: true if connected
    :rtype: bool
    """
    return bool(list_modi_ports())


class MODIConnectionError(Exception):
    pass
