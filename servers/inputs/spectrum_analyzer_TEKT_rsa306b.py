# -*- coding: utf-8 -*-
"""
Spectrum analyzer - Tektronix RSA306B

Created on Wed May  1 18:32:59 2019

@author: mccambria

### BEGIN NODE INFO
[info]
name = spectrum_analyzer_TEKT_rsa306b
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
import numpy
import rsa_api
import socket
import logging


class SpectrumAnalyzerTektRsa306b(LabradServer):
    name = "spectrum_analyzer_TEKT_rsa306b"
    pc_name = socket.gethostname()
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%y-%m-%d_%H-%M-%S",
        filename=(
            "E:/Shared drives/Kolkowitz Lab"
            " Group/nvdata/pc_{}/labrad_logging/{}.log".format(pc_name, name)
        ),
    )

    def initServer(self):
        # Connect to the device - assume there is only one
        self.search_connect()

    ############ The code below is pulled from Tektronix sample code:
    # https://github.com/tektronix/RSA_API/blob/master/Python/Cython%20Version/cython_example.py

    def search_connect(self):
        ret_vals = rsa_api.DEVICE_Search_py()
        numDevicesFound, deviceIDs, deviceSerial, deviceType = ret_vals
        # Connect to the device - assume there is only one
        if numDevicesFound > 0:
            rsa_api.DEVICE_Connect_py(deviceIDs[0])
        rsa_api.CONFIG_Preset_py()

    def config_spectrum(self, cf=2.87e9, refLevel=0, span=30e6, rbw=300e3):
        rsa_api.SPECTRUM_SetEnable_py(True)
        rsa_api.CONFIG_SetCenterFreq_py(cf)
        rsa_api.CONFIG_SetReferenceLevel_py(refLevel)

        rsa_api.SPECTRUM_SetDefault_py()
        rsa_api.SPECTRUM_SetSettings_py(span=span, rbw=rbw, traceLength=801)
        specSet = rsa_api.SPECTRUM_GetSettings_py()
        return specSet

    def create_frequency_array(self, specSet):
        # Create array of frequency data for plotting the spectrum.
        start = specSet["actualStartFreq"]
        stop = (
            specSet["actualStartFreq"]
            + specSet["actualFreqStepSize"] * specSet["traceLength"]
        )
        step = specSet["actualFreqStepSize"]
        freq = numpy.arange(start, stop, step)
        return freq

    ############

    def acquire_spectrum_internal(self, freq_center=2.87, freq_range=0.5):
        freq_center_hz = freq_center * 10**9
        freq_range_hz = freq_range * 10**9
        ref_level = 0
        resolution_bandwidth = 300e3  # I don't know what this means
        specSet = self.config_spectrum(
            freq_center_hz, ref_level, freq_range_hz, resolution_bandwidth
        )
        spec_trace_1 = rsa_api.SpectrumTraces.SpectrumTrace1
        freqs = self.create_frequency_array(specSet)
        powers = rsa_api.SPECTRUM_Acquire_py(
            spec_trace_1, specSet["traceLength"], 100
        )
        return freqs, powers

    @setting(0, freq_center="v[]", freq_range="v[]", returns="*v[]*v[]")
    def acquire_spectrum(self, c, freq_center=2.87, freq_range=0.5):
        return self.acquire_spectrum_internal(freq_center, freq_range)

    @setting(1, freq_center="v[]", freq_range="v[]", returns="v[]v[]")
    def measure_peak(self, c, freq_center=2.87, freq_range=0.5):
        freqs, powers = self.acquire_spectrum_internal(freq_center, freq_range)
        peakPower = numpy.amax(powers)
        peakFreq = freqs[numpy.argmax(powers)]
        return float(peakFreq / 10**9), float(peakPower)


__server__ = SpectrumAnalyzerTektRsa306b()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
