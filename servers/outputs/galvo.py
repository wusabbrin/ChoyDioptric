# -*- coding: utf-8 -*-
"""
Output server for the Thorlabs GVS212 galvanometer. Controlled by the DAQ.

Created on Mon Apr  8 19:50:12 2019

@author: mccambria

### BEGIN NODE INFO
[info]
name = galvo
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
import time


class Galvo(LabradServer):
    name = 'galvo'

    def initServer(self):
        self.task = None
        self.stream_writer = None
        self.stream_voltages = None
        self.stream_buffer_pos = None
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)

    async def get_config(self):
        p = self.client.registry.packet()
        p.cd(['Config', 'Wiring', 'Daq'])
        p.get('ao_galvo_x')
        p.get('ao_galvo_y')
        p.get('di_clock')
        result = await p.send()
        return result['get']

    def on_get_config(self, config):
        self.daq_ao_galvo_x = config[0]
        self.daq_ao_galvo_y = config[1]
        self.daq_di_clock = config[2]

    def stopServer(self):
        self.close_task_internal()

    def stopServer(self):
        self.close_task_internal()

    def load_stream_writer(self, c, task_name, voltages, period):

        # Close the existing task if there is one
        if self.task is not None:
            self.close_task_internal()

        # Write the initial voltages and stream the rest
        num_voltages = voltages.shape[1]
        self.write(c, voltages[0, 0], voltages[1, 0])
        stream_voltages = voltages[:, 1:num_voltages]
        stream_voltages = numpy.ascontiguousarray(stream_voltages)
        num_stream_voltages = num_voltages - 1

        # Create a new task
        task = nidaqmx.Task(task_name)
        self.task = task

        # Clear other existing stream state attributes
        self.stream_writer = None
        self.stream_voltages = None
        self.stream_buffer_pos = None

        # Set up the output channels
        task.ao_channels.add_ao_voltage_chan(self.daq_ao_galvo_x,
                                             min_val=-10.0, max_val=10.0)
        task.ao_channels.add_ao_voltage_chan(self.daq_ao_galvo_y,
                                             min_val=-10.0, max_val=10.0)

        # Set up the output stream
        output_stream = nidaqmx.task.OutStream(task)
        writer = stream_writers.AnalogMultiChannelWriter(output_stream)

        # Configure the sample to advance on the rising edge of the PFI input.
        # The frequency specified is just the max expected rate in this case.
        # We'll stop once we've run all the samples.
        freq = float(1/(period*(10**-9)))  # freq in seconds as a float
        task.timing.cfg_samp_clk_timing(freq, source=self.daq_di_clock,
                                        samps_per_chan=num_stream_voltages)

        # We'll write incrementally if there are more than 4000 samples
        # per channel since the DAQ buffer supports 8191 samples max
        if False: # num_stream_voltages > 4000:
            buffer_voltages = numpy.ascontiguousarray(stream_voltages[:,
                                                                      0:4000])
            # Set up the stream state attributes
            self.stream_writer = writer
            self.stream_voltages = stream_voltages
            self.stream_buffer_pos = 4000
            # Refill the buffer every 3000 samples
            writer.write_many_sample(buffer_voltages)
            task.register_every_n_samples_transferred_from_buffer_event(3000,
                                                            self.fill_buffer)
        else:
            # Just write all the samples
            writer.write_many_sample(stream_voltages)

        # Close the task once we've written all the samples
        task.register_done_event(self.close_task_internal)

        task.start()

    def fill_buffer(self, task_handle=None, every_n_samples_event_type=None,
                    number_of_samples=None, callback_data=None):
        # Check if there are more than 3000 samples left to write
        voltages = self.stream_voltages
        buffer_pos = self.stream_buffer_pos
        num_left_to_write = voltages.shape[1] - buffer_pos
        if num_left_to_write > 3000:
            next_buffer_pos = buffer_pos + 3000
            buffer_voltages = voltages[:, buffer_pos:next_buffer_pos]
            self.stream_buffer_pos = next_buffer_pos
        else:
            buffer_voltages = voltages[:, buffer_pos:]
        cont_buffer_voltages = numpy.ascontiguousarray(buffer_voltages)
        self.stream_writer.write_many_sample(cont_buffer_voltages)

    def close_task_internal(self, task_handle=None, status=None,
                            callback_data=None):
        task = self.task
        if task is not None:
            task.close()
            self.task = None
            self.stream_writer = None
            self.stream_voltages = None
            self.stream_buffer_pos = None
        return 0

    @setting(0, xVoltage='v[]', yVoltage='v[]')
    def write(self, c, xVoltage, yVoltage):

        # Close the stream task if it exists
        # This can happen if we quit out early
        if self.task is not None:
            self.close_task_internal()

        with nidaqmx.Task() as task:
            # Set up the output channels
            task.ao_channels.add_ao_voltage_chan(self.daq_ao_galvo_x,
                                                 min_val=-10.0, max_val=10.0)
            task.ao_channels.add_ao_voltage_chan(self.daq_ao_galvo_y,
                                                 min_val=-10.0, max_val=10.0)
            task.write([xVoltage, yVoltage])

    @setting(1, returns='*v[]')
    def read(self, c):
        with nidaqmx.Task() as task:
            # Set up the internal channels - to do: actual parsing...
            if self.daq_ao_galvo_x == 'dev1/AO0':
                chan_name = 'dev1/_ao0_vs_aognd'
            task.ai_channels.add_ai_voltage_chan(chan_name,
                                                 min_val=-10.0, max_val=10.0)
            if self.daq_ao_galvo_y == 'dev1/AO1':
                chan_name = 'dev1/_ao1_vs_aognd'
            task.ai_channels.add_ai_voltage_chan(chan_name,
                                                 min_val=-10.0, max_val=10.0)
            voltages = task.read()

        return voltages[0], voltages[1]

    @setting(2, x_center='v[]', y_center='v[]',
             x_range='v[]', y_range='v[]', num_steps='i', period='i',
             returns='*v[]*v[]')
    def load_sweep_scan(self, c, x_center, y_center,
                        x_range, y_range, num_steps, period):

        ######### Assumes x_range == y_range #########

        if x_range != y_range:
            raise ValueError('x_range must equal y_range for now')

        x_num_steps = num_steps
        y_num_steps = num_steps

        # Force the scan to have square pixels by only applying num_steps
        # to the shorter axis
        half_x_range = x_range / 2
        half_y_range = y_range / 2

        x_low = x_center - half_x_range
        x_high = x_center + half_x_range
        y_low = y_center - half_y_range
        y_high = y_center + half_y_range

        # Apply scale and offset to get the voltages we'll apply to the galvo
        # Note that the polar/azimuthal angles, not the actual x/y positions
        # are linear in these voltages. For a small range, however, we don't
        # really care.
        x_voltages_1d = numpy.linspace(x_low, x_high, num_steps)
        y_voltages_1d = numpy.linspace(y_low, y_high, num_steps)

        ######### Works for any x_range, y_range #########

        # Winding cartesian product
        # The x values are repeated and the y values are mirrored and tiled
        # The comments below shows what happens for [1, 2, 3], [4, 5, 6]

        # [1, 2, 3] => [1, 2, 3, 3, 2, 1]
        x_inter = numpy.concatenate((x_voltages_1d,
                                     numpy.flipud(x_voltages_1d)))
        # [1, 2, 3, 3, 2, 1] => [1, 2, 3, 3, 2, 1, 1, 2, 3]
        if y_num_steps % 2 == 0:  # Even x size
            x_voltages = numpy.tile(x_inter, int(y_num_steps/2))
        else:  # Odd x size
            x_voltages = numpy.tile(x_inter, int(numpy.floor(y_num_steps/2)))
            x_voltages = numpy.concatenate((x_voltages, x_voltages_1d))

        # [4, 5, 6] => [4, 4, 4, 5, 5, 5, 6, 6, 6]
        y_voltages = numpy.repeat(y_voltages_1d, x_num_steps)

        voltages = numpy.vstack((x_voltages, y_voltages))

        self.load_stream_writer(c, 'Galvo-load_sweep_scan', voltages, period)

        return x_voltages_1d, y_voltages_1d

    @setting(3, x_center='v[]', y_center='v[]', xy_range='v[]',
             num_steps='i', period='i', returns='*v[]*v[]')
    def load_cross_scan(self, c, x_center, y_center,
                        xy_range, num_steps, period):

        half_xy_range = xy_range / 2

        x_low = x_center - half_xy_range
        x_high = x_center + half_xy_range
        y_low = y_center - half_xy_range
        y_high = y_center + half_xy_range

        x_voltages_1d = numpy.linspace(x_low, x_high, num_steps)
        y_voltages_1d = numpy.linspace(y_low, y_high, num_steps)

        x_voltages = numpy.concatenate([x_voltages_1d,
                                        numpy.full(num_steps, x_center)])
        y_voltages = numpy.concatenate([numpy.full(num_steps, y_center),
                                        y_voltages_1d])

        voltages = numpy.vstack((x_voltages, y_voltages))

        self.load_stream_writer(c, 'Galvo-load_cross_scan', voltages, period)

        return x_voltages_1d, y_voltages_1d

    @setting(4, x_center='v[]', y_center='v[]', scan_range='v[]',
             num_steps='i', period='i', returns='*v[]')
    def load_x_scan(self, c, x_center, y_center,
                    scan_range, num_steps, period):

        half_scan_range = scan_range / 2

        x_low = x_center - half_scan_range
        x_high = x_center + half_scan_range

        x_voltages = numpy.linspace(x_low, x_high, num_steps)
        y_voltages = numpy.full(num_steps, y_center)

        voltages = numpy.vstack((x_voltages, y_voltages))

        self.load_stream_writer(c, 'Galvo-load_x_scan', voltages, period)

        return x_voltages

    @setting(5, x_center='v[]', y_center='v[]', scan_range='v[]',
             num_steps='i', period='i', returns='*v[]')
    def load_y_scan(self, c, x_center, y_center,
                    scan_range, num_steps, period):

        half_scan_range = scan_range / 2

        y_low = y_center - half_scan_range
        y_high = y_center + half_scan_range

        x_voltages = numpy.full(num_steps, x_center)
        y_voltages = numpy.linspace(y_low, y_high, num_steps)

        voltages = numpy.vstack((x_voltages, y_voltages))

        self.load_stream_writer(c, 'Galvo-load_y_scan', voltages, period)

        return y_voltages


__server__ = Galvo()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
