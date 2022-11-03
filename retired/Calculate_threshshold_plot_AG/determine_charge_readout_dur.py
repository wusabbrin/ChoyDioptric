# -*- coding: utf-8 -*-
"""
Created on Thu Apr 22 14:09:39 2021

@author: samli
"""

# import labrad
import scipy.stats
import scipy.special
import numpy
import math
import copy
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import random
import chargeroutines.photonstatistics as model
import labrad

import utils.tool_belt as tool_belt
import majorroutines.optimize as optimize

#%% import your data in the data_file
# import NV_data as data
#%% functions

#fit the NV- and NV0 counts to the rate model
def get_photon_dis_curve_fit_plot(readout_time,NV0,NVm, do_plot = True): # NV0, NVm in array
    trail_nv0_30ms = numpy.array(NV0)
    trail_nvm_30ms = numpy.array(NVm)
    tR = readout_time
    combined_count = trail_nvm_30ms.tolist() + trail_nv0_30ms.tolist()
    random.shuffle(combined_count)
    # fit = [g0,g1,y1,y0]

    # if it is the SiV sample, use this guess
    # guess = [ 0.01 ,0.02, 0.57, 0.08]

    # if it is the E6 sample, use this guess
    guess = [ 1e-3,1e-8, 1e-1, 1e-2]
    # fit gives g0, g1, y1, y0
    fit,dev = model.get_curve_fit(tR,0,combined_count,guess)
#    print(fit,np.diag(dev))

    if do_plot:
        u_value0, freq0 = model.get_Probability_distribution(trail_nv0_30ms.tolist())
        u_valuem, freqm = model.get_Probability_distribution(trail_nvm_30ms.tolist())
        u_value2, freq2 = model.get_Probability_distribution(combined_count)
        curve = model.get_photon_distribution_curve(tR,u_value2, fit[0] ,fit[1], fit[2] ,fit[3])

        A1, A1pcov = model.get_curve_fit_to_weight(tR,0,trail_nv0_30ms.tolist(),[0.5],fit)
        A2, A2pcov = model.get_curve_fit_to_weight(tR,0,trail_nvm_30ms.tolist(),[0.5],fit)

        nv0_curve = model.get_photon_distribution_curve_weight(u_value0,tR, fit[0] ,fit[1], fit[2] ,fit[3],A1[0])
        nvm_curve = model.get_photon_distribution_curve_weight(u_valuem,tR, fit[0] ,fit[1], fit[2] ,fit[3],A2[0])
        fig4, ax = plt.subplots()
        ax.plot(u_value0,0.5*np.array(freq0),"-ro")
        ax.plot(u_valuem,0.5*np.array(freqm),"-go")
        ax.plot(u_value2,freq2,"-bo")
        ax.plot(u_value2,curve)
        ax.plot(u_valuem,0.5*np.array(nvm_curve),"green")
        ax.plot(u_value0,0.5*np.array(nv0_curve),"red")
        textstr = '\n'.join((
        r'$g_0(s^{-1}) =%.2f$'% (fit[0]*10**3, ),
        r'$g_1(s^{-1})  =%.2f$'% (fit[1]*10**3, ),
        r'$y_0 =%.2f$'% (fit[3], ),
        r'$y_1 =%.2f$'% (fit[2], )))
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.6, 0.95, textstr, transform=ax.transAxes, fontsize=12,
            verticalalignment='top', bbox=props)
        plt.xlabel("Number of counts")
        plt.ylabel("Probability Density")
        plt.show()
    return fit

