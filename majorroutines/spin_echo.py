# -*- coding: utf-8 -*-
"""
Spin echo.

Polarize the nv to 0, then applies a pi/2 pulse to send the state to the
equator. Allow to precess for some time, then apply a pi pulse and allow to
precess for the same amount of time, cancelling the previous precession and
resulting in an echo. Finally readout after a second pi/s pulse.

Created on Wed Apr 24 15:01:04 2019

@author: mccambria
"""

# %% Imports


import utils.tool_belt as tool_belt
import majorroutines.optimize as optimize
import numpy
import time
import matplotlib.pyplot as plt
from random import shuffle
import labrad
from utils.tool_belt import States
from scipy.optimize import curve_fit
from numpy.linalg import eigvals


# %% Constants


im = 0+1j
inv_sqrt_2 = 1/numpy.sqrt(2)
gmuB = 2.8e-3  # gyromagnetic ratio in MHz / G**-


# %% Simplified Hamiltonian analysis
# This assumes no E field, though it does allow for a variable center frequency


def calc_single_hamiltonian(theta_B, center_freq, mag_B):
    # Get parallel and perpendicular components of B field in
    # units of frequency
    par_B = gmuB * mag_B * numpy.cos(theta_B)
    perp_B = gmuB * mag_B * numpy.sin(theta_B)
    hamiltonian = numpy.array([[center_freq + par_B, inv_sqrt_2 * perp_B, 0],
                               [inv_sqrt_2 * perp_B, 0, inv_sqrt_2 * perp_B],
                               [0, inv_sqrt_2 * perp_B, center_freq - par_B]])
    return hamiltonian


def calc_hamiltonian(theta_B, center_freq, mag_B):
    fit_vec = [center_freq, mag_B]
    if (type(theta_B) is list) or (type(theta_B) is numpy.ndarray):
        hamiltonian_list = [calc_single_hamiltonian(val, *fit_vec)
                            for val in theta_B]
        return hamiltonian_list
    else:
        return calc_single_hamiltonian(theta_B, *fit_vec)


def calc_res_pair(theta_B, center_freq, mag_B):
    hamiltonian = calc_hamiltonian(theta_B, center_freq, mag_B)
    if (type(theta_B) is list) or (type(theta_B) is numpy.ndarray):
        vals = numpy.sort(eigvals(hamiltonian), axis=1)
        resonance_low = numpy.real(vals[:,1] - vals[:,0])
        resonance_high = numpy.real(vals[:,2] - vals[:,0])
    else:
        vals = numpy.sort(eigvals(hamiltonian))
        resonance_low = numpy.real(vals[1] - vals[0])
        resonance_high = numpy.real(vals[2] - vals[0])
    return resonance_low, resonance_high


def plot_resonances_vs_theta_B(folder, file, center_freq):
    
    fit_func, popt, stes, fit_fig = fit_data_from_file(folder, file)
    if (fit_func is None) or (popt is None):
        print('Fit failed!')
        return
    
    data = tool_belt.get_raw_data(folder, file)
    nv_sig = data['nv_sig']
    resonance_LOW = nv_sig['resonance_LOW']
    resonance_HIGH = nv_sig['resonance_HIGH']
    
    revival_time = popt[1]
    revival_time_ste = stes[1]
    mag_B, mag_B_ste = mag_B_from_revival_time(revival_time, revival_time_ste)
    print(mag_B)
    print(mag_B_ste)
    num_steps = 1000
    linspace_theta_B = numpy.linspace(0, numpy.pi/2, num_steps)
    
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    fig.set_tight_layout(True)
    res_pairs = calc_res_pair(linspace_theta_B, center_freq, mag_B)
    res_pairs_high = calc_res_pair(linspace_theta_B, center_freq, mag_B+mag_B_ste)
    res_pairs_low = calc_res_pair(linspace_theta_B, center_freq, mag_B-mag_B_ste)
    linspace_theta_B_deg = linspace_theta_B * (180/numpy.pi)
    ax.plot(linspace_theta_B_deg, res_pairs[0])
    ax.fill_between(linspace_theta_B_deg, res_pairs_high[0], res_pairs_low[0],
                    alpha=0.5)
    ax.plot(linspace_theta_B_deg, res_pairs[1])
    ax.fill_between(linspace_theta_B_deg, res_pairs_high[1], res_pairs_low[1],
                    alpha=0.5)
    
    ax.plot(linspace_theta_B_deg, [resonance_LOW
                                   for el in range(0, num_steps)])
    ax.plot(linspace_theta_B_deg, [resonance_HIGH
                                   for el in range(0, num_steps)])
    
    ax.set_xlabel(r'$\theta_{B}$ (deg))')
    ax.set_ylabel('Resonances (GHz)')
    

