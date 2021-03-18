# -*- coding: utf-8 -*-
"""
Output server for the arbitrary waveform generator.

Created on Wed Apr 10 12:53:38 2019

@author: mccambria

### BEGIN NODE INFO
[info]
name = arbitrary_waveform_generator
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
import visa  # Docs here: https://pyvisa.readthedocs.io/en/master/
import socket
import logging


class ArbitraryWaveformGenerator(LabradServer):
    name = 'arbitrary_waveform_generator'
    pc_name = socket.gethostname()
    logging.basicConfig(level=logging.DEBUG, 
                format='%(asctime)s %(levelname)-8s %(message)s',
                datefmt='%y-%m-%d_%H-%M-%S',
                filename='E:/Shared drives/Kolkowitz Lab Group/nvdata/pc_{}/labrad_logging/{}.log'.format(pc_name, name))

    def initServer(self):
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)

    async def get_config(self):
        p = self.client.registry.packet()
        p.cd('Config')
        p.get('arb_wave_gen_visa_address')
        result = await p.send()
        return result['get']

    def on_get_config(self, config):
        resource_manager = visa.ResourceManager()
        self.wave_gen = resource_manager.open_resource(config)
        self.reset(None)
        
    @setting(3)
    def iq_switch(self, c):
        """
        On trigger from Pulse Streamer, switch between (0.5, 0) and (0.5, 0)
        for IQ modulation
        """
        
        for chan in [1, 2]:
            source_name = 'SOUR{}:'.format(chan)
            self.wave_gen.write('{}FUNC:ARB:FILT OFF'.format(source_name))
            self.wave_gen.write('{}FUNC:ARB:ADV TRIG'.format(source_name))
            self.wave_gen.write('{}FUNC:ARB:PTP 2'.format(source_name))
        
        # It would be nice if we could just write '0.5, 0.0', but there's a
        # minimum number of points
        seq = '0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0'
        self.wave_gen.write('SOUR1:DATA:ARB iqSwitch1, {}'.format(seq))
        seq = '0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5'
        self.wave_gen.write('SOUR2:DATA:ARB iqSwitch2, {}'.format(seq))
        
        for chan in [1, 2]:
            source_name = 'SOUR{}:'.format(chan)
            self.wave_gen.write('{}FUNC:ARB iqSwitch{}'.format(source_name, chan))
            self.wave_gen.write('{}FUNC ARB'.format(source_name))
            
        self.wave_gen.write('TRIG1:SOUR EXT')
        self.wave_gen.write('TRIG2:SOUR EXT')
        self.wave_gen.write('TRIG1:SLOP POS')
        self.wave_gen.write('TRIG2:SLOP POS')
        
        self.wave_gen.write('OUTP1 ON')
        self.wave_gen.write('OUTP2 ON')
        
        
    @setting(4)
    def test_sin(self, c):
        for chan in [1, 2]:
            source_name = 'SOUR{}:'.format(chan)
            self.wave_gen.write('{}FUNC SIN'.format(source_name))
            self.wave_gen.write('{}FREQ 10000'.format(source_name))
            self.wave_gen.write('{}VOLT:HIGH +0.5'.format(source_name))
            self.wave_gen.write('{}VOLT:LOW -0.5'.format(source_name))
        self.wave_gen.write('OUTP1 ON')
        self.wave_gen.write('SOUR2:PHAS 0')
        self.wave_gen.write('OUTP2 ON')
        
    @setting(5)
    def wave_off(self, c):
        self.wave_gen.write('OUTP1 OFF')
        self.wave_gen.write('OUTP2 OFF')
        
    @setting(6)
    def reset(self, c):
        self.wave_off(c)
        self.wave_gen.write('SOUR1:DATA:VOL:CLE')
        self.wave_gen.write('SOUR2:DATA:VOL:CLE')
        self.wave_gen.write('OUTP1:LOAD 50')
        self.wave_gen.write('OUTP2:LOAD 50')


__server__ = ArbitraryWaveformGenerator()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
