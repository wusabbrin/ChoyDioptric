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
    init_pulse_time, readout_time, init_laser_key, readout_laser_key,\
      init_laser_power, read_laser_power, apd_index  = args

    # Get what we need out of the wiring dictionary
    pulser_wiring = config['Wiring']['PulseStreamer']
    pulser_do_daq_clock = pulser_wiring['do_sample_clock']
    pulser_do_daq_gate = pulser_wiring['do_apd_{}_gate'.format(apd_index)]
    
    galvo_move_time = config['Positioning']['xy_small_response_delay']
    init_pulse_aom_delay_time = config['Optics'][init_laser_key]['delay']
    read_pulse_aom_delay_time = config['Optics'][readout_laser_key]['delay']
    
    # Convert the 32 bit ints into 64 bit ints
    init_pulse_time = numpy.int64(init_pulse_time)
    readout_time = numpy.int64(readout_time)
    
    intra_pulse_delay = config['CommonDurations']['cw_meas_buffer']
    
    if init_laser_key == readout_laser_key:
        total_delay = init_pulse_aom_delay_time
    else:
        total_delay = init_pulse_aom_delay_time + read_pulse_aom_delay_time
    
    period = galvo_move_time + total_delay + init_pulse_time + readout_time +\
                                        intra_pulse_delay + 300
        
    #%% Define the sequence
    seq = Sequence()

    # Clock
    train = [(galvo_move_time + total_delay + init_pulse_time + intra_pulse_delay + readout_time + 100, LOW), (100, HIGH), (100, LOW)]
    seq.setDigital(pulser_do_daq_clock, train)

    # APD gate
    train = [(galvo_move_time + total_delay + init_pulse_time + intra_pulse_delay, LOW), (readout_time, HIGH), (300, LOW)]
    seq.setDigital(pulser_do_daq_gate, train)
    
    if init_laser_key == readout_laser_key:
        laser_key = readout_laser_key
        laser_power = read_laser_power
        
        train = [(galvo_move_time, LOW), (init_pulse_time, HIGH), 
                 (intra_pulse_delay, LOW), 
                 (readout_time, HIGH), (100 ,LOW )]
        tool_belt.process_laser_seq(pulse_streamer, seq, config,
                                laser_key, laser_power, train)
    
    else:
        train_init_laser = [(galvo_move_time + read_pulse_aom_delay_time, LOW), 
                            (init_pulse_time, HIGH), 
                            (100  + intra_pulse_delay + readout_time,LOW )]
        tool_belt.process_laser_seq(pulse_streamer, seq, config,
                                init_laser_key, init_laser_power, train_init_laser)
        
        
        train_read_laser = [(galvo_move_time + init_pulse_aom_delay_time + init_pulse_time + intra_pulse_delay, LOW), 
                 (readout_time, HIGH), (100 ,LOW )]
        tool_belt.process_laser_seq(pulse_streamer, seq, config,
                                readout_laser_key, read_laser_power, train_read_laser)
        
    final_digital = []
    final = OutputState(final_digital, 0.0, 0.0)

    return seq, final, [period]


if __name__ == '__main__':
    config = tool_belt.get_config_dict()
    # args = [10000, 10000, 'cobolt_638', 'laserglow_589', None, 0.8, 0]
    args = [1000.0, 100000000, 'laserglow_532', 'laserglow_589', None, 0.15, 0]
    seq = get_seq(None, config, args)[0]
    seq.plot()