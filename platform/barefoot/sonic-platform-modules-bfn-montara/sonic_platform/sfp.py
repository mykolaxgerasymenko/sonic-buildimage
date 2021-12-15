#!/usr/bin/env python

try:
    import os
    import sys
    import time

    import tempfile
    from contextlib import contextmanager
    from copy import copy

    sys.path.append(os.path.dirname(__file__))

    from .platform_thrift_client import ThriftClient
    from .platform_thrift_client import thrift_try
    from .platform_thrift_client import pltfm_mgr_try

    from sonic_platform_base.sfp_base import SfpBase
    from sonic_platform_base.sonic_sfp.sfputilbase import SfpUtilBase
    from sonic_py_common import device_info
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")

SFP_TYPE = "SFP"
QSFP_TYPE = "QSFP"
QSFP_DD_TYPE = "QSFP_DD"


class SfpUtil(SfpUtilBase):
    """Platform-specific SfpUtil class"""

    PORT_START = 1
    PORT_END = 0
    PORTS_IN_BLOCK = 0
    QSFP_PORT_START = 1
    QSFP_PORT_END = 0
    EEPROM_OFFSET = 0
    QSFP_CHECK_INTERVAL = 4

    @property
    def port_start(self):
        self.update_port_info()
        return self.PORT_START

    @property
    def port_end(self):
        self.update_port_info()
        return self.PORT_END

    @property
    def qsfp_ports(self):
        self.update_port_info()
        return range(self.QSFP_PORT_START, self.PORTS_IN_BLOCK + 1)

    @property
    def port_to_eeprom_mapping(self):
        print("dependency on sysfs has been removed")
        raise Exception()

    def __init__(self):
        self.ready = False
        self.phy_port_dict = {'-1': 'system_not_ready'}
        self.phy_port_cur_state = {}
        self.qsfp_interval = self.QSFP_CHECK_INTERVAL

        SfpUtilBase.__init__(self)

    def update_port_info(self):
        def qsfp_max_port_get(client):
            return client.pltfm_mgr.pltfm_mgr_qsfp_get_max_port()

    def update_port_info(self):
        def qsfp_max_port_get(client):
            return client.pltfm_mgr.pltfm_mgr_qsfp_get_max_port()

        if self.QSFP_PORT_END == 0:
            platform = device_info.get_platform()
            self.QSFP_PORT_END = thrift_try(qsfp_max_port_get)
            exclude_cpu_port = [
                "x86_64-accton_as9516_32d-r0",
                "x86_64-accton_as9516bf_32d-r0",
                "x86_64-accton_wedge100bf_32x-r0"
            ]
            if platform in exclude_cpu_port:
                self.QSFP_PORT_END -= 1
            self.PORT_END = self.QSFP_PORT_END
            self.PORTS_IN_BLOCK = self.QSFP_PORT_END

    def get_presence(self, port_num):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end:
            return False

        presence = False

        def qsfp_presence_get(client):
            return client.pltfm_mgr.pltfm_mgr_qsfp_presence_get(port_num)

        try:
            presence = thrift_try(qsfp_presence_get)
        except Exception as e:
            print( e.__doc__)
            print(e.message)

        return presence

    def get_low_power_mode(self, port_num):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end:
            return False

        def qsfp_lpmode_get(client):
            return client.pltfm_mgr.pltfm_mgr_qsfp_lpmode_get(port_num)

        lpmode = thrift_try(qsfp_lpmode_get)

        return lpmode

    def set_low_power_mode(self, port_num, lpmode):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end:
            return False

        def qsfp_lpmode_set(client):
            return client.pltfm_mgr.pltfm_mgr_qsfp_lpmode_set(port_num, lpmode)

        status = thrift_try(qsfp_lpmode_set)

        return (status == 0)

    def get_tx_disable_channel(self, port_num, channel_num):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end:
            return True

        def qsfp_tx_is_disabled(client):
            return client.pltfm_mgr.pltfm_mgr_qsfp_tx_is_disabled(port_num, channel_num)

        tx_is_disabled = thrift_try(qsfp_tx_is_disabled, 1)

        return tx_is_disabled

    def tx_disable_channel(self, port_num, channel_mask, disable):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end:
            return False

        def qsfp_tx_disable_channel(client):
            return client.pltfm_mgr.pltfm_mgr_qsfp_tx_disable(port_num, channel_mask, disable)

        status = thrift_try(qsfp_tx_disable_channel)

        return (status == 0)

    def reset(self, port_num):
        # Check for invalid port_num
        if port_num < self.port_start or port_num > self.port_end:
            return False

        def qsfp_reset(client):
            client.pltfm_mgr.pltfm_mgr_qsfp_reset(port_num, True)
            return client.pltfm_mgr.pltfm_mgr_qsfp_reset(port_num, False)

        err = thrift_try(qsfp_reset)

        return not err

    def check_transceiver_change(self):
        if not self.ready:
            return

        self.phy_port_dict = {}

        try:
            client = ThriftClient().open()
        except Exception:
            return

        # Get presence of each SFP
        for port in range(self.port_start, self.port_end + 1):
            try:
                sfp_resent = client.pltfm_mgr.pltfm_mgr_qsfp_presence_get(port)
            except Exception:
                sfp_resent = False
            sfp_state = '1' if sfp_resent else '0'

            if port in self.phy_port_cur_state:
                if self.phy_port_cur_state[port] != sfp_state:
                    self.phy_port_dict[port] = sfp_state
            else:
                self.phy_port_dict[port] = sfp_state

            # Update port current state
            self.phy_port_cur_state[port] = sfp_state

        client.close()

    def get_transceiver_change_event(self, timeout=0):
        forever = False
        if timeout == 0:
            forever = True
        elif timeout > 0:
            timeout = timeout / float(1000) # Convert to secs
        else:
            print("get_transceiver_change_event:Invalid timeout value", timeout)
            return False, {}

        while forever or timeout > 0:
            if not self.ready:
                try:
                    with ThriftClient(): pass
                except Exception:
                    pass
                else:
                    self.ready = True
                    self.phy_port_dict = {}
                    break
            elif self.qsfp_interval == 0:
                self.qsfp_interval = self.QSFP_CHECK_INTERVAL

                # Process transceiver plug-in/out event
                self.check_transceiver_change()

                # Break if tranceiver state has changed
                if bool(self.phy_port_dict):
                    break

            if timeout:
                timeout -= 1

            if self.qsfp_interval:
                self.qsfp_interval -= 1

            time.sleep(1)

        return self.ready, self.phy_port_dict

    @contextmanager
    def eeprom_action(self):
        u = copy(self)
        with tempfile.NamedTemporaryFile() as f:
            u.eeprom_path = f.name
            yield u

    def _sfp_eeprom_present(self, client_eeprompath, offset):
        return client_eeprompath and super(SfpUtil, self)._sfp_eeprom_present(client_eeprompath, offset)

    def _get_port_eeprom_path(self, port_num, devid):
        def qsfp_info_get(client):
            return client.pltfm_mgr.pltfm_mgr_qsfp_info_get(port_num)

        if self.get_presence(port_num):
            eeprom_hex = thrift_try(qsfp_info_get)
            eeprom_raw = bytearray.fromhex(eeprom_hex)
            with open(self.eeprom_path, 'wb') as eeprom_cache:
                eeprom_cache.write(eeprom_raw)
            return self.eeprom_path

        return None

