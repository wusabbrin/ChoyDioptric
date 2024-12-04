# -*- coding: utf-8 -*-
"""
Base class for Cobolt/Hubner laser servers. These lasers require a higher
voltage TTL than the PulseStreamer outputs, so we'll feed the TTL from the
PulseStreamer through to the DAQ and get a full 5 V TTL from there.

Created on November 1st, 2021

@author: mccambria
"""

from labrad.server import LabradServer
from labrad.server import setting
from twisted.internet.defer import ensureDeferred
import nidaqmx
import nidaqmx.stream_writers as stream_writers
import numpy
import logging
import socket


class LaserCoboBase(LabradServer):
    pc_name = socket.gethostname()

    def initServer(self):
        filename = 'E:/Shared drives/Kolkowitz Lab Group/nvdata/pc_{}/labrad_logging/{}.log'
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%y-%m-%d_%H-%M-%S', filename=filename)
        self.task = None
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)

    async def get_config(self):
        p = self.client.registry.packet()
        p.cd(['', 'Config', 'Wiring', 'Daq'])
        p.get('do_{}_feedthrough'.format(self.name))
        p.get('di_{}_feedthrough'.format(self.name))
        result = await p.send()
        return result['get']

    def on_get_config(self, config):
        self.do_feedthrough = config[0]
        self.di_feedthrough = config[1]
        # Load the feedthrough and just leave it running
        try:
            self.load_feedthrough(None)
        except Exception as e:
            logging.debug(e)
        logging.debug('Init complete')

    def stopServer(self):
        self.close_task_internal()

    def load_stream_writer(self, c, task_name, stream_bools):

        # Close the existing task if there is one
        if self.task is not None:
            self.close_task_internal()

        # Create a new task
        task = nidaqmx.Task(task_name)
        self.task = task

        # Set up the output channel
        task.do_channels.add_do_chan(self.do_feedthrough)

        # Set up the output stream
#        output_stream = nidaqmx.task.OutStream(task)
#        writer = stream_writers.DigitalSingleChannelWriter(output_stream)

        # Configure the sample to advance on the rising edge of the PFI input.
        # The frequency specified is just the max expected rate in this case.
        freq = 10E6  # 10 MHz, every 100 ns. Thjs is the max freq for PCIE6738
        clock = self.di_feedthrough
        sample_mode = nidaqmx.constants.AcquisitionType.CONTINUOUS
        task.timing.cfg_samp_clk_timing(freq, source=clock,
                                        sample_mode=sample_mode)
        
        task.write(stream_bools)

        # Close the task once we've written all the samples
        task.register_done_event(self.close_task_internal)

        task.start()


    def close_task_internal(self, task_handle=None, status=None,
                            callback_data=None):
        task = self.task
        if task is not None:
            task.close()
            self.task = None
        return 0


    @setting(0)
    def load_feedthrough(self, c):
        # Just flip the TTL out on the rising edge of the TTL in
        stream_bools = numpy.array([True, False], dtype=bool)
        self.load_stream_writer(c, '{}-load_feedthrough'.format(self.name), 
                                stream_bools)
        
        
    @setting(1)
    def reset(self, c):
        # Make sure the laser is off
        self.laser_off(c)
        
        
    @setting(2)
    def laser_on(self, c):
        self.close_task_internal()
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self.do_feedthrough)
            task.write(True)
        
        
    @setting(3)
    def laser_off(self, c):
        self.close_task_internal()
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self.do_feedthrough)
            task.write(False)
