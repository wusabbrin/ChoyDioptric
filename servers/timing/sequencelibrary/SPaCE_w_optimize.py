# -*- coding: utf-8 -*-
"""
Created on Sat Mar  24 08:34:08 2020

Thsi file is for use with the isolate_nv_charge_dynamics_moving_target' routine.

This sequence has three pulses, seperated by wait times that allow time for
the galvo to move. We also have two clock pulses instructing the galvo to move, 
followed by a clock pulse at the end of the sequence to signifiy the counts to read.

@author: Aedan
"""

from pulsestreamer import Sequence
from pulsestreamer import OutputState
import utils.tool_belt as tool_belt
import numpy

LOW = 0
HIGH = 1

def get_seq(pulse_streamer, config, args):

    # %% Parse wiring and args

    # The first 2 args are ns durations and we need them as int64s
    durations = []
    for ind in range(7):
        durations.append(numpy.int64(args[ind]))

    # Unpack the durations
    initialization_time, pulse_time, charge_readout_time, imaging_readout_dur, \
        x_move_delay, y_move_delay, z_move_delay = durations
                
    aom_ao_589_pwr = args[7]
    num_opti_steps = args[8]

    # Get the APD index
    apd_index = args[9]

    init_color = args[10]
    pulse_color = args[11]
    read_color = args[12]
    
    galvo_move_time = config['Positioning']['xy_large_response_delay']
    
    # Get what we need out of the wiring dictionary
    pulser_wiring = config['Wiring']['PulseStreamer']
    
    pulser_do_apd_gate = pulser_wiring['do_apd_{}_gate'.format(apd_index)]
    pulser_do_clock = pulser_wiring['do_sample_clock']
    pulser_do_532_aom = pulser_wiring['do_laserglow_532_dm']
    pulser_ao_589_aom = pulser_wiring['ao_laserglow_589_am']
    pulser_do_638_aom = pulser_wiring['do_cobolt_638_dm']
    
    green_laser_delay =  config['Optics']['laserglow_532']['delay']
    yellow_laser_delay = config['Optics']['laserglow_589']['delay']
    red_laser_delay = config['Optics']['cobolt_638']['delay']
    
    
    total_laser_delay = green_laser_delay + yellow_laser_delay + red_laser_delay

    # %% Calclate total period.
    