# %% Functions
    
    
def mag_B_from_revival_time(revival_time, revival_time_ste=None):
    # 1071 Hz/G is the C13 Larmor precession frequency
    mag_B = ((revival_time*10**-6)*1071)**-1
    if revival_time_ste is not None:
        mag_B_ste = mag_B * (revival_time_ste / revival_time)
        return mag_B, mag_B_ste
    else:
        return mag_B
 

def quartic(tau, offset, revival_time, decay_time,
            *amplitudes):
    # return amplitude * numpy.exp(((tau - revival_time)/decay_time)**4)
    # complex_arg = amplitude * numpy.exp((tau - im*revival_time/decay_time)**4)
    # return numpy.real(complex_arg)
    tally = offset
    for ind in range(0, len(amplitudes)):
        exp_part = numpy.exp(-((tau - ind*revival_time)/decay_time)**4)
        tally += amplitudes[ind] * exp_part
    return tally


def fit_data_from_file(folder, file):

    data = tool_belt.get_raw_data(folder, file)
    precession_dur_range = data['precession_time_range']
    sig_counts = data['sig_counts']
    ref_counts = data['ref_counts']
    num_steps = data['num_steps']
    num_runs = data['num_runs']
    
    # Get the pi pulse duration
    state = data['state']
    nv_sig = data['nv_sig']
    pi_pulse_dur = nv_sig['rabi_{}'.format(state)]
    
    ret_vals =  fit_data(precession_dur_range, pi_pulse_dur,
                         num_steps, num_runs,
                         sig_counts, ref_counts)
    return ret_vals


def fit_data(precession_dur_range, pi_pulse_dur,
             num_steps, num_runs,
             sig_counts, ref_counts):
    
    # Everything here is converted to us!!

    # %% Set up

    min_precession_dur = precession_dur_range[0]
    min_precession_dur_us = float(min_precession_dur) / 1000
    max_precession_dur = precession_dur_range[1]
    max_precession_dur_us = float(max_precession_dur) / 1000
    taus, tau_step  = numpy.linspace(min_precession_dur_us,
                                     max_precession_dur_us,
                                     num=num_steps, dtype=float, retstep=True)
    
    # Account for the pi/2 pulse on each side of a tau
    pi_pulse_dur_us = float(pi_pulse_dur) / 1000
    taus += pi_pulse_dur_us
    
    fit_func = quartic
    
    # %% Normalization and uncertainty
    
    avg_sig_counts = numpy.average(sig_counts[::], axis=0)
    ste_sig_counts = numpy.std(sig_counts[::], axis=0, ddof = 1) / numpy.sqrt(num_runs)
    
    # Assume reference is constant and can be approximated to one value
    avg_ref = numpy.average(ref_counts[::])

    # Divide signal by reference to get normalized counts and st error
    norm_avg_sig = avg_sig_counts / avg_ref
    norm_avg_sig_ste = ste_sig_counts / avg_ref

    # %% Estimated fit parameters

    # Assume that the bulk of points are the floor and that revivals take
    # us back to 1.0
    amplitude = 1.0 - numpy.average(norm_avg_sig)
    offset = 1.0 - amplitude
    decay_time = 3

    # To estimate the revival frequency let's find the highest peak in the FFT
    transform = numpy.fft.rfft(norm_avg_sig)
    freqs = numpy.fft.rfftfreq(num_steps, d=tau_step)
    transform_mag = numpy.absolute(transform)
    # [1:] excludes frequency 0 (DC component)
    max_ind = numpy.argmax(transform_mag[1:])
    frequency = freqs[max_ind+1]
    revival_time = 1/frequency
    
    num_revivals = max_precession_dur_us / revival_time
    amplitudes = [amplitude for el in range(0, int(1.5*num_revivals))]

    # %% Fit
    
    init_params = [offset, revival_time, decay_time, *amplitudes]
    min_bounds = (0.5, 0.0, 0.0, *[0.0 for el in amplitudes])
    max_bounds = (1.0, max_precession_dur_us, max_precession_dur_us,
                  *[0.3 for el in amplitudes])

    try:
        popt, pcov = curve_fit(fit_func, taus, norm_avg_sig,
                                sigma=norm_avg_sig_ste, absolute_sigma=True,
                                p0=init_params, bounds=(min_bounds, max_bounds))
    except Exception as e:
        print(e)
        popt = None
        
    revival_time = popt[1]
    stes = numpy.sqrt(numpy.diag(pcov))

    if (fit_func is not None) and (popt is not None):
        fit_fig = create_fit_figure(precession_dur_range, pi_pulse_dur,
                                    num_steps, norm_avg_sig, norm_avg_sig_ste, 
                                    fit_func, popt)

    return fit_func, popt, stes, fit_fig