# calculate the threshold of given NV0 and NV- data
# tR in units of ms
def calculate_threshold_plot(readout_time,nv0_array,nvm_array, nd_filter, aom_power):
    tR = readout_time
    fit_rate = get_photon_dis_curve_fit_plot(readout_time,nv0_array,nvm_array)
    # fit_rate=[4.90996754e-03, 3.36515387e-10, 1.15328406e-01, 3.99459743e-02]
    x_data = np.linspace(0,50,51)
    thresh_para = model.calculate_threshold(tR,x_data,fit_rate )
    print(thresh_para)

    x_data = np.linspace(0,60,61)
    fig3,ax = plt.subplots()
    ax.plot(x_data,model.get_PhotonNV0_list(x_data,tR,fit_rate,0.5),"-o")
    ax.plot(x_data,model.get_PhotonNVm_list(x_data,tR,fit_rate,0.5),"-o")
    plt.axvline(x=thresh_para[0],color = "red")
    mu_1 = fit_rate[3]*tR
    mu_2 = fit_rate[2]*tR
    textstr = '\n'.join((
        r'$\mu_1=%.2f$' % ( mu_1 ),
        r'$\mu_2=%.2f$'% (mu_2),
        r'$fidelity =%.2f$'% (thresh_para[1] ),
        r'$threshold = %.1f$'% (thresh_para[0], )))
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.65, 0.95, textstr, transform=ax.transAxes, fontsize=12,
            verticalalignment='top', bbox=props)
    plt.xlabel("Number of counts")
    plt.ylabel("Probability Density")
    plt.title('{} ms readout, {}, {} V'.format(readout_time, nd_filter, aom_power))

    fidelity = thresh_para[1]
    threshold =thresh_para[0]
    return threshold, fidelity, mu_1, mu_2, fig3

def calculate_threshold_plot_no_model(nv0_hist,nvm_hist,mu0, mu1, x_vals_0, x_vals_m):
    
    thresh, fid = model.calculate_threshold_from_experiment( x_vals_0[:-1], x_vals_m[:-1],mu0, mu1, nv0_hist, nvm_hist)

    fig3, ax = plt.subplots(1, 1)
    ax.plot(x_vals_0[:-1],nv0_hist,  'r-o', label = 'Test red pulse' )
    ax.plot(x_vals_m[:-1],nvm_hist,  'g-o', label = 'Test green pulse' )
    ax.set_xlabel('Counts')
    ax.set_ylabel('Occur.')
    plt.axvline(x=thresh,color = "red")
    textstr = '\n'.join((
        r'$\mu_0=%.2f$' % (mu0 ),
        r'$\mu_1=%.2f$'% (mu1 ),
        r'$threshold = %.1f$'% (thresh )))
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.65, 0.95, textstr, transform=ax.transAxes, fontsize=12,
            verticalalignment='top', bbox=props)
    plt.xlabel("Number of counts")
    plt.ylabel("Probability Density")
    return thresh, fid, fig3

# %%
# Apply a gren or red pulse, then measure the counts under yellow illumination.
# Repeat num_reps number of times and returns the list of counts after red illumination, then green illumination
# Use with DM on red and green
def measure(nv_sig, opti_nv_sig, apd_indices, num_reps):

    with labrad.connect() as cxn:
        sig_counts, ref_counts = measure_with_cxn(cxn, nv_sig,opti_nv_sig,  apd_indices, num_reps)

    return sig_counts, ref_counts
