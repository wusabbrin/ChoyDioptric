# -*- coding: utf-8 -*-
"""
Output server for the Thorlabs GVS212 galvanometer. Controlled by an NI DAQ.

Created on April 8th, 2019

@author: mccambria

### BEGIN NODE INFO
[info]
name = pos_xy_THOR_gvs212
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
import nidaqmx
from nidaqmx.constants import AcquisitionType
import nidaqmx.stream_writers as stream_writers
import numpy as np
import logging
import socket
from servers.outputs.interfaces.pos_xy_stream import PosXyStream


class PosXyThorGvs212(LabradServer, PosXyStream):
    name = "pos_xy_THOR_gvs212"
    pc_name = socket.gethostname()

    def initServer(self):
        filename = (
            "E:/Shared drives/Kolkowitz Lab" " Group/nvdata/pc_{}/labrad_logging/{}.log"
        )
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%y-%m-%d_%H-%M-%S",
            filename=filename,
        )
        self.task = None
        self.sub_init_server_xy()

    def sub_init_server_xy(self):
        """Sub-routine to be called by xyz server"""
        config = ensureDeferred(self.get_config_xy())
        config.addCallback(self.on_get_config_xy)

    async def get_config_xy(self):
        p = self.client.registry.packet()
        p.cd(["", "Config", "Wiring", "Daq"])
        p.get("ao_galvo_x")
        p.get("ao_galvo_y")
        p.get("di_clock")
        result = await p.send()
        return result["get"]

    def on_get_config_xy(self, config):
        self.daq_ao_galvo_x = config[0]
        self.daq_ao_galvo_y = config[1]
        self.daq_di_clock = config[2]
        logging.debug("Init complete")

    def stopServer(self):
        self.close_task_internal()

    def close_task_internal(self, task_handle=None, status=None, callback_data=None):
        task = self.task
        if task is not None:
            task.close()
            self.task = None
        return 0

    @setting(0, xVoltage="v[]", yVoltage="v[]")
    def write_xy(self, c, xVoltage, yVoltage):
        """Write the specified voltages to the galvo.

        Params
            xVoltage: float
                Voltage to write to the x channel
            yVoltage: float
                Voltage to write to the y channel
        """

        # Close the stream task if it exists
        # This can happen if we quit out early
        if self.task is not None:
            self.close_task_internal()

        with nidaqmx.Task() as task:
            # Set up the output channels
            task.ao_channels.add_ao_voltage_chan(
                self.daq_ao_galvo_x, min_val=-10.0, max_val=10.0
            )
            task.ao_channels.add_ao_voltage_chan(
                self.daq_ao_galvo_y, min_val=-10.0, max_val=10.0
            )
            task.write([xVoltage, yVoltage])

    @setting(1, returns="*v[]")
    def read_xy(self, c):
        """Return the current voltages on the x and y channels.

        Returns
            list(float)
                Current voltages on the x and y channels

        """
        with nidaqmx.Task() as task:
            # Set up the internal channels - to do: actual parsing...
            if self.daq_ao_galvo_x == "dev1/AO0":
                chan_name = "dev1/_ao0_vs_aognd"
            task.ai_channels.add_ai_voltage_chan(chan_name, min_val=-10.0, max_val=10.0)
            if self.daq_ao_galvo_y == "dev1/AO1":
                chan_name = "dev1/_ao1_vs_aognd"
            task.ai_channels.add_ai_voltage_chan(chan_name, min_val=-10.0, max_val=10.0)
            voltages = task.read()

        return voltages[0], voltages[1]

    @setting(2, coords_x="*v[]", coords_y="*v[]", continuous="b")
    def load_stream_xy(self, c, coords_x, coords_y, continuous=False):

        voltages = np.vstack((coords_x, coords_y))

        # Close the existing task if there is one
        if self.task is not None:
            self.close_task_internal()

        # Write the initial voltages and stream the rest
        num_voltages = voltages.shape[1]
        self.write_xy(c, voltages[0, 0], voltages[1, 0])
        if continuous:
            # Perfect loop for continuous
            stream_voltages = np.roll(voltages, -1, axis=1)
        else:
            stream_voltages = voltages[:, 1:num_voltages]
        stream_voltages = np.ascontiguousarray(stream_voltages)
        num_stream_voltages = num_voltages - 1
        # Create a new task
        task = nidaqmx.Task(f"{self.name}-load_stream_xy")
        self.task = task

        # Set up the output channels
        task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_galvo_x, min_val=-10.0, max_val=10.0
        )
        task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_galvo_y, min_val=-10.0, max_val=10.0
        )

        # Set up the output stream
        output_stream = nidaqmx.task.OutStream(task)
        writer = stream_writers.AnalogMultiChannelWriter(output_stream)

        # Configure the sample to advance on the rising edge of the PFI input.
        # The frequency specified is just the max expected rate in this case.
        # We'll stop once we've run all the samples.
        freq = 100  # Just guess a data rate of 100 Hz
        if continuous:
            task.timing.cfg_samp_clk_timing(
                freq,
                source=self.daq_di_clock,
                samps_per_chan=num_stream_voltages,
                sample_mode=AcquisitionType.CONTINUOUS,
            )
        else:
            task.timing.cfg_samp_clk_timing(
                freq,
                source=self.daq_di_clock,
                samps_per_chan=num_stream_voltages,
            )

        writer.write_many_sample(stream_voltages)

        # Close the task once we've written all the samples
        task.register_done_event(self.close_task_internal)
        task.start()
        
    @setting(3)
    def reset(self, c):
        self.close_task_internal()


__server__ = PosXyThorGvs212()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