def create_fit_figure(precession_dur_range, pi_pulse_dur,
                      num_steps, norm_avg_sig, norm_avg_sig_ste,
                      fit_func, popt):
    
    min_precession_dur = precession_dur_range[0]
    min_precession_dur_us = float(min_precession_dur) / 1000
    max_precession_dur = precession_dur_range[1]
    max_precession_dur_us = float(max_precession_dur) / 1000
    taus = numpy.linspace(min_precession_dur_us, max_precession_dur_us,
                          num=num_steps, dtype=float)
    # Account for the pi/2 pulse on each side of a tau
    pi_pulse_dur_us = float(pi_pulse_dur) / 1000
    taus += pi_pulse_dur_us
    linspaceTau = numpy.linspace(min_precession_dur_us+pi_pulse_dur_us,
                                 max_precession_dur_us+pi_pulse_dur_us,
                                 num=1000)
    

    fit_fig, ax = plt.subplots(figsize=(8.5, 8.5))
    fit_fig.set_tight_layout(True)
    ax.plot(taus, norm_avg_sig,'bo',label='data')
    # ax.errorbar(taus, norm_avg_sig, yerr=norm_avg_sig_ste,\
    #             fmt='bo', label='data')
    ax.plot(linspaceTau, fit_func(linspaceTau, *popt), 'r-', label='fit')
    ax.set_xlabel(r'$\tau + \pi/2$ ($\mathrm{\mu s}$)')
    ax.set_ylabel('Contrast (arb. units)')
    ax.set_title('Spin Echo')
    ax.legend()
    
    revival_time = popt[1]
    text_popt = '\n'.join(
        (
            r'$\tau_{r}=$%.3f $\mathrm{\mu s}$'%(revival_time),
            r'$B=$%.3f G'%(mag_B_from_revival_time(revival_time)),
         )
        )

    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.80, 0.90, text_popt, transform=ax.transAxes, fontsize=12,
            verticalalignment='top', bbox=props)

    fit_fig.canvas.draw()
    fit_fig.set_tight_layout(True)
    fit_fig.canvas.flush_events()

    return fit_fig


# %% Main

def main(nv_sig, apd_indices,
         precession_dur_range, num_steps, num_reps, num_runs,
         state=States.LOW):

    with labrad.connect() as cxn:
        main_with_cxn(cxn, nv_sig, apd_indices,
                  precession_dur_range, num_steps, num_reps, num_runs,
                  state)