class Sfp(SfpBase):
    """Platform-specific Sfp class"""

    sfputil = SfpUtil()

    @staticmethod
    def port_start():
        return Sfp.sfputil.port_start

    @staticmethod
    def port_end():
        return Sfp.sfputil.port_end

    @staticmethod
    def qsfp_ports():
        return Sfp.sfputil.qsfp_ports()

    @staticmethod
    def get_transceiver_change_event(timeout=0):
        return Sfp.sfputil.get_transceiver_change_event()

    def __chan_count_get(self):
        def get_qsfp_chan_count(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_chan_count_get(self.index)
        err, count = pltfm_mgr_try(get_qsfp_chan_count)
        if err:
            return None
        return int(count)

    def __init__(self, port_num):
        self.index = port_num
        self.port_num = port_num
        self.sfp_type = QSFP_TYPE
        SfpBase.__init__(self)

    def get_presence(self):
        with Sfp.sfputil.eeprom_action() as u:
            return u.get_presence(self.port_num)

    def get_lpmode(self):
        with Sfp.sfputil.eeprom_action() as u:
            return u.get_low_power_mode(self.port_num)

    def set_lpmode(self, lpmode):
        with Sfp.sfputil.eeprom_action() as u:
            return u.set_low_power_mode(self.port_num, lpmode)

    def reset(self):
        return Sfp.sfputil.reset(self.port_num)

    def get_transceiver_info(self):
        with Sfp.sfputil.eeprom_action() as u:
            return u.get_transceiver_info_dict(self.port_num)

    def get_transceiver_bulk_status(self):
        status = dict()

        chan_count = self.__chan_count_get()
        if chan_count is None:
            return None

        rx_los = self.get_rx_los()
        status['rx_los'] = any(rx_los) if rx_los is not None else 'N/A'

        tx_fault = self.get_tx_fault()
        status['tx_fault'] = any(tx_fault) if tx_fault is not None else 'N/A'

        voltage = self.get_voltage()
        status['voltage'] = int(voltage) if voltage is not None else 'N/A'

        lp_mode = self.get_lpmode()
        status['lp_mode'] = lp_mode if lp_mode is not None else 'N/A'

        temperature = self.get_temperature()
        status['temperature'] = int(temperature) if temperature is not None else 'N/A'

        tx_bias = self.get_tx_bias()
        for n in range(chan_count):
            status[f'tx{n + 1}bias'] = int(tx_bias[n]) if tx_bias is not None else 'N/A'

        tx_power = self.get_tx_power()
        for n in range(chan_count):
            status[f'tx{n + 1}power'] = int(tx_power[n]) if tx_power is not None else 'N/A'

        rx_power = self.get_rx_power()
        for n in range(chan_count):
            status[f'rx{n + 1}power'] = int(rx_power[n]) if rx_power is not None else 'N/A'

        return status

    def get_change_event(self, timeout=0):
        return Sfp.get_transceiver_change_event(timeout)

    def is_replaceable(self):
        """
        Indicate whether this device is replaceable.
        Returns:
            bool: True if it is replaceable.
        """
        return True

    def get_name(self):
        """
        Retrieves the name of the device
            Returns:
            string: The name of the device
        """
        return "sfp{}".format(self.index)

    def get_model(self):
        """
        Retrieves the model number (or part number) of the device
        Returns:
            string: Model/part number of device
        """
        info = self.get_transceiver_info()
        return info.get("model", "N/A")

    def get_serial(self):
        """
        Retrieves the serial number of the device
        Returns:
            string: Serial number of device
        """
        info = self.get_transceiver_info()
        return info.get("serial", "N/A")

    def get_error_description(self):
        if not self.get_presence():
            return self.SFP_STATUS_UNPLUGGED
        return self.SFP_STATUS_OK

    def get_revision(self):
        info = self.get_transceiver_info()
        return info.get("hardware_rev", "N/A")

    def get_status(self):
        return self.get_presence() and bool(self.get_transceiver_bulk_status())

    def get_position_in_parent(self):
        return self.index

    def get_tx_disable(self):
        """
        Retrieves the tx_disable status of this SFP
        Returns:
            A Boolean, True if tx_disable is enabled, False if disabled
        """
        tx_disable_list = []
        with Sfp.sfputil.eeprom_action() as u:
            if self.sfp_type == QSFP_TYPE:
                tx_disable_list.append(u.get_tx_disable_channel(self.port_num, 0))
                tx_disable_list.append(u.get_tx_disable_channel(self.port_num, 1))
                tx_disable_list.append(u.get_tx_disable_channel(self.port_num, 2))
                tx_disable_list.append(u.get_tx_disable_channel(self.port_num, 3))
                return tx_disable_list
        return None

    def get_tx_disable_channel(self):
        """
        Retrieves the TX disabled channels in this SFP
        Returns:
            A hex of 4 bits (bit 0 to bit 3 as channel 0 to channel 3) to represent
            TX channels which have been disabled in this SFP.
            As an example, a returned value of 0x5 indicates that channel 0
            and channel 2 have been disabled.
        """
        if self.sfp_type == QSFP_TYPE:
            tx_disable_list = self.get_tx_disable()
            if tx_disable_list is None:
                return 0
            tx_disabled = 0
            for i in range(len(tx_disable_list)):
                if tx_disable_list[i]:
                    tx_disabled |= 1 << i
            return tx_disabled
        return None

    def tx_disable(self, tx_disable):
        """
        Disable SFP TX for all channels
        Args:
            tx_disable : A Boolean, True to enable tx_disable mode, False to disable
                         tx_disable mode.
        Returns:
            A boolean, True if tx_disable is set successfully, False if not
        """
        if self.sfp_type == QSFP_TYPE:
            return self.tx_disable_channel(0xF, tx_disable)
        return False

    def tx_disable_channel(self, channel, disable):
        """
        Sets the tx_disable for specified SFP channels
        Args:
            channel : A hex of 4 bits (bit 0 to bit 3) which represent channel 0 to 3,
                      e.g. 0x5 for channel 0 and channel 2.
            disable : A boolean, True to disable TX channels specified in channel,
                      False to enable
        Returns:
            A boolean, True if successful, False if not
        """
        with Sfp.sfputil.eeprom_action() as u:
            if self.sfp_type == QSFP_TYPE:
                return u.tx_disable_channel(self.port_num, channel, disable)
        return False

    def get_rx_los(self):
        def get_qsfp_rx_los(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_chan_rx_los_get(self.index)
        err, rx_los = pltfm_mgr_try(get_qsfp_rx_los)
        return rx_los

    def get_tx_los(self):
        def get_qsfp_tx_los(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_chan_tx_los_get(self.index)
        err, tx_los = pltfm_mgr_try(get_qsfp_tx_los)
        return tx_los

    def get_tx_fault(self):
        def get_qsfp_tx_fault(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_chan_tx_fault_get(self.index)
        err, tx_fault = pltfm_mgr_try(get_qsfp_tx_fault)
        return tx_fault

    def get_tx_bias(self):
        def get_qsfp_tx_bias(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_chan_tx_bias_get(self.index)
        err, tx_bias_A = pltfm_mgr_try(get_qsfp_tx_bias)
        if err:
            return None
        tx_bias_mA = [1000 * b for b in tx_bias_A]
        return tx_bias_mA

    def get_rx_power(self):
        def get_qsfp_rx_power(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_chan_rx_pwr_get(self.index)
        err, rx_W = pltfm_mgr_try(get_qsfp_rx_power)
        if err:
            return None
        rx_mW = [1000 * p for p in rx_W]
        return rx_mW

    def get_tx_power(self):
        def get_qsfp_tx_power(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_chan_tx_pwr_get(self.index)
        err, tx_W = pltfm_mgr_try(get_qsfp_tx_power)
        if err:
            return None
        tx_mW = [1000 * p for p in tx_W]
        return tx_mW

    def get_temperature(self):
        def get_qsfp_temp(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_temperature_get(self.index)
        err, temp_C = pltfm_mgr_try(get_qsfp_temp)
        return temp_C

    def get_voltage(self):
        def get_qsfp_voltage(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_voltage_get(self.index)
        err, voltage_V = pltfm_mgr_try(get_qsfp_voltage)
        if err:
            return None
        voltage_mV = voltage_V * 1000
        return voltage_mV

    def get_reset_status(self):
        def get_qsfp_reset(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_reset_get(self.index)
        err, status = pltfm_mgr_try(get_qsfp_reset, False)
        return status

    def get_power_override(self):
        def get_qsfp_power_override(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_pwr_override_get(self.index)
        err, pwr_override = pltfm_mgr_try(get_qsfp_power_override)
        return pwr_override

    def set_power_override(self, power_override, power_set):
        def set_qsfp_power_override(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_pwr_override_set(
                self.index, power_override, power_set
            )
        err, status = pltfm_mgr_try(set_qsfp_power_override)
        return status

    def get_transceiver_threshold_info(self):
        def qsfp_thres_info(pltfm_mgr):
            return pltfm_mgr.pltfm_mgr_qsfp_thresholds_get(self.index)

        err, ths = pltfm_mgr_try(qsfp_thres_info)
        if err:
            return None

        info = dict()

        info['rxpowerhighalarm'] = ths.rx_pwr.highalarm if ths.rx_pwr_is_set else 'N/A'
        info['rxpowerhighwarning'] = ths.rx_pwr.lowalarm if ths.rx_pwr_is_set else 'N/A'
        info['rxpowerlowalarm'] = ths.rx_pwr.highwarning if ths.rx_pwr_is_set else 'N/A'
        info['rxpowerlowwarning'] = ths.rx_pwr.lowwarning if ths.rx_pwr_is_set else 'N/A'
        info['temphighalarm'] = ths.temp.highalarm if ths.temp_is_set else 'N/A'
        info['temphighwarning'] = ths.temp.lowalarm if ths.temp_is_set else 'N/A'
        info['templowalarm'] = ths.temp.highwarning if ths.temp_is_set else 'N/A'
        info['templowwarning'] = ths.temp.lowwarning if ths.temp_is_set else 'N/A'
        info['txbiashighalarm'] = ths.tx_bias.highalarm if ths.tx_bias_is_set else 'N/A'
        info['txbiashighwarning'] = ths.tx_bias.lowalarm if ths.tx_bias_is_set else 'N/A'
        info['txbiaslowalarm'] = ths.tx_bias.highwarning if ths.tx_bias_is_set else 'N/A'
        info['txbiaslowwarning'] = ths.tx_bias.lowwarning if ths.tx_bias_is_set else 'N/A'
        info['txpowerhighalarm'] = ths.tx_pwr.highalarm if ths.tx_pwr_is_set else 'N/A'
        info['txpowerhighwarning'] = ths.tx_pwr.lowalarm if ths.tx_pwr_is_set else 'N/A'
        info['txpowerlowalarm'] = ths.tx_pwr.highwarning if ths.tx_pwr_is_set else 'N/A'
        info['txpowerlowwarning'] = ths.tx_pwr.lowwarning if ths.tx_pwr_is_set else 'N/A'
        info['vcchighalarm'] = ths.vcc.highalarm if ths.vcc_is_set else 'N/A'
        info['vcchighwarning'] = ths.vcc.lowalarm if ths.vcc_is_set else 'N/A'
        info['vcclowalarm'] = ths.vcc.highwarning if ths.vcc_is_set else 'N/A'
        info['vcclowwarning'] = ths.vcc.lowwarning if ths.vcc_is_set else 'N/A'

        return info

def sfp_list_get():
    sfp_list = []
    for index in range(Sfp.port_start(), Sfp.port_end() + 1):
        sfp_node = Sfp(index)
        sfp_list.append(sfp_node)
    return sfp_list
