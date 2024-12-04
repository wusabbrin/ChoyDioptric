# -*- coding: utf-8 -*-
"""
Output server for Multicomp Pro's 5.5 digit benchtop multimeter.
Programming manual here: https://www.farnell.com/datasheets/3205713.pdf

Created on August 10th, 2021

@author: mccambria

### BEGIN NODE INFO
[info]
name = temp_controller_THOR_tc200
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
import numpy
import serial


class TempControllerThorTc200(LabradServer):
    name = "temp_controller_THOR_tc200"
    pc_name = socket.gethostname()

    def initServer(self):
        filename = (
            "E:/Shared drives/Kolkowitz Lab"
            " Group/nvdata/pc_{}/labrad_logging/{}.log"
        )
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%y-%m-%d_%H-%M-%S",
            filename=filename,
        )
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)

    async def get_config(self):
        p = self.client.registry.packet()
        p.cd(["", "Config", "DeviceIDs"])
        p.get("{}_com".format(self.name))
        result = await p.send()
        return result["get"]

    def on_get_config(self, config):
        # Get the slider
        try:
            self.controller = serial.Serial(
                config,
                115200,
                serial.EIGHTBITS,
                serial.PARITY_NONE,
                serial.STOPBITS_ONE,
                timeout=2,
            )
        except Exception as e:
            logging.debug(e)
            del self.controller
        time.sleep(0.1)
        self.controller.flush()
        time.sleep(0.1)
        logging.info("Init complete")

    @setting(2, detector="s", unit="s")
    def config_measurement(self, c, detector, unit):
        """There is an option to measure temperature directly on this
        multimeter but it's buggy. In particular, the measurement
        stops returning values much outside room temperature if the unit is
        left on for several days. By monitioring the resistance directly
        we avoid this problem."""

        # Options ptc100, ptc1000, th10k
        self.controller.write("sns={}\r".format(detector).encode())
        self.controller.readline()
        # Options c, k, f
        self.controller.write("unit={}\r".format(unit).encode())
        self.controller.readline()

    @setting(5, returns="v[]")
    def measure(self, c):
        """Return the value from the main display."""
        self.controller.write(b"tact?\r")
        value = self.controller.readline()
        if value == "":
            logging.info("Read blank string in measure!")
            while value == "":
                time.sleep(0.1)
                value = self.controller.readline()
        # Extract the temp from the returned string.
        float_value = float(value.decode().split(" ")[1])
        # The box always writes temps to serial as C, so convert to K.
        return float_value + 273.15

    @setting(6)
    def reset_cfm_opt_out(self, c):
        """This setting is just a flag for the client. If you include this
        setting on a server, then the server won't be reset along with the
        rest of the instruments when we call tool_belt.reset_cfm.
        """
        pass

    # @setting(7)
    # def reset(self, c):
    #     """Fully reset to factory defaults"""
    #     pass


__server__ = TempControllerThorTc200()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)

    # with serial.Serial("COM8", 115200, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE, timeout=2) as controller:
    #     controller.write(b"sns=ptc100\r")
    #     controller.readline()
    #     # # controller.flush()
    #     controller.write(b"unit=k\r")
    #     controller.readline()
    #     # # controller.readline()
    #     # # controller.flush()
    #     controller.write(b"tact?\r")
    #     # # controller.flush()
    #     # time.sleep(0.1)
    #     value = controller.readline()

    #     print(float(value.decode().split(" ")[1]))