def main_with_cxn(cxn, nv_sig, apd_indices,
                  precession_time_range, num_steps, num_reps, num_runs,
                  state=States.LOW):
    
    tool_belt.reset_cfm(cxn)
    
    # %% Define the times to be used in the sequence

    shared_params = tool_belt.get_shared_parameters_dict(cxn)

    polarization_time = shared_params['polarization_dur']
    # time of illumination during which signal readout occurs
    signal_time = polarization_time
    # time of illumination during which reference readout occurs
    reference_time = polarization_time
    pre_uwave_exp_wait_time = shared_params['post_polarization_wait_dur']
    post_uwave_exp_wait_time = shared_params['pre_readout_wait_dur']
    # time between signal and reference without illumination
    sig_to_ref_wait_time = pre_uwave_exp_wait_time + post_uwave_exp_wait_time
    aom_delay_time = shared_params['532_aom_delay']
    rf_delay_time = shared_params['uwave_delay']
    gate_time = nv_sig['pulsed_readout_dur']
    
    # Default to the low state
    rabi_period = nv_sig['rabi_{}'.format(state.name)]
    uwave_freq = nv_sig['resonance_{}'.format(state.name)]
    uwave_power = nv_sig['uwave_power_{}'.format(state.name)]

    # Get pulse frequencies
    uwave_pi_pulse = round(rabi_period / 2)
    uwave_pi_on_2_pulse = round(rabi_period / 4)
    
    seq_file_name = 'spin_echo.py'

    # %% Create the array of relaxation times
    
    # Array of times to sweep through
    # Must be ints
    min_precession_time = int(precession_time_range[0])
    max_precession_time = int(precession_time_range[1])
    
    taus = numpy.linspace(min_precession_time, max_precession_time,
                          num=num_steps, dtype=numpy.int32)
     
    # %% Fix the length of the sequence to account for odd amount of elements
     
    # Our sequence pairs the longest time with the shortest time, and steps 
    # toward the middle. This means we only step through half of the length
    # of the time array. 
    
    # That is a problem if the number of elements is odd. To fix this, we add 
    # one to the length of the array. When this number is halfed and turned 
    # into an integer, it will step through the middle element.
    
    if len(taus) % 2 == 0:
        half_length_taus = int( len(taus) / 2 )
    elif len(taus) % 2 == 1:
        half_length_taus = int( (len(taus) + 1) / 2 )
        
    # Then we must use this half length to calculate the list of integers to be
    # shuffled for each run
    
    tau_ind_list = list(range(0, half_length_taus))
        
    # %% Create data structure to save the counts
    
    # We create an array of NaNs that we'll fill
    # incrementally for the signal and reference counts. 
    # NaNs are ignored by matplotlib, which is why they're useful for us here.
    # We define 2D arrays, with the horizontal dimension for the frequency and
    # the veritical dimension for the index of the run.
    
    sig_counts = numpy.empty([num_runs, num_steps], dtype=numpy.uint32)
    sig_counts[:] = numpy.nan
    ref_counts = numpy.copy(sig_counts)
    
    # %% Make some lists and variables to save at the end
    
    opti_coords_list = []
    tau_index_master_list = [[] for i in range(num_runs)]
    
    # %% Analyze the sequence
    
    # We can simply reuse t1_double_quantum for this if we pass a pi/2 pulse
    # instead of a pi pulse and use the same states for init/readout
    seq_args = [min_precession_time, polarization_time, signal_time, reference_time, 
                sig_to_ref_wait_time, pre_uwave_exp_wait_time, 
                post_uwave_exp_wait_time, aom_delay_time, rf_delay_time, 
                gate_time, uwave_pi_pulse, uwave_pi_on_2_pulse,
                max_precession_time, apd_indices[0], state.value]
    seq_args_string = tool_belt.encode_seq_args(seq_args)
    seq_args = [int(el) for el in seq_args]
    ret_vals = cxn.pulse_streamer.stream_load(seq_file_name, seq_args_string)
    seq_time = ret_vals[0]
#    print(sequence_args)
#    print(seq_time)
    
    # %% Let the user know how long this will take
    
    seq_time_s = seq_time / (10**9)  # to seconds
    expected_run_time_s = (num_steps/2) * num_reps * num_runs * seq_time_s  # s
    expected_run_time_m = expected_run_time_s / 60  # to minutes
    
    print(' \nExpected run time: {:.1f} minutes. '.format(expected_run_time_m))
