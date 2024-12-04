# -*- coding: utf-8 -*-
"""
Input server for the amplified photodiode. Communicates via the DAQ.

Created on Thu Mar 20 08:52:34 2020

@author: mccambria

### BEGIN NODE INFO
[info]
name = photodiode
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
import nidaqmx
import socket
import logging


class photodiode(LabradServer):
    name = 'photodiode'
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
        p.cd(['Config', 'Wiring', 'Daq'])
        p.get('ai_photodiode')
        result = await p.send()
        return result['get']

    def on_get_config(self, wiring):
        self.daq_ai_pd = wiring

    def stopServer(self):
        for apd_index in self.tasks:
            self.close_task_internal(apd_index)

    @setting(0, returns='v[]')
    def read_optical_power(self, c):
        """Return the optical power from a pickoff beam in V"""
        
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(self.daq_ai_pd,
                                                 min_val=0.0, max_val=5.0)
            pd_voltage = task.read()
            
        
        return pd_voltage


__server__ = photodiode()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