#    We're going to readout the entire sequence, including the clock pulse
    measurement_period = initialization_time + pulse_time + charge_readout_time \
        + 2 * galvo_move_time + 3* 100
    optimize_x_time = (x_move_delay + imaging_readout_dur + 300) * num_opti_steps
    optimize_y_time = (y_move_delay + imaging_readout_dur + 300) * num_opti_steps
    optimize_z_time = (z_move_delay + imaging_readout_dur + 300) * num_opti_steps
    total_optimize_time = optimize_x_time + optimize_y_time + optimize_z_time
    period = total_laser_delay + measurement_period + total_optimize_time
    
    # %% Define the sequence

    seq = Sequence()
    
    #################### APD ####################
    # Sequence for the measurement
    train = [(total_laser_delay, LOW), (initialization_time, HIGH),
             (100 + galvo_move_time, LOW), (pulse_time, HIGH),
             (100 + galvo_move_time, LOW), (charge_readout_time, HIGH),
             (100, LOW)]
    # Sequence for optimizing in x
    x_opti_train = [(x_move_delay, LOW), (imaging_readout_dur, HIGH), (300, LOW)]
    for i in range(num_opti_steps):
        train.extend(x_opti_train)
    # Sequence for optimizing in y
    y_opti_train = [(y_move_delay, LOW), (imaging_readout_dur, HIGH), (300, LOW)]
    for i in range(num_opti_steps):
        train.extend(y_opti_train)
    # Sequence for optimizing in z
    z_opti_train = [(z_move_delay, LOW), (imaging_readout_dur, HIGH), (300, LOW)]
    for i in range(num_opti_steps):
        train.extend(z_opti_train)
    seq.setDigital(pulser_do_apd_gate, train)
    
    #################### clock #################### 
    # Sequence for the measurement
    # I needed to add 100 ns between the redout and the clock pulse, otherwise 
    # the tagger misses some of the gate open/close clicks
    train = [(total_laser_delay + initialization_time+ 100, LOW),(100, HIGH),
             (galvo_move_time + pulse_time, LOW), (100, HIGH), 
             (galvo_move_time + charge_readout_time, LOW), (100, HIGH),
             (100, LOW)] 
    # Sequence for optimizing in x
    x_opti_train = [(x_move_delay + imaging_readout_dur + 100, LOW), 
                    (100, HIGH), (100, LOW)]
    for i in range(num_opti_steps):
        train.extend(x_opti_train)
    # Sequence for optimizing in y
    y_opti_train = [(y_move_delay + imaging_readout_dur + 100, LOW), 
                    (100, HIGH), (100, LOW)]
    for i in range(num_opti_steps):
        train.extend(y_opti_train)
    # Sequence for optimizing in z
    z_opti_train = [(y_move_delay + imaging_readout_dur + 100, LOW), 
                    (100, HIGH), (100, LOW)]
    for i in range(num_opti_steps):
        train.extend(z_opti_train)
    seq.setDigital(pulser_do_clock, train)
    
    #################### lasers #################### 
    # start each laser sequence
    train_532 = [(total_laser_delay - green_laser_delay , LOW)]
    train_589 = [(total_laser_delay - yellow_laser_delay, LOW)]
    train_638 = [(total_laser_delay - red_laser_delay, LOW)]
   
    galvo_delay_train = [(100 + galvo_move_time, LOW)]
    
    # add the initialization pulse segment
    init_train_on = [(initialization_time, HIGH)]
    init_train_off = [(initialization_time, LOW)]
    if init_color == 532:
        train_532.extend(init_train_on)
        train_589.extend(init_train_off)
        train_638.extend(init_train_off)
    if init_color == 589:
        init_train_on = [(initialization_time, aom_ao_589_pwr)]
        train_532.extend(init_train_off)
        train_589.extend(init_train_on)
        train_638.extend(init_train_off)
    if init_color == 638:
        train_532.extend(init_train_off)
        train_589.extend(init_train_off)
        train_638.extend(init_train_on)
        
    train_532.extend(galvo_delay_train)
    train_589.extend(galvo_delay_train)
    train_638.extend(galvo_delay_train)
    
    # add the pulse pulse segment
    pulse_train_on = [(pulse_time, HIGH)]
    pulse_train_off = [(pulse_time, LOW)]
    if pulse_color == 532:
        train_532.extend(pulse_train_on)
        train_589.extend(pulse_train_off)
        train_638.extend(pulse_train_off)
    if pulse_color == 589:
        pulse_train_on = [(pulse_time, aom_ao_589_pwr)]
        train_532.extend(pulse_train_off)
        train_589.extend(pulse_train_on)
        train_638.extend(pulse_train_off)
    if pulse_color == 638:
        train_532.extend(pulse_train_off)
        train_589.extend(pulse_train_off)
        train_638.extend(pulse_train_on)
        
    train_532.extend(galvo_delay_train)
    train_589.extend(galvo_delay_train)
    train_638.extend(galvo_delay_train)
    
    # add the readout pulse segment
    read_train_on = [(charge_readout_time, HIGH)]
    read_train_off = [(charge_readout_time, LOW)]
    if read_color == 532:
        train_532.extend(read_train_on)
        train_589.extend(read_train_off)
        train_638.extend(read_train_off)
    if read_color == 589:
        read_train_on = [(charge_readout_time, aom_ao_589_pwr)]
        train_532.extend(read_train_off)
        train_589.extend(read_train_on)
        train_638.extend(read_train_off)
    if read_color == 638:
        train_532.extend(pulse_train_off)
        train_589.extend(pulse_train_off)
        train_638.extend(read_train_on)
        
    train_532.extend([(100, LOW)])
    train_589.extend([(100, LOW)])
    train_638.extend([(100, LOW)])
        
    
    train_532.extend([(x_move_delay, LOW),
      (total_optimize_time - x_move_delay, HIGH)])
        

    seq.setDigital(pulser_do_532_aom, train_532)
    seq.setAnalog(pulser_ao_589_aom, train_589)
    seq.setDigital(pulser_do_638_aom, train_638)    
        
    final_digital = []
    final = OutputState(final_digital, 0.0, 0.0)
    return seq, final, [period]

if __name__ == '__main__':
    config = tool_belt.get_config_dict()

    seq_args = [100000.0, 100000.0, 500000, 200000, 100000,100000,100000, 0.9, 2, 0, 532, 638, 589]
    seq = get_seq(None, config, seq_args)[0]
    seq.plot()
