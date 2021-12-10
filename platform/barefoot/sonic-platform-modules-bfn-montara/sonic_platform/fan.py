try:
    from sonic_platform.platform_thrift_client import thrift_try
    from sonic_platform_base.fan_base import FanBase
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")

def _fan_info_get(fan_num, cb, default=None):
    def get_data(client):
        return client.pltfm_mgr.pltfm_mgr_fan_info_get(fan_num)
    fan_info = thrift_try(get_data)
    if fan_num == fan_info.fan_num:
        return cb(fan_info)
    if default is None:
        raise LookupError
    return default

# Fan -> FanBase -> DeviceBase
class Fan(FanBase):
    def __init__(self, num):
        self.__num = num

    # FanBase interface methods:
    # returns speed in percents
    def get_speed(self):
        def cb(info): return info.percent
        return _fan_info_get(self.__num, cb, 0)

    def set_speed(self, percent):
        def set_fan_speed(client):
            return client.pltfm_mgr.pltfm_mgr_fan_speed_set(self.__num, percent)
        return thrift_try(set_fan_speed)

    # DeviceBase interface methods:
    def get_name(self):
        return f"counter-rotating-fan-{self.__num}"

    def get_presence(self):
        return _fan_info_get(self.__num, lambda _: True, False)

    def get_position_in_parent(self):
        return self.__num

    def is_replaceable(self):
        return True

    def get_status(self):
        return True

    def get_model(self):
        """
        Retrieves the part number of the fan drawer
        Returns:
            string: Part number of fan drawer
        """
        return 'N/A'

    def get_direction(self):
        """
        Retrieves the direction of fan

        Returns:
            A string, either FAN_DIRECTION_INTAKE or FAN_DIRECTION_EXHAUST
            depending on fan direction
        """
        return 'N/A'

    def get_target_speed(self):
        """
        Retrieves the target (expected) speed of the fan
        Returns:
            An integer, the percentage of full fan speed, in the range 0 (off)
                 to 100 (full speed)
        """
        return 0

    def get_speed_tolerance(self):
        """
        Retrieves the speed tolerance of the fan

        Returns:
            An integer, the percentage of variance from target speed which is
                 considered tolerable
        """
        return 0

    def get_serial(self):
        """
        Retrieves the serial number of the device

        Returns:
            string: Serial number of device
        """
        return 'N/A'

    def set_status_led(self, color):
        """
        Sets the state of the fan module status LED

        Args:
            color: A string representing the color with which to set the
                   fan module status LED

        Returns:
            bool: True if status LED state is set successfully, False if not
        """
        # Fan tray status LED controlled by BMC
        # Should return True to avoid thermalctld alarm
        return False