def measure_with_cxn(cxn, nv_sig, opti_nv_sig, apd_indices, num_reps):

    tool_belt.reset_cfm(cxn)

    # Optimize
    opti_coords_list = []
    opti_coords = optimize.main_with_cxn(cxn, opti_nv_sig, apd_indices)
    opti_coords_list.append(opti_coords)

    # Initial Calculation and setup

    tool_belt.set_filter(cxn, nv_sig, 'charge_readout_laser')
    tool_belt.set_filter(cxn, nv_sig, 'nv-_prep_laser')

    readout_laser_power = tool_belt.set_laser_power(cxn, nv_sig, 'charge_readout_laser')
    nvm_laser_power = tool_belt.set_laser_power(cxn, nv_sig, "nv-_prep_laser")
    nv0_laser_power = tool_belt.set_laser_power(cxn,nv_sig,"nv0_prep_laser")


    readout_pulse_time = nv_sig['charge_readout_dur']

    reionization_time = nv_sig['nv-_prep_laser_dur']
    ionization_time = nv_sig['nv0_prep_laser_dur']

    # Pulse sequence to do a single pulse followed by readout
    seq_file = 'simple_readout_two_pulse.py'


    ################## Load the measuremnt with green laser ##################
      
    seq_args = [reionization_time, readout_pulse_time, nv_sig["nv-_prep_laser"],
                nv_sig["charge_readout_laser"], nvm_laser_power,
                readout_laser_power, 2, apd_indices[0]]
    seq_args_string = tool_belt.encode_seq_args(seq_args)
    cxn.pulse_streamer.stream_load(seq_file, seq_args_string)
    print(seq_args)

    # Load the APD
    cxn.apd_tagger.start_tag_stream(apd_indices)
    # Clear the buffer
    cxn.apd_tagger.clear_buffer()
    # Run the sequence
    cxn.pulse_streamer.stream_immediate(seq_file, num_reps, seq_args_string)

    nvm = cxn.apd_tagger.read_counter_simple(num_reps)
    
    
    opti_coords = optimize.main_with_cxn(cxn, opti_nv_sig, apd_indices)
    opti_coords_list.append(opti_coords)
    

    ################## Load the measuremnt with red laser ##################
    seq_args = [ionization_time, readout_pulse_time, nv_sig["nv0_prep_laser"],
                nv_sig["charge_readout_laser"], nv0_laser_power,
                readout_laser_power, 2,apd_indices[0]]
    seq_args_string = tool_belt.encode_seq_args(seq_args)
    cxn.pulse_streamer.stream_load(seq_file, seq_args_string)
    print(seq_args)

    # Load the APD
    cxn.apd_tagger.start_tag_stream(apd_indices)
    # Clear the buffer
    cxn.apd_tagger.clear_buffer()
    # Run the sequence
    cxn.pulse_streamer.stream_immediate(seq_file, num_reps, seq_args_string)

    nv0 = cxn.apd_tagger.read_counter_simple(num_reps)


    tool_belt.reset_cfm(cxn)

    return nv0, nvm

# %%
# Apply an initialization pulse, then pulse either green or red pulse, 
# finally measure the counts under yellow illumination.
# Repeat num_reps number of times and returns the list of counts after red illumination, then green illumination

def measure_3(nv_sig, opti_nv_sig, apd_indices, num_reps):

    with labrad.connect() as cxn:
        sig_counts, ref_counts = measure_3_with_cxn(cxn, nv_sig,opti_nv_sig,  apd_indices, num_reps)

    return sig_counts, ref_counts
def measure_3_with_cxn(cxn, nv_sig, opti_nv_sig, apd_indices, num_reps):

    tool_belt.reset_cfm(cxn)

    # Optimize
    opti_coords_list = []
    opti_coords = optimize.main_with_cxn(cxn, opti_nv_sig, apd_indices)
    opti_coords_list.append(opti_coords)

    # Initial Calculation and setup

    tool_belt.set_filter(cxn, nv_sig, 'charge_readout_laser')
    tool_belt.set_filter(cxn, nv_sig, 'initialization_laser')
    tool_belt.set_filter(cxn, nv_sig, 'nv-_prep_laser')

    readout_laser_power = tool_belt.set_laser_power(cxn, nv_sig, 'charge_readout_laser')
    init_laser_power = tool_belt.set_laser_power(cxn, nv_sig, "initialization_laser")
    nvm_laser_power = tool_belt.set_laser_power(cxn, nv_sig, "nv-_prep_laser")
    nv0_laser_power = tool_belt.set_laser_power(cxn,nv_sig,"nv0_prep_laser")


    readout_pulse_time = nv_sig['charge_readout_dur']

    initialization_time = nv_sig['initialization_laser_dur']
    reionization_time = nv_sig['nv-_prep_laser_dur']
    ionization_time = nv_sig['nv0_prep_laser_dur']

    # Pulse sequence to do a single pulse followed by readout
    seq_file = 'simple_readout_three_pulse.py'


    ################## Load the measuremnt with green laser ##################
      
    seq_args = [initialization_time, reionization_time, readout_pulse_time, 
                  nv_sig["initialization_laser"], nv_sig["nv-_prep_laser"], nv_sig["charge_readout_laser"], 
                  init_laser_power, nvm_laser_power, readout_laser_power, apd_indices[0]]
    seq_args_string = tool_belt.encode_seq_args(seq_args)
    cxn.pulse_streamer.stream_load(seq_file, seq_args_string)
    
    print(seq_args)

    # Load the APD
    cxn.apd_tagger.start_tag_stream(apd_indices)
    # Clear the buffer
    cxn.apd_tagger.clear_buffer()
    # Run the sequence
    cxn.pulse_streamer.stream_immediate(seq_file, num_reps, seq_args_string)

    nvm = cxn.apd_tagger.read_counter_simple(num_reps)
    
    
    opti_coords = optimize.main_with_cxn(cxn, opti_nv_sig, apd_indices)
    opti_coords_list.append(opti_coords)

    ################## Load the measuremnt with no test laser ##################
    
    seq_args = [initialization_time, ionization_time, readout_pulse_time, 
                  nv_sig["initialization_laser"], None, nv_sig["charge_readout_laser"], 
                  init_laser_power, nv0_laser_power, readout_laser_power, apd_indices[0]]

    seq_args_string = tool_belt.encode_seq_args(seq_args)
    cxn.pulse_streamer.stream_load(seq_file, seq_args_string)
    print(seq_args)

    # Load the APD
    cxn.apd_tagger.start_tag_stream(apd_indices)
    # Clear the buffer
    cxn.apd_tagger.clear_buffer()
    # Run the sequence
    cxn.pulse_streamer.stream_immediate(seq_file, num_reps, seq_args_string)

    nv0 = cxn.apd_tagger.read_counter_simple(num_reps)


    tool_belt.reset_cfm(cxn)

    return nv0, nvm