#    return
    
    # %% Get the starting time of the function, to be used to calculate run time

    startFunctionTime = time.time()
    start_timestamp = tool_belt.get_time_stamp()
    
    # %% Collect the data
    
    # Start 'Press enter to stop...'
    tool_belt.init_safe_stop()
    
    for run_ind in range(num_runs):

        print(' \nRun index: {}'.format(run_ind))
        
        # Break out of the while if the user says stop
        if tool_belt.safe_stop():
            break
        
        # Optimize
        opti_coords = optimize.main_with_cxn(cxn, nv_sig, apd_indices)
        opti_coords_list.append(opti_coords)
        
        # Set up the microwaves
        sig_gen_cxn = tool_belt.get_signal_generator_cxn(cxn, state)
        sig_gen_cxn.set_freq(uwave_freq)
        sig_gen_cxn.set_amp(uwave_power)
        sig_gen_cxn.uwave_on()
            
        # Load the APD
        cxn.apd_tagger.start_tag_stream(apd_indices)  
        
        # Shuffle the list of tau indices so that it steps thru them randomly
        shuffle(tau_ind_list)
                
        for tau_ind in tau_ind_list:
            
            # 'Flip a coin' to determine which tau (long/shrt) is used first
            rand_boolean = numpy.random.randint(0, high=2)
            
            if rand_boolean == 1:
                tau_ind_first = tau_ind
                tau_ind_second = -tau_ind - 1
            elif rand_boolean == 0:
                tau_ind_first = -tau_ind - 1
                tau_ind_second = tau_ind
                
            # add the tau indexxes used to a list to save at the end
            tau_index_master_list[run_ind].append(tau_ind_first)
            tau_index_master_list[run_ind].append(tau_ind_second)

            # Break out of the while if the user says stop
            if tool_belt.safe_stop():
                break
            
            print(' \nFirst relaxation time: {}'.format(taus[tau_ind_first]))
            print('Second relaxation time: {}'.format(taus[tau_ind_second])) 
            
            seq_args = [taus[tau_ind_first], polarization_time, signal_time, reference_time, 
                        sig_to_ref_wait_time, pre_uwave_exp_wait_time, 
                        post_uwave_exp_wait_time, aom_delay_time, rf_delay_time, 
                        gate_time, uwave_pi_pulse, uwave_pi_on_2_pulse,
                        taus[tau_ind_second], apd_indices[0], state.value]
            seq_args = [int(el) for el in seq_args]
            seq_args_string = tool_belt.encode_seq_args(seq_args)
            cxn.pulse_streamer.stream_immediate(seq_file_name, num_reps,
                                                seq_args_string)   
            
            # Each sample is of the form [*(<sig_shrt>, <ref_shrt>, <sig_long>, <ref_long>)]
            # So we can sum on the values for similar index modulus 4 to
            # parse the returned list into what we want.
            new_counts = cxn.apd_tagger.read_counter_separate_gates(1)
            sample_counts = new_counts[0]
            
            count = sum(sample_counts[0::4])
            sig_counts[run_ind, tau_ind_first] = count
            print('First signal = ' + str(count))
            
            count = sum(sample_counts[1::4])
            ref_counts[run_ind, tau_ind_first] = count  
            print('First Reference = ' + str(count))
            
            count = sum(sample_counts[2::4])
            sig_counts[run_ind, tau_ind_second] = count
            print('Second Signal = ' + str(count))

            count = sum(sample_counts[3::4])
            ref_counts[run_ind, tau_ind_second] = count
            print('Second Reference = ' + str(count))
            
        cxn.apd_tagger.stop_tag_stream()
        
        # %% Save the data we have incrementally for long T1s

        raw_data = {'start_timestamp': start_timestamp,
                'nv_sig': nv_sig,
                'nv_sig-units': tool_belt.get_nv_sig_units(),
                'gate_time': gate_time,
                'gate_time-units': 'ns',
                'uwave_freq': uwave_freq,
                'uwave_freq-units': 'GHz',
                'uwave_power': uwave_power,
                'uwave_power-units': 'dBm',
                'rabi_period': rabi_period,
                'rabi_period-units': 'ns',
                'uwave_pi_pulse': uwave_pi_pulse,
                'uwave_pi_pulse-units': 'ns',
                'uwave_pi_on_2_pulse': uwave_pi_on_2_pulse,
                'uwave_pi_on_2_pulse-units': 'ns',
                'precession_time_range': precession_time_range,
                'precession_time_range-units': 'ns',
                'state': state.name,
                'num_steps': num_steps,
                'num_reps': num_reps,
                'run_ind': run_ind,
                'tau_index_master_list': tau_index_master_list,
                'opti_coords_list': opti_coords_list,
                'opti_coords_list-units': 'V',
                'sig_counts': sig_counts.astype(int).tolist(),
                'sig_counts-units': 'counts',
                'ref_counts': ref_counts.astype(int).tolist(),
                'ref_counts-units': 'counts'}

        # This will continuously be the same file path so we will overwrite
        # the existing file with the latest version
        file_path = tool_belt.get_file_path(__file__, start_timestamp,
                                            nv_sig['name'], 'incremental')
        tool_belt.save_raw_data(raw_data, file_path)

    # %% Hardware clean up
    
    tool_belt.reset_cfm(cxn)
    
    # %% Average the counts over the iterations

    avg_sig_counts = numpy.average(sig_counts, axis=0)
    avg_ref_counts = numpy.average(ref_counts, axis=0)
    
    # %% Calculate the ramsey data, signal / reference over different 
    # relaxation times

    # Replace x/0=inf with 0
    try:
        norm_avg_sig = avg_sig_counts / avg_ref_counts
    except RuntimeWarning as e:
        print(e)
        inf_mask = numpy.isinf(norm_avg_sig)
        # Assign to 0 based on the passed conditional array
        norm_avg_sig[inf_mask] = 0
    
    # %% Plot the data

    raw_fig, axes_pack = plt.subplots(1, 2, figsize=(17, 8.5))

    ax = axes_pack[0]
    ax.plot(taus / 10**3, avg_sig_counts, 'r-', label = 'signal')
    ax.plot(taus / 10**3, avg_ref_counts, 'g-', label = 'reference')
    ax.set_xlabel('\u03C4 (us)')  # tau = \u03C4 in unicode
    ax.set_ylabel('Counts')
    ax.legend()

    ax = axes_pack[1]
    ax.plot(taus / 10**3, norm_avg_sig, 'b-')
    ax.set_title('Spin Echo Measurement')
    ax.set_xlabel('Precession time (us)')
    ax.set_ylabel('Contrast (arb. units)')

    raw_fig.canvas.draw()
