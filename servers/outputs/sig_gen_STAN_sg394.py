# -*- coding: utf-8 -*-
"""
Output server for the SRS SG394 microwave signal generator.

Created on Wed Apr 10 12:53:38 2019

@author: mccambria

### BEGIN NODE INFO
[info]
name = sig_gen_STAN_sg394
version = 1.0
description =

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 5
### END NODE INFO
"""

from labrad.server import LabradServer
from labrad.server import setting
from twisted.internet.defer import ensureDeferred
import socket
import logging
import pyvisa as visa  # Docs here: https://pyvisa.readthedocs.io/en/master/
from servers.outputs.interfaces.sig_gen_vector import SigGenVector


class SigGenStanSg394(LabradServer, SigGenVector):
    name = "sig_gen_STAN_sg394"
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
        p.get(f"{self.name}_visa")
        p.cd(["", "Config", "Wiring", "Daq"])
        p.get("di_clock")
        result = await p.send()
        return result["get"]

    def on_get_config(self, config):
        resource_manager = visa.ResourceManager()
        self.sig_gen = resource_manager.open_resource(config[0])
        # Set the VISA read and write termination. This is specific to the
        # instrument - you can find it in the instrument's programming manual
        self.sig_gen.read_termination = "\r\n"
        self.sig_gen.write_termination = "\r\n"
        # Set our channels for FM
        self.daq_di_pulser_clock = config[1]
        # self.daq_ao_sig_gen_mod = config[2]
        self.task = None  # Initialize state variable
        self.reset(None)
        logging.info("Init complete")

    @setting(0)
    def uwave_on(self, c):
        """Turn on the signal. This is like opening an internal gate on
        the signal generator.
        """

        self.sig_gen.write("ENBR 1")

    @setting(1)
    def uwave_off(self, c):
        """Turn off the signal. This is like closing an internal gate on
        the signal generator.
        """

        self.sig_gen.write("ENBR 0")

    @setting(2, freq="v[]")
    def set_freq(self, c, freq):
        """Set the frequency of the signal.

        Params
            freq: float
                The frequency of the signal in GHz
        """

        # Determine how many decimal places we need
        precision = len(str(freq).split(".")[1])
        self.sig_gen.write("FREQ {0:.{1}f} GHZ".format(freq, precision))

    @setting(3, amp="v[]")
    def set_amp(self, c, amp):
        """Set the amplitude of the signal.

        Params
            amp: float
                The amplitude of the signal in dBm
        """

        # Determine how many decimal places we need
        precision = len(str(amp).split(".")[1])
        cmd = "AMPR {0:.{1}f} DBM".format(amp, precision)
        # logging.info(cmd)
        self.sig_gen.write(cmd)

    @setting(5)
    def mod_off(self, c):
        """Turn off the modulation."""

        self.sig_gen.write("MODL 0")
        task = self.task
        if task is not None:
            task.close()

    @setting(7)
    def load_iq(self, c):
        """
        Set up external IQ modulation
        """

        # The sg394 only supports up to 10 dBm of power output with IQ modulation
        # Let's check what the amplitude is set as, and if it's over 10 dBm,
        # we'll quit out and save a note in the labrad logging
        if float(self.sig_gen.query("AMPR?")) > 10:
            msg = (
                "IQ modulation on sg394 supports up to 10 dBm. The power was"
                " set to {} dBm and the operation was stopped.".format(
                    self.sig_gen.query("AMPR?")
                )
            )
            raise Exception(msg)
            return

        # QAM is type 7
        self.sig_gen.write("TYPE 7")
        # STYP 1 is vector modulation
        # self.sig_gen.write('STYP 1')
        # External mode is modulation function 5
        self.sig_gen.write("QFNC 5")
        # Turn on modulation
        cmd = "MODL 1"
        self.sig_gen.write(cmd)
        # logging.info(cmd)
        
    @setting(8, deviation='v[]')
    def load_fm(self, c, deviation):
        """
        Set up frequency modulation using a nexternal analog source
        Parameters
        ----------
        deviation : float
            The deviation ofthe frequency, in MHz. Max value is 6 MHz.

        Returns
        -------
        None.

        """
        # logging.info("test")
        
        # FM is type 1
        self.sig_gen.write('TYPE 1')
        # STYP 1 is analog modulation
        self.sig_gen.write('STYP 0')
        # external is 5
        self.sig_gen.write('MFNC 5')
        #set the rate? For external this is 100 kHz
        # self.sig_gen.write('RATE 100 kHz')
        #set the deviation
        cmd = 'FDEV {} MHz'.format(deviation)
        self.sig_gen.write(cmd)
        # Turn on modulation
        cmd = 'MODL 1'
        self.sig_gen.write(cmd)
        
    @setting(6)
    def reset(self, c):
        self.sig_gen.write("FDEV 0")
        cmd = 'MODL 0'
        self.sig_gen.write(cmd)
        self.uwave_off(c)
        self.mod_off(c)


__server__ = SigGenStanSg394()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
