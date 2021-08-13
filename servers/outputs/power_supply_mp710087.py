# -*- coding: utf-8 -*-
"""
Output server for Multicomp Pro's 0-60 V, 0-3 A benchtop linear power supply

Created on August 10th, 2021

@author: mccambria

### BEGIN NODE INFO
[info]
name = power_supply_mp710087
version = 1.0
description =

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 
### END NODE INFO
"""


from labrad.server import LabradServer
from labrad.server import setting
from twisted.internet.defer import ensureDeferred
import logging
import socket
import visa
import time


class PowerSupplyMp710087(LabradServer):
    name = "power_supply_mp710087"
    pc_name = socket.gethostname()
    reset_cfm_opt_out = True

    def initServer(self):
        filename = (
            "E:/Shared drives/Kolkowitz Lab Group/nvdata/pc_{}/labrad_logging/{}.log"
        )
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%y-%m-%d_%H-%M-%S",
            filename=filename,
        )
        self.current_limit = None
        self.voltage_limit = None
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)

    async def get_config(self):
        p = self.client.registry.packet()
        p.cd(["", "Config", "DeviceIDs"])
        p.get("{}_visa_address".format(self.name))
        result = await p.send()
        return result["get"]

    def on_get_config(self, config):
        resource_manager = visa.ResourceManager()
        visa_address = config
        logging.info(visa_address)
        # visa_address = 'MCCTEST'
        self.power_supply = resource_manager.open_resource(visa_address)
        self.power_supply.baud_rate = 115200
        self.power_supply.read_termination = '\n'
        self.power_supply.write_termination = '\n'
        logging.info(self.power_supply)
        self.power_supply.write("*RST")
        logging.info('MCCTEST')
        self.power_supply.write('*IDN?')
        # for i in range(30):
        #     logging.debug(self.power_supply.read_bytes(1))
        test = self.power_supply.read()
        # test = self.multimeter.query("*IDN?")
        logging.info(test)
        logging.info("Init complete")

    @setting(0)
    def output_on(self, c):
        self.power_supply.write("OUTP ON")

    @setting(1)
    def output_off(self, c):
        self.power_supply.write("OUTP OFF")

    @setting(2, limit="v[]")
    def set_current_limit(self, c, limit):
        """Set the maximum current the instrument will allow (up to 3 A)

        Parameters
        ----------
        limit : float
            Current limit in amps
        """
        self.current_limit = limit
        self.power_supply.write("CURR:LIM {}".format(limit))

    @setting(3, limit="v[]")
    def set_voltage_limit(self, c, limit):
        """Set the maximum voltage the instrument will allow (up to 60 V)

        Parameters
        ----------
        limit : float
            Voltage limit in volts
        """
        self.voltage_limit = limit
        self.power_supply.write("VOLT:LIM {}".format(limit))

    @setting(4, val="v[]")
    def set_current(self, c, val):
        """
        Parameters
        ----------
        val : float
            Current to set in amps
        """
        lim = self.current_limit
        if (lim is not None) and (val > lim):
            val = lim
        self.power_supply.write("CURR {}".format(val))

    @setting(5, val="v[]")
    def set_voltage(self, c, val):
        """
        Parameters
        ----------
        val : float
            Voltage to set in volts
        """
        lim = self.voltage_limit
        if (lim is not None) and (val > lim):
            val = lim
        self.power_supply.write("VOLT {}".format(val))

    @setting(6)
    def reset(self, c):
        """Reset the power supply. Turn off the output, leave the current
        and voltage limits as they are. This instrument is not reset 
        tool_belt.reset_cfm
        """
        self.output_off(c)


__server__ = PowerSupplyMp710087()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