#     fig.set_tight_layout(True)
    raw_fig.canvas.flush_events()
    
    # %% Save the data

    endFunctionTime = time.time()

    timeElapsed = endFunctionTime - startFunctionTime

    timestamp = tool_belt.get_time_stamp()
    
    raw_data = {'timestamp': timestamp,
            'timeElapsed': timeElapsed,
            'nv_sig': nv_sig,
            'nv_sig-units': tool_belt.get_nv_sig_units(),
            'gate_time': gate_time,
            'gate_time-units': 'ns',
            'uwave_freq': uwave_freq,
            'uwave_freq-units': 'GHz',
            'uwave_power': uwave_power,
            'uwave_power-units': 'dBm',
            'rabi_period': rabi_period,
            'rabi_period-units': 'ns',
            'uwave_pi_pulse': uwave_pi_pulse,
            'uwave_pi_pulse-units': 'ns',
            'uwave_pi_on_2_pulse': uwave_pi_on_2_pulse,
            'uwave_pi_on_2_pulse-units': 'ns',
            'precession_time_range': precession_time_range,
            'precession_time_range-units': 'ns',
            'state': state.name,
            'num_steps': num_steps,
            'num_reps': num_reps,
            'num_runs': num_runs,
            'tau_index_master_list': tau_index_master_list,
            'opti_coords_list': opti_coords_list,
            'opti_coords_list-units': 'V',
            'sig_counts': sig_counts.astype(int).tolist(),
            'sig_counts-units': 'counts',
            'ref_counts': ref_counts.astype(int).tolist(),
            'ref_counts-units': 'counts',
            'norm_avg_sig': norm_avg_sig.astype(float).tolist(),
            'norm_avg_sig-units': 'arb'}
    
    file_path = tool_belt.get_file_path(__file__, timestamp, nv_sig['name'])
    tool_belt.save_figure(raw_fig, file_path)
    tool_belt.save_raw_data(raw_data, file_path)


# %% Run the file


if __name__ == '__main__':

    center_freq = 2.8703  # zfs in GHz
    folder = 'spin_echo/2019_12'
#    file = '2019_12_22-16_46_54-goeppert_mayer-nv7_2019_11_27'
#    file = '2019_12_22-19_18_05-goeppert_mayer-nv7_2019_11_27'
#    file = '2019_12_30-16_23_51-goeppert_mayer-nv7_2019_11_27'
    file = '2019_12_30-18_22_09-goeppert_mayer-nv7_2019_11_27'
    
    # fit_func, popt, stes, fit_fig = fit_data_from_file(folder, file)
        
    plot_resonances_vs_theta_B(folder, file, center_freq)