def determine_readout_dur(nv_sig, opti_nv_sig, apd_indices,
                          readout_times=None, readout_yellow_powers=None,
                          nd_filter='nd_0.5', num_pulses = 2,
                          fit_threshold_full_model = True):
    '''
    

    Parameters
    ----------
    nv_sig : TYPE
        parameters of NV we intend to measure on.
    opti_nv_sig : TYPE
        parameters of a single NV to optimize on. Can be same as nv_sig.
    apd_indices : TYPE
        apds to read counts from.
    readout_times : TYPE, optional
        Yellow readout durations to measure. Each one is individually measured. The default is None.
    readout_yellow_powers : TYPE, optional
        The powers of the yellow power (typically a voltage between 0 to 1.0 for the AOM of the yellow laser). The default is None.
    nd_filter : TYPE, optional
        Usually, the yellow laser has an ND filter slider in it's path, which can be set here. The default is 'nd_0.5'.

    Returns
    -------
    None.

    '''
    num_reps = 500
    # num_reps = int(2e4)

    # standard readout times to test are 50, 100, 250 ms.
    if readout_times is None:
        readout_times = [50*10**6, 100*10**6, 250*10**6]
    # standard readout powers to test are below.
    if readout_yellow_powers is None:
        readout_yellow_powers = [0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6]

    # Set us lists to save data in. These will be 3D lists:
    # first index will be power, second will be time, third will be individual points
    nv0_master = []
    nvm_master =[]

    tool_belt.init_safe_stop()

    for p in readout_yellow_powers:
        nv0_power =[]
        nvm_power =[]
        for t in readout_times:
            # Break out of the while if the user says stop
            if tool_belt.safe_stop():
                break

            nv_sig_copy = copy.deepcopy(nv_sig)
            if nd_filter is not None:
                nv_sig_copy['charge_readout_laser_filter'] = nd_filter
            nv_sig_copy['charge_readout_dur'] = t
            nv_sig_copy['charge_readout_laser_power'] = p
            
            if num_pulses == 3:
                nv0, nvm = measure_3(nv_sig_copy, opti_nv_sig, apd_indices, num_reps)
            elif num_pulses == 2:
                nv0, nvm = measure(nv_sig_copy, opti_nv_sig, apd_indices, num_reps)
            nv0_power.append(nv0)
            nvm_power.append(nvm)
            timestamp = tool_belt.get_time_stamp()
            raw_data = {'timestamp': timestamp,
                    'nv_sig': nv_sig_copy,
                    'nv_sig-units': tool_belt.get_nv_sig_units(),
                    'num_pulses': num_pulses,
                    'num_runs':num_reps,
                    'nv0': nv0.tolist(),
                    'nv0_list-units': 'counts',
                    'nvm': nvm.tolist(),
                    'nvmt-units': 'counts',
                    }

            fig_hist, ax = plt.subplots(1, 1)
            max_0 = max(nv0)
            max_m = max(nvm)
            occur_0, x_vals_0 = numpy.histogram(nv0, numpy.linspace(0,max_0, max_0+1))
            occur_m, x_vals_m = numpy.histogram(nvm, numpy.linspace(0,max_m, max_m+1))
            # print(occur_0)
            # print(occur_m)
            ax.plot(x_vals_0[:-1],occur_0,  'r-o', label = 'Test red pulse' )
            ax.plot(x_vals_m[:-1],occur_m,  'g-o', label = 'Test green pulse' )
            ax.set_xlabel('Counts')
            ax.set_ylabel('Occur.')
            ax.set_title('{} ms readout, {}, {} V'.format(t/10**6, nd_filter, p))
            ax.legend()

            file_path = tool_belt.get_file_path(__file__, timestamp, nv_sig['name']+'histogram' )
            tool_belt.save_raw_data(raw_data, file_path)
            tool_belt.save_figure(fig_hist, file_path)

            print('data collected!')
            # return
            # print('{} ms readout, {}, {} V'.format(t/10**6, nd_filter, p))
            # print(nv0)
            if fit_threshold_full_model:
                threshold, fidelity, mu_0, mu_m, fig = calculate_threshold_plot(t/10**6, nv0, nvm, nd_filter, p)
            else:
                mu_0 = numpy.mean(nv0)
                mu_m = numpy.mean(nvm)
                threshold, fidelity, fig = calculate_threshold_plot_no_model(occur_0, 
                                                      occur_m,mu_0, mu_m,x_vals_0, x_vals_m)


            raw_data = {'timestamp': timestamp,
                    'nv_sig': nv_sig_copy,
                    'nv_sig-units': tool_belt.get_nv_sig_units(),
                    'num_runs':num_reps,
                    'nv0': nv0.tolist(),
                    'nv0_list-units': 'counts',
                    'nvm': nvm.tolist(),
                    'nvmt-units': 'counts',
                    'mu_0': mu_0,
                    'mu_m': mu_m,
                    'fidelity': fidelity,
                    'threshold': threshold
                    }

            file_path = tool_belt.get_file_path(__file__, timestamp, nv_sig['name'])
            tool_belt.save_raw_data(raw_data, file_path)
            tool_belt.save_figure(fig, file_path)


        nv0_master.append(nv0_power)
        nvm_master.append(nvm_power)

    return

