# -*- coding: utf-8 -*-
"""
Timing server for the Swabian Pulse Stream 8/2.

Created on Tue Apr  9 17:12:27 2019

@author: mccambria

### BEGIN NODE INFO
[info]
name = pulse_streamer
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
from pulsestreamer import PulseStreamer as Pulser
from pulsestreamer import TriggerStart
from pulsestreamer import OutputState
import importlib
import os
import sys


class PulseStreamer(LabradServer):
    name = 'pulse_streamer'

    def initServer(self):
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)
        self.seq = None
        self.loaded_seq_streamed = False

    async def get_config(self):
        p = self.client.registry.packet()
        p.cd('Config')
        p.get('pulse_streamer_ip')
        p.get('sequence_library_path')
        p.cd(['Wiring', 'Pulser'])
        p.dir()
        result = await p.send()
        return result

    def on_get_config(self, config):
        get_result = config['get']
        self.pulser = Pulser(get_result[0])
        sys.path.append(get_result[1])
        reg_keys = config['dir'][1]  # dir returns subdirs followed by keys
        wiring = ensureDeferred(self.get_wiring(reg_keys))
        wiring.addCallback(self.on_get_wiring, reg_keys)

    async def get_wiring(self, reg_keys):
        p = self.client.registry.packet()
        for reg_key in reg_keys:
            p.get(reg_key, key=reg_key)  # Return as a dictionary
        result = await p.send()
        return result

    def on_get_wiring(self, wiring, reg_keys):
        self.pulser_wiring = {}
        for reg_key in reg_keys:
            self.pulser_wiring[reg_key] = wiring[reg_key]
            
    def stopServer(self):
        self.constant()

    def get_seq(self, seq_file, args):
        seq = None
        file_name, file_ext = os.path.splitext(seq_file)
        if file_ext == '.py':  # py: import as a module
            seq_module = importlib.import_module(file_name)
            seq, ret_vals = seq_module.get_seq(self.pulser_wiring, args)
        return seq, ret_vals

    def set_output_state(self, output_state):
        if output_state == 0:  # Default, AOM on
            pulser_do_aom = self.pulser_wiring['do_aom']
            self.output_state = OutputState([pulser_do_aom], 0, 0)
        elif output_state == 1:  # DAQ clock on
            pulser_do_daq_clock = self.pulser_wiring['do_daq_clock']
            self.output_state = OutputState([pulser_do_daq_clock], 0, 0)
        elif output_state == 2:  # Uwave gate open
            pulser_do_daq_clock = self.pulser_wiring['do_uwave_gate']
            self.output_state = OutputState([pulser_do_daq_clock], 0, 0)

    @setting(0, seq_file='s', num_repeat='i',
             args='*?', output_state='i', returns='*?')
    def stream_immediate(self, c, seq_file, num_repeat=1,
                         args=None, output_state=0):
        ret_vals = self.stream_load(c, seq_file, args, output_state)
        self.stream_start(c, num_repeat)
        return ret_vals

    @setting(1, seq_file='s', args='*?', output_state='i', returns='*?')
    def stream_load(self, c, seq_file, args=None, output_state=0):
        self.pulser.setTrigger(start=TriggerStart.SOFTWARE)
        self.set_output_state(output_state)
        seq, ret_vals = self.get_seq(seq_file, args)
        if seq is not None:
            self.seq = seq
            self.loaded_seq_streamed = False
        return ret_vals

    @setting(2, num_repeat='i')
    def stream_start(self, c, num_repeat=1):
        if self.seq == None:
            raise RuntimeError('Stream started with no sequence.')
        if not self.loaded_seq_streamed:
            self.pulser.stream(self.seq, num_repeat, self.output_state)
            self.loaded_seq_streamed = True
        self.pulser.startNow()

    @setting(3, output_state='i')
    def constant(self, c, output_state=0):
        self.set_output_state(output_state)
        self.pulser.constant(self.output_state)


__server__ = PulseStreamer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
