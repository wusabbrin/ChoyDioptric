# -*- coding: utf-8 -*-
"""
Combined server for galvo and objective_piezo

Created on July 2021

@author: mccambria

### BEGIN NODE INFO
[info]
name = pos_xyz_THOR_gvs212_PI_pifoc
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
import nidaqmx.stream_writers as stream_writers
import numpy
import logging
import socket
from pipython import GCSDevice
from pathlib import Path
from servers.outputs.pos_xy_THOR_gvs212 import PosXyThorGvs212
from servers.outputs.pos_z_PI_pifoc import PosZPiPifoc


class PosXyzThorgvs212PiPifoc(PosXyThorGvs212, PosZPiPifoc):
    name = "pos_xyz_THOR_gvs212_PI_pifoc"
    pc_name = socket.gethostname()

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
        self.task = None
        self.sub_init_server_xy()
        self.sub_init_server_z()
        logging.info('Init complete')

    def stopServer(self):
        self.close_task_internal()

    @setting(100, coords_x="*v[]", coords_y="*v[]", coords_z="*v[]", continuous="b")
    def load_stream_xyz(self, c, coords_x, coords_y, coords_z, continuous=False):

        
        voltages = numpy.vstack((coords_x, coords_y, coords_z))
        
        # Close the existing task if there is one
        if self.task is not None:
            self.close_task_internal()

        # Write the initial voltages and stream the rest
        num_voltages = voltages.shape[1]
        self.write_xy(c, voltages[0, 0], voltages[1, 0])
        self.write_z(c, voltages[2, 0])
        stream_voltages = voltages[:, 1:num_voltages]
        stream_voltages = numpy.ascontiguousarray(stream_voltages)
        num_stream_voltages = num_voltages - 1

        # Create a new task
        task = nidaqmx.Task(f"{self.name}-load_stream_xyz")
        self.task = task

        # Set up the output channels
        task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_galvo_x, min_val=-10.0, max_val=10.0
        )
        task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_galvo_y, min_val=-10.0, max_val=10.0
        )
        task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_objective_piezo, min_val=1.0, max_val=9.0
        )

        # Set up the output stream
        output_stream = nidaqmx.task.OutStream(task)
        writer = stream_writers.AnalogMultiChannelWriter(output_stream)

        # Configure the sample to advance on the rising edge of the PFI input.
        # The frequency specified is just the max expected rate in this case.
        # We'll stop once we've run all the samples.
        freq = 100  # Just guess a data rate of 100 Hz
        task.timing.cfg_samp_clk_timing(
            freq, source=self.daq_di_clock, samps_per_chan=num_stream_voltages
        )

        writer.write_many_sample(stream_voltages)

        # Close the task once we've written all the samples
        task.register_done_event(self.close_task_internal)

        task.start()

    @setting(200, xVoltage="v[]", yVoltage="v[]", zVoltage="v[]")
    def write_xyz(self, c, xVoltage, yVoltage, zVoltage):
        """Write the specified voltages to the galvo.

        Params
            xVoltage: float
                Voltage to write to the x channel
            yVoltage: float
                Voltage to write to the y channel
            zVoltage: float
                Voltage to write to the z channel
        """

        self.write_xy(c, [xVoltage], [yVoltage])
        self.write_z(c, [zVoltage])
  

__server__ = PosXyzThorgvs212PiPifoc()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