# def sweep_readout_dur(nv_sig, readout_times = None, readout_yellow_power = 0.4,
#                           nd_filter = 'nd_0.5'):
#     num_reps = 500
#     apd_indices =[0]

#     if not readout_times:
#         readout_times = [10*10**3,
#                            20*10**3, 30*10**3, 40*10**3,
#                                   50*10**3, 100*10**3,500*10**3,
#                                   1*10**6, 2*10**6, 3*10**6, 4*10**6, 5*10**6,
#                                   6*10**6, 7*10**6, 8*10**6, 9*10**6, 1*10**7,
#                                  2*10**7,3*10**7,4*10**7,
#                                  5*10**7
#                                ]

#     # first index will be power, second will be time, third wil be individual points
#     nv0_count_raw = []
#     nvm_count_raw = []
#     nv0_counts_avg = []
#     nvm_counts_avg = []
#     snr_list = []

#     tool_belt.init_safe_stop()

#     for t in readout_times:
#         # Break out of the while if the user says stop
#         if tool_belt.safe_stop():
#             break

#         nv_sig_copy = copy.deepcopy(nv_sig)
#         nv_sig_copy['charge_readout_laser_filter'] = nd_filter
#         nv_sig_copy['charge_readout_dur'] = t
#         nv_sig_copy['charge_readout_laser_power'] = readout_yellow_power

