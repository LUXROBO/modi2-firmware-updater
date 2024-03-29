import time
from os import path
from typing import Union

from modi2_firmware_updater.util.message_util import parse_message

BROADCAST_ID = 0xFFF


def get_module_type_from_uuid(uuid):
    try:
        hexadecimal = hex(uuid).lstrip("0x")
        hexadecimal = int(hexadecimal, 16) >> 32
        type_indicator = hexadecimal
        module_type = {
            # Setup modules
            0x10  : "battery",
            # Input modules
            0x2000: "env",
            0x2010: "imu",
            0x2020: "mic",
            0x2030: "button",
            0x2040: "dial",
            0x2050: "ultrasonic",
            0x2060: "ir",
            0x2070: "joystick",
            0x2080: "tof",
            0x2090: "camera",
            # Output modules
            0x4000: "display",
            0x4010: "motor",
            0x4011: "motor",
            0x4020: "led",
            0x4030: "speaker",
        }.get(type_indicator)
        return "network" if module_type is None else module_type
    except Exception:
        return "None"


def get_module_uuid_from_type(module_type):
    module_type_hex = {
        # Setup modules
        "battery": 0x10,
        # module: # Input
        "env": 0x2000,
        "imu": 0x2010,
        "mic": 0x2020,
        "button": 0x2030,
        "dial": 0x2040,
        "ultrasonic": 0x2050,
        "ir": 0x2060,
        "joystick": 0x2070,
        "tof": 0x2080,
        "camera": 0x2090,
        #  module: # Output
        "display": 0x4000,
        "motor": 0x4010,
        "motor_a": 0x4010,
        "motor_b": 0x4011,
        "led": 0x4020,
        "speaker": 0x4030,
    }.get(module_type)
    return "network" if module_type_hex is None else module_type_hex


class Module:
    """
    :param int id_: The id of the module.
    :param int uuid: The uuid of the module.
    """

    class Property:
        def __init__(self, value: Union[int, float] = 0):
            self.value = value
            self.last_update_time = time.time()

    RUN = 0
    WARNING = 1
    FORCED_PAUSE = 2
    ERROR_STOP = 3
    UPDATE_FIRMWARE = 4
    UPDATE_FIRMWARE_READY = 5
    REBOOT = 6
    PNP_ON = 1
    PNP_OFF = 2

    def __init__(self, id_, uuid, conn_task):
        self._id = id_
        self._uuid = uuid
        self._conn = conn_task

        self.module_type = str()
        self._properties = dict()
        self._topology = {"r": 0, "t": 0, "l": 0, "b": 0}

        # sampling_rate = (100 - property_sampling_frequency) * 11, in ms
        self.prop_samp_freq = 91

        self.is_connected = True
        self.has_printed = False
        self.last_updated = time.time()
        self.battery = 100
        self.position = (0, 0)
        self.__version = None
        self.user_code_status = -1  # 1 if user code and 0 if not

    def __gt__(self, other):
        if self.order == other.order:
            if self.position[0] == other.position[0]:
                return self.position[1] < other.position[1]
            else:
                return self.position[0] > other.position[0]
        else:
            return self.order > other.order

    def __lt__(self, other):
        if self.order == other.order:
            if self.position[0] == other.position[0]:
                return self.position[1] > other.position[1]
            else:
                return self.position[0] < other.position[0]
        else:
            return self.order < other.order

    def __str__(self):
        return f"{self.__class__.__name__} ({self._id})"

    @property
    def has_user_code(self):
        return self.user_code_status == 1

    @property
    def version(self):
        version_string = ""
        version_string += str(self.__version >> 13) + "."
        version_string += str(self.__version % (2 ** 13) >> 8) + "."
        version_string += str(self.__version % (2 ** 8))
        return version_string

    @version.setter
    def version(self, version_info):
        self.__version = version_info

    @property
    def order(self):
        return self.position[0] ** 2 + self.position[1] ** 2

    @property
    def id(self) -> int:
        return self._id

    @property
    def uuid(self) -> int:
        return self._uuid

    @property
    def is_up_to_date(self):
        root_path = path.join(
            path.dirname(__file__), "..", "assets", "firmware", "module"
        )
        version_path = path.join(root_path, "version.txt")
        with open(version_path) as version_file:
            version_info = version_file.readline().lstrip("v").rstrip("\n").split("-")[0]
        version_digits = [int(digit) for digit in version_info.split(".")]
        latest_version = (
            version_digits[0] << 13
            | version_digits[1] << 8
            | version_digits[2]
        )
        return latest_version <= self.__version

    def _get_property(self, property_type: int) -> float:
        """Get module property value and request

        :param property_type: Type of the requested property
        :type property_type: int
        """

        # Register property if not exists
        if property_type not in self._properties:
            self._properties[property_type] = self.Property()
            self.__request_property(self._id, property_type)

        # Request property value if not updated for 1.5 sec
        last_update = self._properties[property_type].last_update_time
        if time.time() - last_update > 1.5:
            self.__request_property(self._id, property_type)

        return self._properties[property_type].value

    def update_property(
        self, property_type: int, property_value: float
    ) -> None:
        """Update property value and time

        :param property_type: Type of the updated property
        :type property_type: int
        :param property_value: Value to update the property
        :type property_value: float
        """
        if property_type not in self._properties:
            self._properties[property_type] = self.Property()
        self._properties[property_type].value = property_value
        self._properties[property_type].last_update_time = time.time()

    def __request_property(
        self, destination_id: int, property_type: int
    ) -> None:
        """Generate message for request property

        :param destination_id: Id of the destination module
        :type destination_id: int
        :param property_type: Type of the requested property
        :type property_type: int
        :return: None
        """
        self._properties[property_type].last_update_time = time.time()
        req_prop_msg = parse_message(
            0x03,
            0,
            destination_id,
            (property_type, None, self.prop_samp_freq, None),
        )
        self._conn.send(req_prop_msg)
