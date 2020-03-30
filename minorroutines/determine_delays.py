# -*- coding: utf-8 -*-
"""
Plot the counts obtained by moving the AOM on time so that we can
determine the delay of the AOM relative to the APD gating.

For laser delays, the tail of the pulse shoudl be at 500 ns. If it occurs
later thatn 500 ns, the difference is the delay added at the beginning of 
all other sequence trains.

Created on Fri Jul 12 13:53:45 2019

@author: mccambria
"""


# %% Imports


import labrad
import utils.tool_belt as tool_belt
import majorroutines.optimize as optimize
from random import shuffle
import numpy
import matplotlib.pyplot as plt
from utils.tool_belt import States


# %% Functions


def measure_delay(cxn, nv_sig, readout, apd_indices,
              delay_range, num_steps, num_reps, seq_file, color_ind,
              state=States.LOW, aom_delay=None):
    
    taus = numpy.linspace(delay_range[0], delay_range[1],
                          num_steps, dtype=numpy.int32)
    max_tau = delay_range[1]
    tau_ind_list = list(range(num_steps))
    shuffle(tau_ind_list)
    
    sig_counts = numpy.empty(num_steps, dtype=numpy.uint32)
    sig_counts[:] = numpy.nan
    ref_counts = numpy.copy(sig_counts)
    
    # Input a set delay to check that measured delay is correct
    shared_params = tool_belt.get_shared_parameters_dict(cxn)
    
    #delay of aoms and laser
#    if not aom_delay:
    laser_delay = 0
#    else:
    if color_ind == 532:
        laser_delay = shared_params['515_laser_delay']
    if color_ind == 589:
        laser_delay = shared_params['589_aom_delay']
    if color_ind == 638:
        laser_delay = 0
#        
        

#    optimize.main_with_cxn(cxn, nv_sig, apd_indices)
    
    tool_belt.reset_cfm(cxn)
    
    # Turn on the microwaves for determining microwave delay
    sig_gen = None
    if seq_file == 'uwave_delay.py':
        sig_gen = tool_belt.get_signal_generator_name(state)
        sig_gen_cxn = tool_belt.get_signal_generator_cxn(cxn, state)
        sig_gen_cxn.set_freq(nv_sig['resonance_{}'.format(state.name)])
        sig_gen_cxn.set_amp(nv_sig['uwave_power_{}'.format(state.name)])
        sig_gen_cxn.uwave_on()
        pi_pulse = round(nv_sig['rabi_{}'.format(state.name)] / 2)
    cxn.apd_tagger.start_tag_stream(apd_indices)  
    
    tool_belt.init_safe_stop()
    
    for tau_ind in tau_ind_list:
        
        # Break out of the while if the user says stop
        if tool_belt.safe_stop():
            break
        
        tau = taus[tau_ind]
        if seq_file == 'aom_delay.py':
            seq_args = [tau, max_tau, readout, laser_delay, apd_indices[0], color_ind]
#            print(seq_args)
        elif seq_file == 'uwave_delay.py':
            polarization_time = 1000
            wait_time = 1000
            seq_args = [tau, max_tau, readout, pi_pulse, aom_delay, 
                        polarization_time, wait_time, state.value, apd_indices[0]]
        seq_args = [int(el) for el in seq_args]
        seq_args_string = tool_belt.encode_seq_args(seq_args)
        cxn.pulse_streamer.stream_immediate(seq_file, num_reps,
                                            seq_args_string)
        
        new_counts = cxn.apd_tagger.read_counter_separate_gates(1)
        sample_counts = new_counts[0]
        sig_counts[tau_ind] = sum(sample_counts[0::2])
        ref_counts[tau_ind] = sum(sample_counts[1::2])
            
    cxn.apd_tagger.stop_tag_stream()
    tool_belt.reset_cfm(cxn)
    
    # kcps