#         nv0, nvm = measure(nv_sig_copy, apd_indices, num_reps)
#         nv0 = [int(el) for el in nv0]
#         nvm = [int(el) for el in nvm]
#         nv0_count_raw.append(nv0)
#         nvm_count_raw.append(nvm)

#         snr = tool_belt.calc_snr(nvm, nv0)
#         nv0_counts_avg.append(numpy.average(nv0))
#         nvm_counts_avg.append(numpy.average(nvm))
#         snr_list.append(snr)

#         timestamp = tool_belt.get_time_stamp()
#         raw_data = {'timestamp': timestamp,
#                 'nv_sig': nv_sig_copy,
#                 'nv_sig-units': tool_belt.get_nv_sig_units(),
#                 'num_runs':num_reps,
#                 'nv0': nv0,
#                 'nv0_list-units': 'counts',
#                 'nvm': nvm,
#                 'nvm-units': 'counts',
#                 }

#         #plot histogram of counts
#         fig_hist, ax = plt.subplots(1, 1)
#         max_0 = max(nv0)
#         max_m = max(nvm)
#         occur_0, x_vals_0 = numpy.histogram(nv0, numpy.linspace(0,max_0, max_0+1))
#         occur_m, x_vals_m = numpy.histogram(nvm, numpy.linspace(0,max_m, max_m+1))
#         ax.plot(x_vals_0[:-1],occur_0,  'r-o', label = 'Initial red pulse' )
#         ax.plot(x_vals_m[:-1],occur_m,  'g-o', label = 'Initial green pulse' )
#         ax.set_xlabel('Counts')
#         ax.set_ylabel('Occur.')
#         ax.set_title('{} ms readout, {}, {} V'.format(t/10**6, nd_filter, readout_yellow_power))
#         ax.legend()

#         file_path = tool_belt.get_file_path(__file__, timestamp, nv_sig['name'])
#         tool_belt.save_raw_data(raw_data, file_path)
#         tool_belt.save_figure(fig_hist, file_path + '_histogram')

#     title = '{}, {} V'.format( nd_filter, readout_yellow_power)
#     # plot average counts
#     readout_times = numpy.array(readout_times)

#     fig, axes = plt.subplots(1,2, figsize = (17, 8.5))
#     ax = axes[0]
#     ax.plot(readout_times / 10**3, nvm_counts_avg, 'ro',
#            label = 'Test green pulse')
#     ax.plot(readout_times / 10**3, nv0_counts_avg, 'ko',
#            label = 'Test red pulse')
#     ax.set_xlabel('Test pulse length (us)')
#     ax.set_ylabel('Counts (single shot measurement)')
#     ax.set_title(title)
#     ax.legend()

#     ax = axes[1]
#     ax.plot(readout_times / 10**3, snr_list, 'ro')
#     ax.set_xlabel('Test pulse length (us)')
#     ax.set_ylabel('SNR')
#     ax.set_title(title)

#     # then try to find optimum time based on readout time and SNR
#     max_tr = max(readout_times)
#     # print(max_tr)
#     SNR_tot = numpy.array(snr_list) * numpy.sqrt(max_tr/(readout_times + 6e6))
#     fig2, ax = plt.subplots(1,1)
#     ax.plot(readout_times / 10**3, SNR_tot, 'bo')
#     ax.set_xlabel('Test pulse length (us)')
#     ax.set_ylabel('SNR, scaled with sqrt(readout time/max readout time)')


#     raw_data = {'timestamp': timestamp,
#             'nv_sig': nv_sig,
#             'nv_sig-units': tool_belt.get_nv_sig_units(),
#             'readout_yellow_power': readout_yellow_power,
#             'nd_filter': nd_filter,
#             'num_runs':num_reps,
#             'readout_times': readout_times.tolist(),

#             'nv0_counts_avg': nv0_counts_avg,
#             'nv0_counts_avg-units': 'counts',
#             'nvm_counts_avg': nvm_counts_avg,
#             'nvm_counts_avg-units': 'counts',

