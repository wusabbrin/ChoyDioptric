# -*- coding: utf-8 -*-
"""
Timing server for the Swabian Pulse Stream 8/2.

Created on Tue Apr  9 17:12:27 2019

@author: mccambria

### BEGIN NODE INFO
[info]
name = pulse_gen_SWAB_82
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
import importlib
import os
import sys
sys.path.insert(0, 'C:\\Users\\choyl\\ChoyDioptric')  # Add parent directory to path
import utils.tool_belt as tool_belt
import logging
import socket
from pathlib import Path
from servers.timing.interfaces.pulse_gen import PulseGen
from pulsestreamer import PulseStreamer
from pulsestreamer import TriggerStart
from pulsestreamer import OutputState



class PulseGenSwab82(PulseGen, LabradServer):
    name = "pulse_gen_SWAB_82"
    pc_name = socket.gethostname()

    def initServer(self):
        filename = (
            "D:/Choy_Lab/"
            "sivdata/labrad_logging/{}.log"
        )
        filename = filename.format(self.name)
        logging.basicConfig(
            level=logging.INFO,
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
        p.dir()
        result = await p.send()
        return result

    def on_get_config(self, config):
        self.pulse_streamer = PulseStreamer(config["get"])
        calibration = self.pulse_streamer.getAnalogCalibration()
        logging.info(calibration)
        # sequence_library_path = os.path.join(
        #     "C:\\Users\\choyl\\ChoyDioptric\\servers\\timing\\sequencelibrary",
        #     self.name
        # )
        sequence_library_path = Path("C:/Users/choyl/ChoyDioptric/servers/timing/sequencelibrary") / self.name

    #     sequence_library_path = (
    #     Path.home()s
    #     / "ChoyDioptric/servers/timing/sequencelibrary"
    #     / self.name
    # )
        sys.path.append(str(sequence_library_path))
        self.get_config_dict()

    def get_config_dict(self):
        """
        Get the config dictionary on the registry recursively. Very similar
        to the function of the same name in tool_belt.
        """
        config_dict = {}
        _ = ensureDeferred(
            self.populate_config_dict(["", "Config"], config_dict)
        )
        _.addCallback(self.on_get_config_dict, config_dict)

    async def populate_config_dict(self, reg_path, dict_to_populate):
        """Populate the config dictionary recursively"""

        # Sub-folders
        p = self.client.registry.packet()
        p.cd(reg_path)
        p.dir()
        result = await p.send()
        sub_folders, keys = result["dir"]
        for el in sub_folders:
            sub_dict = {}
            sub_path = reg_path + [el]
            await self.populate_config_dict(sub_path, sub_dict)
            dict_to_populate[el] = sub_dict

        # Keys
        if len(keys) == 1:
            p = self.client.registry.packet()
            p.cd(reg_path)
            key = keys[0]
            p.get(key)
            result = await p.send()
            val = result["get"]
            dict_to_populate[key] = val

        elif len(keys) > 1:
            p = self.client.registry.packet()
            p.cd(reg_path)
            for key in keys:
                p.get(key)
            result = await p.send()
            vals = result["get"]

            for ind in range(len(keys)):
                key = keys[ind]
                val = vals[ind]
                dict_to_populate[key] = val

    def on_get_config_dict(self, _, config_dict):
        self.config_dict = config_dict
        self.pulse_streamer_wiring = self.config_dict["Wiring"]["PulseGen"]
        logging.info(self.pulse_streamer_wiring)
        
        # Initialize state variables and reset
        self.seq = None
        self.loaded_seq_streamed = False
        self.reset(None)
        logging.info("Init complete")

    def get_seq(self, seq_file, seq_args_string):
        seq = None
        file_name, file_ext = os.path.splitext(seq_file)
        if file_ext == ".py":  # py: import as a module
            seq_module = importlib.import_module(file_name)
            args = tool_belt.decode_seq_args(seq_args_string)
            seq, final, ret_vals = seq_module.get_seq(
                self, self.config_dict, args
            )
        return seq, final, ret_vals

    @setting(2, seq_file="s", seq_args_string="s", returns="*?")
    def stream_load(self, c, seq_file, seq_args_string=""):
        """Load the sequence from seq_file. Set it to end in the specified
        final output state. The sequence will not run until you call
        stream_start.

        Params
            seq_file: str
                A sequence file from the sequence library
            args: list(any)
                Arbitrary list used to modulate a sequence from the sequence
                library - see simple_readout.py for an example. Default is
                None

        Returns
            list(any)
                Arbitrary list returned by the sequence file
        """

        self.pulse_streamer.setTrigger(start=TriggerStart.SOFTWARE)
        seq, final, ret_vals = self.get_seq(seq_file, seq_args_string)
        if seq is not None:
            self.seq = seq
            self.loaded_seq_streamed = False
            self.final = final
        return ret_vals

    @setting(3, num_repeat="i")
    def stream_start(self, c, num_repeat=1):
        """Run the currently loaded stream for the specified number of
        repitions.

        Params
            num_repeat: int
                Number of times to repeat the sequence. Default is 1
        """
                
        if self.seq == None:
            raise RuntimeError("Stream started with no sequence.")
        if not self.loaded_seq_streamed:
            self.pulse_streamer.stream(self.seq, num_repeat, self.final)
            self.loaded_seq_streamed = True
        self.pulse_streamer.startNow()

    @setting(
        4,
        digital_channels="*i",
        analog_0_voltage="v[]",
        analog_1_voltage="v[]",
    )
    def constant(
        self,
        c,
        digital_channels=[],
        analog_0_voltage=0.0,
        analog_1_voltage=0.0,
    ):
        """Set the PulseStreamer to a constant output state."""

        digital_channels = [int(el) for el in digital_channels]
        state = OutputState(
            digital_channels, analog_0_voltage, analog_1_voltage
        )
        self.pulse_streamer.constant(state)

    @setting(5)
    def force_final(self, c):
        """Force the PulseStreamer its current final output state.
        Essentially a stop command.
        """

        self.pulse_streamer.forceFinal()

    @setting(6)
    def reset(self, c):
        # Probably don't need to force_final right before constant but...
        self.force_final(c)
        self.constant(
            c, digital_channels=[], analog_0_voltage=0.0, analog_1_voltage=0.0
        )
        self.seq = None
        self.loaded_seq_streamed = False


__server__ = PulseGenSwab82()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