#    sig_count_rates = (sig_counts / (num_reps * 1000)) / (readout / (10**9))
#    ref_count_rates = (ref_counts / (num_reps * 1000)) / (readout / (10**9))
    norm_avg_sig = sig_counts / ref_counts

    fig, axes_pack = plt.subplots(1, 2, figsize=(17, 8.5))
    ax = axes_pack[0]
    ax.plot(taus, sig_counts, 'r-', label = 'signal')
    ax.plot(taus, ref_counts, 'g-', label = 'reference')
    ax.set_title('Counts vs Delay Time')
    ax.set_xlabel('Delay time (ns)')
    ax.set_ylabel('Count rate (cps)')
    ax.legend()
    ax = axes_pack[1]
    ax.plot(taus, norm_avg_sig, 'b-')
    ax.set_title('Contrast vs Delay Time')
    ax.set_xlabel('Delay time (ns)')
    ax.set_ylabel('Contrast (arb. units)')
    fig.canvas.draw()
    fig.set_tight_layout(True)
    fig.canvas.flush_events()
    
    timestamp = tool_belt.get_time_stamp()
    raw_data = {'timestamp': timestamp,
            'sequence': seq_file,
            'sig_gen': sig_gen,
            'nv_sig': nv_sig,
            'nv_sig-units': tool_belt.get_nv_sig_units(),
            'color_ind': color_ind,
            'readout': readout,
            'readout-units': 'ns',
            'delay_range': delay_range,
            'delay_range-units': 'ns',
            'num_steps': num_steps,
            'num_reps': num_reps,
            'sig_counts': sig_counts.astype(int).tolist(),
            'sig_counts-units': 'counts',
            'ref_counts': ref_counts.astype(int).tolist(),
            'ref_counts-units': 'counts',
            'norm_avg_sig': norm_avg_sig.astype(float).tolist(),
            'norm_avg_sig-units': 'arb'}
    
    file_path = tool_belt.get_file_path(__file__, timestamp, nv_sig['name'])
    tool_belt.save_figure(fig, file_path)
    tool_belt.save_raw_data(raw_data, file_path)


# %% Mains


def aom_delay(cxn, nv_sig, readout, apd_indices,
              delay_range, num_steps, num_reps, color_ind = 532):
    
    seq_file = 'aom_delay.py'
    
    measure_delay(cxn, nv_sig, readout, apd_indices,
              delay_range, num_steps, num_reps, seq_file, color_ind)

def uwave_delay(cxn, nv_sig, apd_indices, state, aom_delay_time,
              delay_range, num_steps, num_reps, color_ind = 532):
    
    '''
    This will incrementally shift the pi pulse through the sequence, starting 
    at the beginning of the sequence. A polorization pulse and wait time after
    of 1000 ns is used. 
    '''
    
    seq_file = 'uwave_delay.py'
    
    readout = nv_sig['pulsed_readout_dur']
    
    measure_delay(cxn, nv_sig, readout, apd_indices,
              delay_range, num_steps, num_reps, seq_file,
              state, color_ind, aom_delay_time)


# %% Run the file


# The __name__ variable will only be '__main__' if you run this file directly.
# This allows a file's functions, classes, etc to be imported without running
# the script that you set up here.
if __name__ == '__main__':

    # Set up your parameters to be passed to main here 
    sample_name = 'hopper'
    nd_filter = 'nd_1.0'
    expected_count_rate = {
            'nd_0': 95,
            'nd_0.5': 85,
            'nd_1.0': 1000,
            'nd_1.5': 25,
            }
    pulsed_readout_dur = {
            'nd_0': 215,
            'nd_0.5': 280,
            'nd_1.0': 350,
            'nd_1.5': 420,
            }

    ensemble = { 'coords': [0.0, 0.0, 5.00],
            'name': '{}-ensemble'.format(sample_name),
            'expected_count_rate': 1000, 'nd_filter': 'nd_0',
            'pulsed_readout_dur': 1000, 'magnet_angle': 0,
            'resonance_LOW': 2.8059, 'rabi_LOW': 173.5, 'uwave_power_LOW': 9.0, 
            'resonance_HIGH': 2.9366, 'rabi_HIGH': 247.4, 'uwave_power_HIGH': 10.0}
    apd_indices = [0]
    num_reps = 2*10**3
    readout = 200
    nv_sig = ensemble

    # aom_delay
    delay_range = [0, 2000]
    num_steps = 151
    with labrad.connect() as cxn:
        aom_delay(cxn, nv_sig, readout, apd_indices,
                  delay_range, num_steps, num_reps, color_ind  =638)

    # uwave_delay
#    delay_range = [500, 2500]
#    num_steps = 101
#    # tsg4104a
##    state = States.LOW
#    # bnc851
#    state = States.HIGH
#    aom_delay_time = 1000
#    with labrad.connect() as cxn:
#        uwave_delay(cxn, nv_sig, apd_indices, state, aom_delay_time,
#              delay_range, num_steps, num_reps)
