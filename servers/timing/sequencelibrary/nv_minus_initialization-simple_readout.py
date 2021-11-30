# -*- coding: utf-8 -*-
"""
Created on Tue Apr  9 21:24:36 2019

@author: mccambria
"""

from pulsestreamer import Sequence
from pulsestreamer import OutputState
import utils.tool_belt as tool_belt
import numpy

LOW = 0
HIGH = 1


def get_seq(pulse_streamer, config, args):

    # Unpack the args
    init_time, readout_time, apd_index, init_laser_name, init_laser_power, readout_laser_name, readout_laser_power = args

    # Get what we need out of the wiring dictionary
    pulser_wiring = config['Wiring']['PulseStreamer']
    pulser_do_daq_clock = pulser_wiring['do_sample_clock']
    pulser_do_daq_gate = pulser_wiring['do_apd_{}_gate'.format(apd_index)]
    
    # And the config dictionary
    init_delay = config["Optics"][init_laser_name]["delay"]
    readout_delay = config["Optics"][readout_laser_name]["delay"]

    # Convert the 32 bit ints into 64 bit ints
    readout_delay = numpy.int64(readout_delay)
    readout_time = numpy.int64(readout_time)
    init_delay = numpy.int64(init_delay)
    init_time = numpy.int64(init_time)

    period = numpy.int64(init_delay + init_time + readout_time + 300)

#    tool_belt.check_laser_power(laser_name, laser_power)

    # Define the sequence
    seq = Sequence()

    # The clock signal will be high for 100 ns with buffers of 100 ns on
    # either side. During the buffers, everything should be low. The buffers
    # account for any timing jitters/delays and ensure that everything we
    # expect to be on one side of the clock signal is indeed on that side.
    train = [(period-200, LOW), (100, HIGH), (100, LOW)]
    seq.setDigital(pulser_do_daq_clock, train)

    train = [(init_delay + init_time, LOW), (readout_time, HIGH), (300, LOW)]
    seq.setDigital(pulser_do_daq_gate, train)

    train = [(init_time, HIGH), (readout_time + 300 + init_delay, LOW)]
    tool_belt.process_laser_seq(pulse_streamer, seq, config, 
                                init_laser_name, init_laser_power, train)

    train = [(init_delay + init_time - readout_delay, LOW), (readout_time, HIGH), (300 + readout_delay, LOW)]
    tool_belt.process_laser_seq(pulse_streamer, seq, config, 
                                readout_laser_name, readout_laser_power, train)

    final_digital = []
    final = OutputState(final_digital, 0.0, 0.0)

    return seq, final, [period]


if __name__ == '__main__':
    config = tool_belt.get_config_dict()
    args = [2000.0, 100000.0, 1, 'laserglow_532', None, 'laserglow_589', 1.0]
#    seq_args_string = tool_belt.encode_seq_args(args)
    seq, ret_vals, period = get_seq(None, config, args)
    seq.plot()