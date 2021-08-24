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
import pyvisa as visa
import time


class PowerSupplyMp710087(LabradServer):
    name = "power_supply_mp710087"
    pc_name = socket.gethostname()
    reset_cfm_opt_out = True
    comms_delay = 0.1

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
        self.power_supply.query_delay = self.comms_delay
        self.power_supply.write("*RST")
        # The IDN command seems to help set up the box for further queries.
        # This may just be superstition though...
        time.sleep(0.1)
        idn = self.power_supply.query("*IDN?")
        time.sleep(0.1)
        logging.info(idn)
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
        
    @staticmethod
    def decode_query_response(response):
        """The instrument (sometimes at least...) returns values with a 
        leading \x00, which is a hex-escaped 0.
        """
        if response.startswith(chr(0)):
            response = response[1:]
        return float(response)

    @setting(7, returns="v[]")
    def meas_resistance(self, c):
        """Measure the resistance of the connected element by R = V / I.
        It seems the read operations on the power supply are slow and 
        serial will get out of sync if you run it too fast. Thus the 100 
        ms delays. There's also a 'query delay' baked into on_get_config. 
        This is an automatic delay between the write/read that makes up a 
        query. Plain writes (no subsequent read) seem to be fast.
        
        Returns
        ----------
        float
            Resistance in ohms
        """
        
        high_z = 10E3  # Typical "high" impedance on a scope
        
        time.sleep(self.comms_delay)
        
        response = self.power_supply.query("MEAS:VOLT?")
        voltage = self.decode_query_response(response)
        logging.info(repr(response))
        
        time.sleep(self.comms_delay)
        
        response = self.power_supply.query("MEAS:CURR?")
        current = self.decode_query_response(response)
        logging.info(repr(response))
        
        time.sleep(self.comms_delay)
        
        logging.info("")
        
        if current < 0.001: 
            resistance = high_z
        else:
            resistance = voltage / current
            
        return resistance

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
