"""
Interface server for Laserglow 532 to control analog voltage from DAQ and gated
by Pulse Streamer

Created on September, 2024

@author: 

### BEGIN NODE INFO
[info]
name = laser_LGLO_532
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
import numpy
import logging
import socket

class LaserLglo532(LabradServer):
    pc_name = socket.gethostname()
    wavelength = 532
    name = f"laser_LGLO_{wavelength}"

    def initServer(self):
        filename = (
            "D:/Choy_Lab/"
            "sivdata/labrad_logging/{}.log"        
        )
        filename = filename.format(self.name)
        logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%y-%m-%d_%H-%M-%S', filename=filename)
        self.task = None
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)

    async def get_config(self):
        p = self.client.registry.packet()
        p.cd(['', 'Config', 'Wiring', 'PulseGen'])
        p.get('do_{}_feedthrough'.format(self.name))
        p.get('di_{}_feedthrough'.format(self.name))
        # p.cd(['', 'Config', 'Optics', '{}'.format(self.name)])
        # p.get('true_zero_voltage_daq') 
        result = await p.send()
        return result['get']

    def on_get_config(self, config):
        self.do_feedthrough = config[0]
        self.di_feedthrough = config[1]
        # self.true_zero_value = config[2]
        # Load the feedthrough and just leave it running
        logging.debug('Init complete')

    @setting(0)
    def laser_on(self, c):

        pass
        
        
    @setting(1)
    def laser_off(self, c):
        
        pass

__server__ = LaserLglo532()     

if __name__ == '__main__':
    from labrad import util
    
    util.runServer(__server__)