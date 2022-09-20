#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Sep  3 11:16:25 2022

@author: carterfox

simple readout sequence for the opx in qua

"""


import numpy
import utils.tool_belt as tool_belt
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *
from qm import SimulationConfig
from configuration import *

def qua_program(args, num_reps, x_voltage_list=[], y_voltage_list=[], z_voltage_list=[]):
    
    delay, readout_time, apd_index, laser_name, laser_power = args

    delay = numpy.int64(delay)
    delay_cc = delay // 4
    readout_time = numpy.int64(readout_time)

    period = numpy.int64(delay + readout_time + 300)
    period_cc = period // 4 
    
    num_gates = 1
    num_apds = len(apd_indices)
    timetag_list_size = int(15900 / num_gates / num_apds)
    
    with program() as seq:
        
        # I make two of each because we can have up to two APDs (two analog inputs), It will save all the streams that are actually used
        
        counts_gate1_apd_0 = declare(int)  # variable for number of counts
        counts_gate1_apd_1 = declare(int)
        counts_st = declare_stream()  # stream for counts
        
        times_gate1_apd_0 = declare(int, size=timetag_list_size)  # why input a size??
        times_gate1_apd_1 = declare(int, size=timetag_list_size)
        times_st = declare_stream()
                
        n = declare(int)
        i = declare(int)
        
        with for_(n, 0, n < num_reps, n + 1):
            
            align()  
            
            ###green laser
            play(laser_ON,laser_name,duration=int(period_cc))  
            
            ###apds
            if 0 in apd_indices:
                wait(delay_cc, "APD_0") # wait for the delay before starting apds
                measure("readout", "APD_0", None, time_tagging.analog(times_gate1_apd_0, readout_time, counts_gate1_apd_0))
                
            if 1 in apd_indices:
                wait(delay_cc, "APD_1") # wait for the delay before starting apds
                measure("readout", "APD_1", None, time_tagging.analog(times_gate1_apd_1, readout_time, counts_gate1_apd_1))
        
            
            # save the sample to the count stream. sample is a list of gates, which is a list of counts from each apd
            # if there is only one gate, it will be in the same structure as read_counter_simple wants so we are good
           
            ###trigger piezos
            if (len(x_voltage_list) > 0):
                wait((period - 200) // 4, "x_channel")
                play("ON", "x_channel", duration=100)  
            if (len(y_voltage_list) > 0):
                wait((period - 200) // 4, "y_channel")
                play("ON", "y_channel", duration=100)  
            if (len(z_voltage_list) > 0):
                wait((period - 200) // 4, "z_channel")
                play("ON", "z_channel", duration=100)  
                
            
            ###saving
            if 0 in apd_indices:
                save(counts_gate1_apd_0, counts_st)
                with for_(i, 0, i < counts_gate1_apd_0, i + 1):
                    save(times_gate1_apd_0[i], times_st)
                        
            if 1 in apd_indices:
                save(counts_gate1_apd_1, counts_st)
                with for_(i, 0, i < counts_gate1_apd_1, i + 1):
                    save(times_gate1_apd_1[i], times_st)
            
        with stream_processing():
            counts_st.buffer(num_gates).buffer(num_apds).buffer(num_reps).save_all("counts")
            times_st.save_all("times")
        
    return seq


def get_seq(config, args): #so this will give just the sequence, no repeats
    
    seq = qua_program(args, num_reps=1)
    
    return seq, final, [period]

def get_full_seq(config, args, num_repeat, x_voltage_list,y_voltage_list,z_voltage_list): #so this will give the full desired sequence, with however many repeats are intended repeats

    seq = qua_program(args, num_reps, x_voltage_list,y_voltage_list,z_voltage_list)

    return seq, final, [period]
    

if __name__ == '__main__':
    
    print('hi')