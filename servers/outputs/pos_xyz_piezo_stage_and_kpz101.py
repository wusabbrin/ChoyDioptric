# -*- coding: utf-8 -*-
"""
Combined server for galvo and objective_piezo

Created on November 2021

@author: agardill

### BEGIN NODE INFO
[info]
name = piezo_stage_and_kpz101
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
from servers.outputs.piezo_stage_626_2cd import PiezoStage
from servers.outputs.z_piezo_kpz101 import ZPiezoKpz101


class PiezoStageAndPKZ101(PiezoStage, ZPiezoKpz101):
    name = "piezo_stage_and_kpz101"
    pc_name = socket.gethostname()

    def initServer(self):
        filename = (
            "E:/Shared drives/Kolkowitz Lab Group/nvdata/pc_{}/labrad_logging/{}.log"
        )
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%y-%m-%d_%H-%M-%S",
            filename=filename,
        )
        self.task = None
        
        logging.debug("before init")
        self.sub_init_server_xy()
        self.sub_init_server_z()
        logging.debug("Init Complete")

    def stopServer(self):
        self.close_task_internal()

    def load_stream_writer_xyz(self, c, task_name, voltages, period):

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
        task = nidaqmx.Task(task_name)
        self.task = task

        # Set up the output channels
        task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_piezo_stage_x, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
        )
        task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_piezo_stage_y, min_val=-self.daq_voltage_range_factor, 
                                        max_val=self.daq_voltage_range_factor
        )
        task.ao_channels.add_ao_voltage_chan(
            self.daq_ao_z_piezo_kpz101, min_val=0.0, max_val=10.0
        )

        # Set up the output stream
        output_stream = nidaqmx.task.OutStream(task)
        writer = stream_writers.AnalogMultiChannelWriter(output_stream)

        # Configure the sample to advance on the rising edge of the PFI input.
        # The frequency specified is just the max expected rate in this case.
        # We'll stop once we've run all the samples.
        freq = float(1 / (period * (10 ** -9)))  # freq in seconds as a float
        task.timing.cfg_samp_clk_timing(
            freq, source=self.daq_di_clock, samps_per_chan=num_stream_voltages
        )

        writer.write_many_sample(stream_voltages)

        # Close the task once we've written all the samples
        task.register_done_event(self.close_task_internal)

        task.start()

    @setting(11, x_points="*v[]", y_points="*v[]", z_points="*v[]", period="i")
    def load_arb_scan_xyz(self, c, x_points, y_points, z_points, period):
        """
        Load a scan around a seuqence of arbitrary xyz points 

        Params
            x_points: list(float)
                X values correspnding to positions in x
            y_points: list(float)
                Y values correspnding to positions in y
            z_points: list(float)
                Z values correspnding to positions in z
            period: int
                Expected period between clock signals in ns

        """

        voltages = numpy.vstack((x_points, y_points, z_points))

        self.load_stream_writer_xyz(
            c, "GalvoAndObjectivePiezo-load_arb_scan_xyz", voltages, period
        )

        return
    
    @setting(
        12,
        x_center="v[]",
        z_center="v[]",
        x_range="v[]",
        z_range="v[]",
        num_steps="i",
        period="i",
        returns="*v[]*v[]",
    )
    def load_sweep_scan_xz(
        self, c, x_center, y_center, z_center, x_range, z_range, num_steps, period
    ):
        """Load a scan that will wind through the grid defined by the passed
        parameters. Samples are advanced by the clock.

        Normal scan performed, starts in bottom right corner, and starts
        heading left
        

        Params
            x_center: float
                Center x voltage of the scan
            y_center: float
                Center position y voltage (won't change in y)
            z_center: float
                Center z voltage of the scan
            x_range: float
                Full scan range in x
            z_range: float
                Full scan range in z
            num_steps: int
                Number of steps the break the ranges into
            period: int
                Expected period between clock signals in ns

        Returns
            list(float)
                The x voltages that make up the scan
            list(float)
                The z voltages that make up the scan
        """

        # Must use same number of steps right now
        x_num_steps = num_steps
        z_num_steps = num_steps

        # Force the scan to have square pixels by only applying num_steps
        # to the shorter axis
        half_x_range = x_range / 2
        half_z_range = z_range / 2

        x_low = x_center - half_x_range
        x_high = x_center + half_x_range
        z_low = z_center - half_z_range
        z_high = z_center + half_z_range

        # Apply scale and offset to get the voltages we'll apply.
        x_voltages_1d = numpy.linspace(x_low, x_high, num_steps)
        z_voltages_1d = numpy.linspace(z_low, z_high, num_steps)
    

        ######### Works for any x_range, y_range #########

        # Winding cartesian product
        # The x values are repeated and the z values are mirrored and tiled
        # The comments below shows what happens for [1, 2, 3], [4, 5, 6]

        # [1, 2, 3] => [1, 2, 3, 3, 2, 1]
        x_inter = numpy.concatenate((x_voltages_1d, numpy.flipud(x_voltages_1d)))
        # [1, 2, 3, 3, 2, 1] => [1, 2, 3, 3, 2, 1, 1, 2, 3]
        if z_num_steps % 2 == 0:  # Even x size
            x_voltages = numpy.tile(x_inter, int(z_num_steps / 2))
        else:  # Odd x size
            x_voltages = numpy.tile(x_inter, int(numpy.floor(z_num_steps / 2)))
            x_voltages = numpy.concatenate((x_voltages, x_voltages_1d))

        # [4, 5, 6] => [4, 4, 4, 5, 5, 5, 6, 6, 6]
        z_voltages = numpy.repeat(z_voltages_1d, x_num_steps)
        
        y_voltages = numpy.empty(len(z_voltages))
        y_voltages.fill(y_center)

        voltages = numpy.vstack((x_voltages,y_voltages, z_voltages))

        self.load_stream_writer_xyz(c, "GalvoAndObjectivePiezo-load_sweep_scan_xz", voltages, period)

        return x_voltages_1d, z_voltages_1d


__server__ = PiezoStageAndPKZ101()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