#             'nv0_count_raw': nv0_count_raw,
#             'nv0_count_raw-units': 'counts',
#             'nvm_count_raw': nvm_count_raw,
#             'nvm_count_raw-units': 'counts',
#             'snr_list': snr_list,
#             'SNR_tot': SNR_tot.tolist()
#             }
#     tool_belt.save_raw_data(raw_data, file_path + '-duration_sweep')
#     tool_belt.save_figure(fig, file_path + '-snr')
#     tool_belt.save_figure(fig2, file_path + '-snr_scaled')
#     return

#%%
if __name__ == '__main__':
    # load the data here

    nd_yellow = "nd_0"
    green_power =8000
    nd_green = 'nd_0.4'
    red_power = 120
    sample_name = "rubin"
    green_laser = "integrated_520"
    yellow_laser = "laserglow_589"
    red_laser = "cobolt_638"

    nv_sig = {
            "coords":[-0.855, -0.591,  6.177],
        "name": "{}-nv1".format(sample_name,),
        "disable_opt":False,
        "ramp_voltages": False,
        "expected_count_rate":13.5,
        "correction_collar": 0.12,
        
        "imaging_laser":green_laser,
        "imaging_laser_power": None,
        "imaging_readout_dur": 1e7,
        
            'initialization_laser': green_laser, 'initialization_laser_power':None, 'initialization_laser_dur': 1e4,
            'nv-_prep_laser': green_laser, 'nv-_prep_laser_power': green_power, 'nv-_prep_laser_dur': 1e4,
            'nv0_prep_laser': red_laser, 'nv0_prep_laser_power': 0.58, 'nv0_prep_laser_dur': 1e4,
            'charge_readout_laser': yellow_laser, 'charge_readout_laser_filter': None,
            'charge_readout_laser_power': None, 'charge_readout_dur':None,
            'collection_filter': "715_sp+630_lp", 'magnet_angle': None,
            'resonance_LOW': 2.8012, 'rabi_LOW': 141.5, 'uwave_power_LOW': 15.5,  # 15.5 max
            'resonance_HIGH': 2.9445, 'rabi_HIGH': 191.9, 'uwave_power_HIGH': 14.5}   # 14.5 max


    # sweep_readout_dur(nv_sig, readout_yellow_power = 0.1,
    #                   nd_filter = 'nd_0.5')
    
    for n in [2]:
        determine_readout_dur(nv_sig, nv_sig, [1], readout_times = [100e6],
                                readout_yellow_powers = [ 0.15, 0.2],
                                # readout_yellow_powers = [0.56],
                          nd_filter = 'nd_1.0',
                          num_pulses = n)
        



# Replotting

    file_name = '2022_08_08-11_52_58-rubin-nv1histogram'
    folder = 'pc_rabi/branch_master/determine_charge_readout_dur/2022_08'
    data = tool_belt.get_raw_data(file_name, folder)
    nv_sig = data["nv_sig"]
    readout_time = nv_sig["charge_readout_dur"]
    nd_filter = nv_sig["charge_readout_laser_filter"]
    aom_power = nv_sig["charge_readout_laser_power"]
    nv0_array = numpy.array(data["nv0"])
    nvm_array = numpy.array(data["nvm"])
    
    max_0 = max(nv0_array)
    max_m = max(nvm_array)
    occur_0, x_vals_0 = numpy.histogram(nv0_array, numpy.linspace(0,max_0, max_0+1))
    occur_m, x_vals_m = numpy.histogram(nvm_array, numpy.linspace(0,max_m, max_m+1))
    
    mu_0 = numpy.mean(nv0_array)
    mu_1 = numpy.mean(nvm_array)
    # print(mu_1)
    # calculate_threshold_plot(readout_time/10**6,nv0_array,nvm_array, nd_filter, aom_power)
    # threshold, fidelity, fig = calculate_threshold_plot_no_model(occur_0, 
    #                                       occur_m,mu_0, mu_1,x_vals_0, x_vals_m , nd_filter, aom_power)
    
