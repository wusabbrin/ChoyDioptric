# -*- coding: utf-8 -*-
"""
Output server for the attodry800's piezos. See the physical manual from the
attodry for more information about how we're communicating with the piezos
and how the piezos work physically. The axes are numeric, with x:1, y:2, z:3.

Created on Tue Dec 29 2020

@author: mccambria

### BEGIN NODE INFO
[info]
name = pos_xyz_ATTO_piezos
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
import socket
import logging

# telnetlib is a package for connecting to networked device over the telnet
# protocol. See the ANC150 section of the cryostat manual for more details on
# this connection
from telnetlib import Telnet


class PosXyzAttoPiezos(LabradServer):
    name = "pos_xyz_ATTO_piezos"
    pc_name = socket.gethostname()

    def initServer(self):
        filename = (
            "E:/Shared drives/Kolkowitz Lab"
            " Group/nvdata/pc_{}/labrad_logging/{}.log"
        )
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%y-%m-%d_%H-%M-%S",
            filename=filename,
        )
        self.task = None
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)

    async def get_config(self):
        p = self.client.registry.packet()
        p.cd(["", "Config", "DeviceIDs"])
        p.get(f"{self.name}_ip")
        p.cd(["", "Config", "Positioning"])
        p.get("cryo_piezos_voltage")
        p.get("z_bias_adjust")
        result = await p.send()
        return result["get"]

    def on_get_config(self, reg_vals):
        ip_address = reg_vals[0]
        cryo_piezos_voltage = reg_vals[1]
        self.z_bias_adjust = reg_vals[2]
        if self.z_bias_adjust >= 0.5:
            raise ValueError("abs(bias adjust) must be < 0.5")
        # Connect via telnet
        try:
            self.piezos = Telnet(ip_address, 7230)
        except Exception as e:
            logging.debug(e)
            del self.piezos
        # Read until we're prompted for a password
        self.piezos.read_until(b"Authorization code: ")
        # Enter the default password
        self.piezos.write(b"123456\r\n")
        # Read until we're prompted for a command
        self.piezos.read_until(b"> ")
        # Make sure all the axis modes are set to ground, with default
        # frequency and voltage of 1000 Hz and 30 V
        self.send_cmd_all("setm", "gnd")
        self.send_cmd_all("setf", 1000)
        self.send_cmd_all("setv", cryo_piezos_voltage)
        # Initialize positions to 0 steps
        self.pos = [0, 0, 0]
        # Done
        logging.debug("Init complete")

    def write_ax(self, pos_in_steps, ax):

        steps_to_move = pos_in_steps - self.pos[ax - 1]
        if steps_to_move == 0:
            return

        # Set to step mode
        self.send_cmd("setm", ax, "stp")

        # Calculate the differential number of steps from where we're at
        abs_steps_to_move = abs(steps_to_move)

        if steps_to_move > 0:
            cmd = "stepu"
            # if ax == 3:
            #     abs_steps_to_move = round((1+self.z_bias_adjust)*abs_steps_to_move)
        else:
            cmd = "stepd"
            if ax == 3:
                abs_steps_to_move = round(
                    (1 - self.z_bias_adjust) * abs_steps_to_move
                )
        self.send_cmd(cmd, ax, abs_steps_to_move)

        # Set to ground mode once we're done stepping
        self.send_cmd("stepw", ax)
        self.send_cmd("setm", ax, "gnd")

        # Cache the position
        self.pos[ax - 1] = pos_in_steps

    def send_cmd(self, cmd, axis, arg=None):
        """
        Set attribute to value for the specified axis. See the manual for
        command details
        """

        # Make sure this is a valid command
        if cmd not in [
            "setm",
            "setf",
            "setv",
            "seta",
            "stepw",
            "stepu",
            "stepd",
        ]:
            msg = "Attempted to perform invalid command: {}".format(cmd)
            logging.debug(msg)
            return

        # Encode to ascii
        cmd_enc = cmd.encode("ascii")
        axis_enc = str(axis).encode("ascii")

        if arg is not None:
            arg_enc = str(arg).encode("ascii")
            self.piezos.write(
                cmd_enc + b" " + axis_enc + b" " + arg_enc + b"\r\n"
            )
        else:
            self.piezos.write(cmd_enc + b" " + axis_enc + b"\r\n")
        self.piezos.read_until(b"> ")

    def send_cmd_all(self, cmd, arg=None):
        """Send a command to all three axes"""
        for axis in [1, 2, 3]:
            self.send_cmd(cmd, axis, arg)

    @setting(2, pos_in_steps="i")
    def write_z(self, c, pos_in_steps):
        """
        Specify the absolute position in steps relative to 0. There will be
        hysteresis on this value, but it's repeatable enough for the
        common and important routines (eg optimize)
        """

        self.write_ax(pos_in_steps, 3)

    @setting(3, x_pos_in_steps="i", y_pos_in_steps="i")
    def write_xy(self, c, x_pos_in_steps, y_pos_in_steps):
        """
        Specify the absolute position in steps relative to 0. There will be
        hysteresis on this value, but it's repeatable enough for the
        common and important routines (eg optimize)
        """

        self.write_ax(x_pos_in_steps, 1)
        self.write_ax(y_pos_in_steps, 2)

    @setting(4, voltage="i", axes="*i")
    def set_voltage(self, c, voltage, axes=[1, 2, 3]):
        """
        Set the voltage of the sawtooth wave used to drive a piezo
        """

        self.send_cmd_all("setm", "gnd")
        for axis in axes:
            self.send_cmd("setv", axis, voltage)


__server__ = PosXyzAttoPiezos()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
