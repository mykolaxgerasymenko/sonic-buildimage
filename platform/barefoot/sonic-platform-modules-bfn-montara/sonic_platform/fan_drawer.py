try:
    from sonic_platform.platform_thrift_client import thrift_try
    from sonic_platform_base.fan_drawer_base import FanDrawerBase
    from sonic_platform_base.fan_base import FanBase
    from sonic_py_common import device_info
    from fan import Fan
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")

_CONST_MAX_FAN = 2
_MAX_FANTRAY = 5

_product_dict = {
    "x86_64-accton_wedge100bf_32x-r0"   : "Montara",
    "x86_64-accton_as9516_32d-r0"       : "Newport",
    "Lx86_64-accton_as9516bf_32d-r0"    : "Newport",
    "x86_64-accton_wedge100bf_65x-r0"   : "Mavericks"
}

def _fan_info_get_all():
    for fan_num in range(1, _CONST_MAX_FAN + 1):
        def get_data(client, fan_num=fan_num):
            return client.pltfm_mgr.pltfm_mgr_fan_info_get(fan_num)
        fan_info = thrift_try(get_data)
        if fan_info.fan_num == fan_num:
            yield fan_info

# FanDrawer -> FanDrawerBase -> DeviceBase
class FanDrawer(FanDrawerBase):
    def __init__(self, fantray_index, modelstr="Montara"):
        # For now we return only present fans
        self.modelstr = modelstr
        self.fantrayindex = fantray_index + 1
        self._fan_list = [Fan(i.fan_num, self.fantrayindex, modelstr) for i in _fan_info_get_all()]



    # DeviceBase interface methods:
    def get_name(self):
        return f"fantray-{self.fantrayindex}"

    def get_presence(self):
        return True

    def get_status(self):
        return True

    def get_position_in_parent(self):
        """
        Retrieves 1-based relative physical position in parent device.
        Returns:
            integer: The 1-based relative physical position in parent
            device or -1 if cannot determine the position
        """
        return self.fantrayindex

    def is_replaceable(self):
        """
        Indicate whether this fan drawer is replaceable.
        Returns:
            bool: True if it is replaceable, False if not
        """
        return False

    def get_model(self):
        """
        Retrieves the part number of the fan drawer
        Returns:
            string: Part number of fan drawer
        """
        return 'N/A'

    def get_serial(self):
        """
        Retrieves the serial number of the fan drawer
        Returns:
            string: Serial number of the fan drawer
        """
        return 'N/A'

    def set_status_led(self, color):
        """
        Set led to expected color
        Args:
            color: A string representing the color with which to set the
            fan module status LED
        Returns:
            bool: True if set success, False if fail.
        """
        # Fan tray status LED controlled by BMC
        # Should return True to avoid thermalctld alarm
        return False

    def get_status_led(self):
        """
        Gets the state of the fan drawer LED
        Returns:
            A string, one of the predefined STATUS_LED_COLOR_* strings above
        """
        return "N/A"

    def get_maximum_consumed_power(self):
        """
        Retrives the maximum power drawn by Fan Drawer
        Returns:
            A float, with value of the maximum consumable power of the
            component.
        """
        return 36.0

def get_platform_name():
    return _product_dict.get(device_info.get_platform())

def fan_drawer_list_get():
    global  _MAX_FANTRAY
    platform = get_platform_name()
    if platform == "Newport":
        _MAX_FANTRAY = 6
    if platform == "Mavericks":
        _MAX_FANTRAY = 10

    return [FanDrawer(i, platform) for i in range(0, _MAX_FANTRAY)]
