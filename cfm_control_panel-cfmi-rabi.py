# -*- coding: utf-8 -*-
"""
This file contains functions to control the CFM. Just change the function call
in the main section at the bottom of this file and run the file. Shared or
frequently changed parameters are in the __main__ body and relatively static
parameters are in the function definitions.

Created on Sun Nov 25 14:00:28 2018

@author: mccambria
"""


# %% Imports


import labrad
import numpy
import time
import copy
import utils.tool_belt as tool_belt
import matplotlib.pyplot as plt
import majorroutines.image_sample as image_sample
import majorroutines.image_sample_xz as image_sample_xz
import chargeroutines.image_sample_charge_state_compare as image_sample_charge_state_compare
import majorroutines.optimize as optimize
import majorroutines.stationary_count as stationary_count
import majorroutines.resonance as resonance
import majorroutines.pulsed_resonance as pulsed_resonance
import majorroutines.optimize_magnet_angle as optimize_magnet_angle
import majorroutines.rabi as rabi
import majorroutines.discrete_rabi as discrete_rabi
import majorroutines.g2_measurement as g2_measurement
import majorroutines.ramsey as ramsey
import majorroutines.t1_dq_main as t1_dq_main
import majorroutines.spin_echo as spin_echo
import majorroutines.dynamical_decoupling_cpmg as dynamical_decoupling_cpmg
import majorroutines.dynamical_decoupling_xy4 as dynamical_decoupling_xy4
import majorroutines.dynamical_decoupling_xy8 as dynamical_decoupling_xy8
import majorroutines.lifetime_v2 as lifetime_v2
import minorroutines.time_resolved_readout as time_resolved_readout
import chargeroutines.SPaCE as SPaCE
import chargeroutines.SPaCE_simplified as SPaCE_simplified
import chargeroutines.scc_pulsed_resonance as scc_pulsed_resonance
import chargeroutines.scc_spin_echo as scc_spin_echo
import minorroutines.determine_standard_readout_params as determine_standard_readout_params
import chargeroutines.super_resolution_pulsed_resonance as super_resolution_pulsed_resonance
import chargeroutines.super_resolution_ramsey as super_resolution_ramsey
import chargeroutines.super_resolution_spin_echo as super_resolution_spin_echo
import chargeroutines.g2_measurement as g2_SCC_branch
import chargeroutines.determine_charge_readout_params as determine_charge_readout_params

# import majorroutines.set_drift_from_reference_image as set_drift_from_reference_image
import debug.test_major_routines as test_major_routines
from utils.tool_belt import States
import time


# %% Major Routines


def do_image_sample(nv_sig, apd_indices):

    # scan_range = 0.5
    # num_steps = 90
    # num_steps = 120
    #
    # scan_range = 0.15
    # num_steps = 60
    #
    # scan_range = 0.75
    # num_steps = 150

    # scan_range = 2
    # num_steps = 160
    # scan_range =.5
    # num_steps = 90
    # scan_range = 0.5
    # num_steps = 120
    # scan_range = 0.05
    # num_steps = 60
    # 80 um / V
    #
    # scan_range = 5.0
    # scan_range = 3
    # scan_range = 1
    # scan_range =4
    # scan_range = 2
    # scan_range = 0.5
    # scan_range = 0.35
    # scan_range = 0.25
    # scan_range = 0.2
    # scan_range = 0.15
    # scan_range = 0.1
    scan_range = 0.05
    # scan_range = 0.025
    # scan_range = 0.012

    #num_steps = 400
    # num_steps = 300
    # num_steps = 200
    # num_steps = 160
    # num_steps = 135
    # num_steps =120
    # num_steps = 90
    # num_steps = 60
    num_steps = 31
    # num_steps = 21

    #individual line pairs:
    # scan_range = 0.16
    # num_steps = 160

    #both line pair sets:
    # scan_range = 0.35
    # num_steps = 160


    # For now we only support square scans so pass scan_range twice
    ret_vals = image_sample.main(nv_sig, scan_range, scan_range, num_steps, apd_indices)
    img_array, x_voltages, y_voltages = ret_vals

    return img_array, x_voltages, y_voltages


def do_subtract_filter_image(nv_sig, apd_indices):
    scan_range = 0.2
    num_steps = 90

    nv_sig['collection_filter'] = "715_lp"
    img_array_siv, x_voltages, y_voltages = image_sample.main(nv_sig, scan_range,
                                          scan_range, num_steps, apd_indices)

    nv_sig['collection_filter'] = "715_sp+630_lp"
    img_array_nv, x_voltages, y_voltages = image_sample.main(nv_sig, scan_range,
                                         scan_range, num_steps, apd_indices)

    img_array_sub = img_array_siv - img_array_nv

    x_num_steps = len(x_voltages)
    x_low = x_voltages[0]
    x_high = x_voltages[x_num_steps-1]
    y_num_steps = len(y_voltages)
    y_low = y_voltages[0]
    y_high = y_voltages[y_num_steps-1]

    pixel_size = x_voltages[1] - x_voltages[0]
    half_pixel_size = pixel_size / 2

    readout = nv_sig['imaging_readout_dur']
    readout_sec = readout / 10**9
    img_array_kcps = numpy.copy(img_array_sub)
    img_array_kcps[:] = (img_array_sub[:] / 1000) / readout_sec

    img_extent = [x_high + half_pixel_size, x_low - half_pixel_size,
                  y_low - half_pixel_size, y_high + half_pixel_size]

    title = 'SiV filter images - NV filter image'
    fig = tool_belt.create_image_figure(img_array_kcps, img_extent,
                    clickHandler=image_sample.on_click_image, color_bar_label='kcps',
                    title=title)

    time.sleep(1)
    timestamp = tool_belt.get_time_stamp()
    filePath = tool_belt.get_file_path('image_sample.py', timestamp, nv_sig['name'])
    tool_belt.save_figure(fig, filePath)

    return

def do_image_sample_xz(nv_sig, apd_indices):

    scan_range_x = .25
# z code range 3 to 7 if centered at 5
    scan_range_z =2
    num_steps = 60

    image_sample_xz.main(
        nv_sig,
        scan_range_x,
        scan_range_z,
        num_steps,
        apd_indices,
        um_scaled=False,
    )


def do_image_charge_states(nv_sig, apd_indices):

    scan_range = 0.01

    num_steps = 31
    num_reps= 10

    image_sample_charge_state_compare.main(
        nv_sig, scan_range, scan_range, num_steps,num_reps, apd_indices
    )


def do_optimize(nv_sig, apd_indices):

    optimize.main(
        nv_sig,
        apd_indices,
        set_to_opti_coords=False,
        save_data=True,
        plot_data=True,
    )


def do_optimize_list(nv_sig_list, apd_indices):

    optimize.optimize_list(nv_sig_list, apd_indices)


def do_opti_z(nv_sig_list, apd_indices):

    optimize.opti_z(
        nv_sig_list,
        apd_indices,
        set_to_opti_coords=False,
        save_data=True,
        plot_data=True,
    )


def do_stationary_count(nv_sig, apd_indices):

    run_time = 1 * 60 * 10 ** 9  # ns

    stationary_count.main(nv_sig, run_time, apd_indices)


def do_g2_measurement(nv_sig, apd_a_index, apd_b_index):

    run_time = 3*60  # s
    diff_window =120# ns

    # g2_measurement.main(
    g2_SCC_branch.main(
        nv_sig, run_time, diff_window, apd_a_index, apd_b_index
    )


def do_resonance(nv_sig, opti_nv_sig,apd_indices, freq_center=2.87, freq_range=0.2):

    num_steps = 11#101
    num_runs = 2#15
    uwave_power = -10.0

    resonance.main(
        nv_sig,
        apd_indices,
        freq_center,
        freq_range,
        num_steps,
        num_runs,
        uwave_power,
        state=States.HIGH,
        opti_nv_sig = opti_nv_sig
    )


def do_resonance_state(nv_sig, opti_nv_sig, apd_indices, state):

    freq_center = nv_sig["resonance_{}".format(state.name)]
    uwave_power = 10.0

    freq_range = 0.15
    num_steps = 51
    num_runs = 10

    # Zoom
    # freq_range = 0.060
    # num_steps = 51
    # num_runs = 10

    resonance.main(
        nv_sig,
        apd_indices,
        freq_center,
        freq_range,
        num_steps,
        num_runs,
        uwave_power,
        opti_nv_sig = opti_nv_sig
    )


def do_pulsed_resonance(nv_sig, opti_nv_sig, apd_indices, freq_center=2.87, freq_range=0.2):

    num_steps =101
    num_reps = 1e4
    num_runs = 15
    uwave_power = 10
    uwave_pulse_dur = int(45)

    pulsed_resonance.main(
        nv_sig,
        apd_indices,
        freq_center,
        freq_range,
        num_steps,
        num_reps,
        num_runs,
        uwave_power,
        uwave_pulse_dur,
        state=States.HIGH,
        opti_nv_sig = opti_nv_sig
    )


def do_pulsed_resonance_state(nv_sig, opti_nv_sig,apd_indices, state):

    # freq_range = 0.150
    # num_steps = 51
    # num_reps = 10**4
    # num_runs = 8

    # Zoom
    freq_range = 0.12
    # freq_range = 0.120
    num_steps = 51
    num_reps = int(1e4)
    num_runs = 5

    composite = False

    res, _ = pulsed_resonance.state(
        nv_sig,
        apd_indices,
        state,
        freq_range,
        num_steps,
        num_reps,
        num_runs,
        composite,
        opti_nv_sig = opti_nv_sig
    )
    nv_sig["resonance_{}".format(state.name)] = res


def do_optimize_magnet_angle(nv_sig, apd_indices):

    # angle_range = [132, 147]
    #    angle_range = [315, 330]
    num_angle_steps = 6
    #    freq_center = 2.7921
    #    freq_range = 0.060
    angle_range = [0, 150]
    #    num_angle_steps = 6
    freq_center = 2.87
    freq_range = 0.6
    num_freq_steps = 121
    num_freq_runs = 25

    # Pulsed
    uwave_power = 10#14.5
    uwave_pulse_dur = 80/2
    num_freq_reps = int(1e4)

    # CW
    #uwave_power = -10.0
    #uwave_pulse_dur = None
    #num_freq_reps = None

    optimize_magnet_angle.main(
        nv_sig,
        apd_indices,
        angle_range,
        num_angle_steps,
        freq_center,
        freq_range,
        num_freq_steps,
        num_freq_reps,
        num_freq_runs,
        uwave_power,
        uwave_pulse_dur,
    )


def do_rabi(nv_sig, opti_nv_sig, apd_indices, state, 
            uwave_time_range=[0, 200]):

    num_steps = 51
    num_reps = int(2e4)
    num_runs = 5

    period = rabi.main(
        nv_sig,
        apd_indices,
        uwave_time_range,
        state,
        num_steps,
        num_reps,
        num_runs,
        iq_mod_on = False,
        opti_nv_sig = opti_nv_sig
    )
    nv_sig["rabi_{}".format(state.name)] = period



def do_discrete_rabi(nv_sig, apd_indices, state, max_num_pi_pulses=5):

    num_reps = 2e4
    # num_runs = 2
    num_runs = 10

    discrete_rabi.main(
        nv_sig, apd_indices, state, max_num_pi_pulses, num_reps, num_runs
    )
    
    # discrete_rabi.main(
    #     nv_sig, apd_indices, state, max_num_pi_pulses, num_reps, num_runs,
    #     iq_delay = 515
    # )

    # for iq_delay in numpy.linspace(298, 732, 15): #448
    # for iq_delay in [450, 485, 515, 545, 580, 608, 645, 680]:
    # # t = 680+35
    # # for iq_delay in numpy.linspace(t-5, t+5, 3):
    #     print(iq_delay)
    #     discrete_rabi.main(nv_sig, apd_indices,
    #                         state, max_num_pi_pulses, num_reps, num_runs, iq_delay)



def do_lifetime(nv_sig, apd_indices):

    # num_reps = 2e4 # SM
    num_reps = 2e4 # SM
    num_bins = 201
    # num_runs = 500
    num_runs = 10
    readout_time_range = [0.95e3, 1.15e3]  # ns
    polarization_time = 1e3 # ns

    lifetime_v2.main(
        nv_sig, 
        apd_indices, 
        readout_time_range,
        num_reps, 
        num_runs, 
        num_bins, 
        polarization_time )



def do_ramsey(nv_sig, opti_nv_sig, apd_indices):

    detuning = 6  # MHz
    precession_time_range = [0, 2 * 10 ** 3]
    num_steps = 101
    num_reps = int( 10 ** 4)
    num_runs = 20

    ramsey.main(
        nv_sig,
        apd_indices,
        detuning,
        precession_time_range,
        num_steps,
        num_reps,
        num_runs,
        opti_nv_sig = opti_nv_sig
    )


def do_spin_echo(nv_sig, apd_indices, state = States.HIGH):

    # T2* in nanodiamond NVs is just a couple us at 300 K
    # In bulk it's more like 100 us at 300 K
    max_time = 30  # us
    num_steps = int(max_time/1+ 1)  # 1 point per 1 us
    precession_time_range = [0, max_time*10**3]

    # revival_time= 9.934e3
    # num_steps = 25
    # precession_time_range = [0, revival_time*(num_steps - 1)]

    num_reps = 1e4
    num_runs =30

    #    num_steps = 151
    #    precession_time_range = [0, 10*10**3]
    #    num_reps = int(10.0 * 10**4)
    #    num_runs = 6




    angle = spin_echo.main(
        nv_sig,
        apd_indices,
        precession_time_range,
        num_steps,
        num_reps,
        num_runs,
        state,
    )
    return angle

def do_dd_cpmg(nv_sig, apd_indices, pi_pulse_reps, T=None):
    # T = 100
    
    if T:
        max_time = T / (2*pi_pulse_reps)  # us
        min_time =0# 1 / (2*pi_pulse_reps) #us
        num_steps = int(T/2+1 )  # 1 point per 2 us
        precession_time_range = [int(min_time*10**3), int(max_time*10**3)]
    
    else:
        revival_time= nv_sig['t2_revival_time']
        num_revivals = 10
        precession_time_range = [0, revival_time*(num_revivals - 1)]
        num_steps=num_revivals

    # num_xy4_reps = 1
    num_reps = 1e4 #1e3
    num_runs =30


    state = States.HIGH



    dynamical_decoupling_cpmg.main(
        nv_sig,
        apd_indices,
        precession_time_range,
        pi_pulse_reps,
        num_steps,
        num_reps,
        num_runs,
        state,
    )
    return 


def do_dd_xy4(nv_sig, apd_indices, num_xy4_reps, step_size, shift, T_min, T_max):

    #step_size = 1 # us
    #shift = 100 #ns
    #T_min = 0
    #T_max = 200
    
    # max_time = T_max / (2*4*num_xy4_reps)  # us
    # min_time = T_min / (2*4*num_xy4_reps) #us
    
    
    #step_size = 2 # us
    #shift = 0 #ns
    #T_min = 350-50
    #T_max = 350+50
    
    max_time = T_max / (2*4*num_xy4_reps)  # us
    min_time = T_min / (2*4*num_xy4_reps) #us
    
    # # revival_time= nv_sig['t2_revival_time']
    # # T_min = (revival_time/1e3 - 3)*(2*4*num_xy4_reps) 
    # # T_max = (revival_time/1e3 + 3)*(2*4*num_xy4_reps)
    
    num_steps = int((T_max - T_min) / step_size ) + 1   # 1 point per 1 us
    # min_time =0.0# 1 / (2*pi_pulse_reps) #us
    # num_steps = int(T/1+1 )  # 1 point per 1 us
    precession_time_range = [int(min_time*10**3+shift), int(max_time*10**3+shift)]
    
    #conventional readout
    num_reps = 1e4
    num_runs= 50
    
    # # scc readout
    # num_reps = 4 #should optimize every 10 min
    # num_runs= 3750

    state = States.HIGH



    dynamical_decoupling_xy4.main(
        nv_sig,
        apd_indices,
        precession_time_range,
        num_xy4_reps,
        num_steps,
        num_reps,
        num_runs,
        state=state,
        scc_readout=False,
    )
    return 

def do_dd_xy4_revivals(nv_sig, apd_indices, num_xy4_reps):

    revival_time= nv_sig['t2_revival_time']
    num_revivals = 6
    precession_time_range = [0, revival_time*(num_revivals - 1)]
    #num_steps= int(num_revivals * 2 - 1)
    
    dt = 5e3 #us
    dt_xy4 = dt/(2*4*num_xy4_reps)
    taus = [0, dt_xy4]
    for ind in range(num_revivals-1):
        # print(ind)
        i = ind+1
        t0 = revival_time*(i-0.5)
        t1 = revival_time*i - dt_xy4
        t2 = revival_time*i
        t3 = revival_time*i + dt_xy4
        taus = taus + [t0, t1, t2, t3]
    
    i = num_revivals
    t0 = revival_time*(i-0.5)
    t1 = revival_time*i - dt_xy4
    t2 = revival_time*i
    taus = taus + [t0, t1, t2]
    # print(taus)
    
    taus = numpy.array(taus)
    num_steps=len(taus)
    # taus = numpy.linspace(
    #     precession_time_range[0],
    #     precession_time_range[1],
    #     num=num_steps,
    #     dtype=numpy.int32,
    # )
    # taus[0] = 500

    # num_xy4_reps = 1
    num_reps = 1e4
    num_runs= 75





    dynamical_decoupling_xy4.main(
        nv_sig,
        apd_indices,
        precession_time_range,
        num_xy4_reps,
        num_steps,
        num_reps,
        num_runs,
        taus = taus,
        state = States.HIGH,
    )
    return 

def do_dd_xy8(nv_sig, apd_indices, num_xy8_reps):

    step_size = 0.02 # us
    shift = 100 #ns
    T_min = 0
    T_max = 2
    
    max_time = T_max #/ (2*8*num_xy8_reps)  # us
    min_time = T_min #/ (2*8*num_xy8_reps) #us
    
    num_steps = int((T_max - T_min) / step_size ) + 1   # 1 point per 1 us
    # min_time =0.0# 1 / (2*pi_pulse_reps) #us
    # num_steps = int(T/1+1 )  # 1 point per 1 us
    precession_time_range = [int(min_time*10**3+shift), int(max_time*10**3+shift)]
    
    num_reps = 1e4
    num_runs= 75


    state = States.HIGH



    dynamical_decoupling_xy8.main(
        nv_sig,
        apd_indices,
        precession_time_range,
        num_xy8_reps,
        num_steps,
        num_reps,
        num_runs,
        state,
    )
    return 

def do_relaxation(nv_sig, apd_indices, ):
    min_tau = 0
    max_tau_omega = 0.7e6#20e6
    max_tau_gamma = 0.4e6# 8e6
    num_steps_omega = 21
    num_steps_gamma = 21
    num_reps = 2000
    num_runs = 200
    
    if False:
     t1_exp_array = numpy.array(
        [[
                [States.ZERO, States.ZERO],
                [min_tau, max_tau_omega],
                num_steps_omega,
                num_reps,
                num_runs,
            ],
        # [
        #         [States.ZERO, States.HIGH],
        #         [min_tau, max_tau_omega],
        #         num_steps_omega,
        #         num_reps,
        #         num_runs,
        #     ],
             
             ])
    if True:
     t1_exp_array = numpy.array(
        [ [
                [States.ZERO, States.ZERO],
                [min_tau, max_tau_omega],
                num_steps_omega,
                num_reps,
                num_runs,
            ],
        [
                [States.ZERO, States.HIGH],
                [min_tau, max_tau_omega],
                num_steps_omega,
                num_reps,
                num_runs,
            ],
                [
                [States.HIGH, States.HIGH],
                [min_tau, max_tau_gamma],
                num_steps_gamma,
                num_reps,
                num_runs,
            ],
                    [
                [States.HIGH, States.LOW],
                [min_tau, max_tau_gamma],
                num_steps_gamma,
                num_reps,
        #        num_runs,
            ]] )

    t1_dq_main.main(
            nv_sig,
            apd_indices,
            t1_exp_array,
            num_runs,
            composite_pulses=False,
            scc_readout=False,
        )

def do_determine_standard_readout_params(nv_sig, apd_indices):
    
    num_reps = 7e5
    max_readouts = [1e3]
    state = States.LOW
    
    determine_standard_readout_params.main(nv_sig, apd_indices, num_reps, 
                                           max_readouts, state=state)
    
def do_determine_charge_readout_params(nv_sig, apd_indices):
        opti_nv_sig = nv_sig
        num_reps = 100
        readout_durs = [50e6]
        readout_durs = [int(el) for el in readout_durs]
        max_readout_dur = max(readout_durs)
        readout_powers = [0.2]
        
            
        determine_charge_readout_params.determine_readout_dur_power(  
          nv_sig,
          opti_nv_sig,
          apd_indices,
          num_reps,
          max_readout_dur=max_readout_dur,
          readout_powers=readout_powers,
          plot_readout_durs=readout_durs,
          fit_threshold_full_model= False,)
        
def do_time_resolved_readout(nv_sig, apd_indices):

    # nv_sig uses the initialization key for the first pulse
    # and the imaging key for the second

    num_reps = 1000
    num_bins = 2001
    num_runs = 20
    # disp = 0.0001#.05

    bin_centers, binned_samples_sig = time_resolved_readout.main(
        nv_sig,
        apd_indices,
        num_reps,
        num_runs,
        num_bins
    )
    return bin_centers, binned_samples_sig

def do_time_resolved_readout_three_pulses(nv_sig, apd_indices):

    # nv_sig uses the initialization key for the first pulse
    # and the imaging key for the second

    num_reps = 1000
    num_bins = 2001
    num_runs = 20


    bin_centers, binned_samples_sig = time_resolved_readout.main_three_pulses(
        nv_sig,
        apd_indices,
        num_reps,
        num_runs,
        num_bins
    )

    return bin_centers, binned_samples_sig



def do_SPaCE(nv_sig, opti_nv_sig, apd_indices,num_runs, num_steps_a, num_steps_b,
               img_range_1D, img_range_2D, offset, charge_state_threshold = None):
    # dr = 0.025 / numpy.sqrt(2)
    # img_range = [[-dr,-dr],[dr, dr]] #[[x1, y1], [x2, y2]]
    # num_steps = 101
    # num_runs = 50
    # measurement_type = "1D"

    # img_range = 0.075
    # num_steps = 71
    # num_runs = 1
    # measurement_type = "2D"

    # dz = 0
    SPaCE.main(nv_sig, opti_nv_sig, apd_indices,num_runs, num_steps_a, num_steps_b,
               charge_state_threshold, img_range_1D, img_range_2D, offset )


def do_SPaCE_simplified(nv_sig, source_coords, apd_indices):

    # pulse_durs = numpy.linspace(0,0.7e9, 3)
    # pulse_durs = numpy.linspace(0,1.5e9, 30)
    # pulse_durs = numpy.linspace(1e2,1e9, 5)
    # pulse_durs = numpy.array([0,  0.1, ])*1e9
    pulse_powers = numpy.array([0, 0.565])
    pulse_durs= None

    num_reps =int(100)

    SPaCE_simplified.main(nv_sig, source_coords, num_reps, apd_indices,
         pulse_durs, pulse_powers)

def do_SPaCE_simplified_time_resolved_readout(nv_sig, source_coords, apd_indices):

    num_reps =int(1000)
    num_runs = 10
    num_bins = 52
    bin_centers, binned_samples_sig = SPaCE_simplified.main_time_resolved_readout(nv_sig, source_coords,
                                                num_reps, num_runs,num_bins,apd_indices)
    return bin_centers, binned_samples_sig

def do_SPaCE_simplified_scan_init(nv_sig, source_coords_list, init_scan_range,
                                  init_scan_steps, num_runs, apd_indices):



    SPaCE_simplified.main_scan_init(nv_sig, source_coords_list, init_scan_range, init_scan_steps,
                   num_runs,  apd_indices)


def do_scc_resonance(nv_sig, opti_nv_sig, apd_indices, state=States.LOW):
    freq_center = nv_sig['resonance_{}'.format(state.name)]
    uwave_power = nv_sig['uwave_power_{}'.format(state.name)]
    uwave_pulse_dur = nv_sig['rabi_{}'.format(state.name)]/2

    freq_range = 0.05
    num_steps = 51
    num_reps = int(10**3)
    num_runs = 30

    scc_pulsed_resonance.main(nv_sig, opti_nv_sig, apd_indices, freq_center, freq_range,
         num_steps, num_reps, num_runs, uwave_power, uwave_pulse_dur, state )

def do_scc_spin_echo(nv_sig, opti_nv_sig, apd_indices, tau_start, tau_stop, state=States.LOW):
    step_size = 1 # us
    num_steps = int((tau_stop - tau_start)/step_size + 1)

    precession_time_range = [tau_start *1e3, tau_stop *1e3]

    num_reps = int(10**3)
    num_runs = 40

    scc_spin_echo.main(nv_sig, opti_nv_sig, apd_indices, precession_time_range,
         num_steps, num_reps, num_runs,
         state )



def do_super_resolution_resonance(nv_sig, opti_nv_sig, apd_indices, state=States.LOW):
    freq_center = nv_sig['resonance_{}'.format(state.name)]
    uwave_power = nv_sig['uwave_power_{}'.format(state.name)]
    uwave_pulse_dur = nv_sig['rabi_{}'.format(state.name)]/2

    freq_range = 0.05
    num_steps = 51
    num_reps = int(10**3)
    num_runs = 30

    super_resolution_pulsed_resonance.main(nv_sig, opti_nv_sig, apd_indices, freq_center, freq_range,
         num_steps, num_reps, num_runs, uwave_power, uwave_pulse_dur, state )

def do_super_resolution_ramsey(nv_sig, opti_nv_sig, apd_indices,
                                  tau_start, tau_stop, state=States.LOW):

    detuning = 5  # MHz

    # step_size = 0.05 # us
    # num_steps = int((tau_stop - tau_start)/step_size + 1)
    num_steps = 101
    precession_time_range = [tau_start *1e3, tau_stop *1e3]


    num_reps = int(10**3)
    num_runs = 30

    super_resolution_ramsey.main(nv_sig, opti_nv_sig, apd_indices,
                                    precession_time_range, detuning,
         num_steps, num_reps, num_runs, state )

def do_super_resolution_spin_echo(nv_sig, opti_nv_sig, apd_indices,
                                  tau_start, tau_stop, state=States.LOW):
    step_size = 1 # us
    num_steps = int((tau_stop - tau_start)/step_size + 1)
    print(num_steps)
    precession_time_range = [tau_start *1e3, tau_stop *1e3]


    num_reps = int(10**3)
    num_runs = 20

    super_resolution_spin_echo.main(nv_sig, opti_nv_sig, apd_indices,
                                    precession_time_range,
         num_steps, num_reps, num_runs, state )

def do_sample_nvs(nv_sig_list, apd_indices):

    # g2 parameters
    run_time = 60 * 5
    diff_window = 150

    # PESR parameters
    num_steps = 101
    num_reps = 10 ** 5
    num_runs = 3
    uwave_power = 9.0
    uwave_pulse_dur = 100

    g2 = g2_measurement.main_with_cxn
    pesr = pulsed_resonance.main_with_cxn

    with labrad.connect() as cxn:
        for nv_sig in nv_sig_list:
            g2_zero = g2(
                cxn,
                nv_sig,
                run_time,
                diff_window,
                apd_indices[0],
                apd_indices[1],
            )
            if g2_zero < 0.5:
                pesr(
                    cxn,
                    nv_sig,
                    apd_indices,
                    2.87,
                    0.1,
                    num_steps,
                    num_reps,
                    num_runs,
                    uwave_power,
                    uwave_pulse_dur,
                )


def do_test_major_routines(nv_sig, apd_indices):
    """Run this whenver you make a significant code change. It'll make sure
    you didn't break anything in the major routines.
    """

    test_major_routines.main(nv_sig, apd_indices)


# %% Run the file


if __name__ == "__main__":

    # In debug mode, don't bother sending email notifications about exceptions
    debug_mode = True
    

    # %% Shared parameters

    # apd_indices = [0]
    apd_indices = [1]
    # apd_indices = [0,1]

    nd_yellow = "nd_0"
    green_power =8000
    nd_green = 'nd_0.4'
    red_power = 120
    sample_name = "rubin"
    green_laser = "integrated_520"
    yellow_laser = "laserglow_589"
    red_laser = "cobolt_638"


    sig_base = {
        "disable_opt":False,
        "ramp_voltages": False,
        "correction_collar": 0.12,

        "spin_laser":green_laser,
        "spin_laser_power": green_power,
        "spin_laser_filter": nd_green,
        "spin_readout_dur": 350,
        "spin_pol_dur": 1000.0,

        "imaging_laser":green_laser,
        "imaging_laser_power": green_power,
        "imaging_laser_filter": nd_green,
        "imaging_readout_dur": 1e7,

        "initialize_laser": green_laser,
        "initialize_laser_power": green_power,
        "initialize_laser_dur":  1e3,
        "CPG_laser": green_laser,
        "CPG_laser_power":red_power,
        "CPG_laser_dur": int(1e6),

        "nv-_prep_laser": green_laser,
        "nv-_prep_laser-power": None,
        "nv-_prep_laser_dur": 1e3,
        "nv0_prep_laser": red_laser,
        "nv0_prep_laser-power": None,
        "nv0_prep_laser_dur": 1e3,
        
        "nv-_reionization_laser": green_laser,
        "nv-_reionization_laser_power": green_power,
        "nv-_reionization_dur": 1e3,
        
        "nv0_ionization_laser": red_laser,
        "nv0_ionization_laser_power": None,
        "nv0_ionization_dur": 300,
        
        "spin_shelf_laser": yellow_laser,
        "spin_shelf_laser_power": None,
        "spin_shelf_dur": 0,
        
        "charge_readout_laser": yellow_laser,
        "charge_readout_laser_power": 0.15, 
        "charge_readout_laser_filter": "nd_1.0",
        "charge_readout_dur": 200e6, 

        "collection_filter": "715_sp+630_lp", # NV band only
        "magnet_angle":  157,
        "uwave_power_LOW": 15,  
        "uwave_power_HIGH": 10,
    } 


    nv_sig_1 = copy.deepcopy(sig_base)
    nv_sig_1["coords"] = [0.126, -0.455, 5.484]
    nv_sig_1["name"] = "{}-nv1_2022_08_10".format(sample_name,)
    nv_sig_1["expected_count_rate"] = 11
    nv_sig_1["resonance_LOW"] = 2.5512
    nv_sig_1["rabi_LOW"] = 118.6
    nv_sig_1["resonance_HIGH"] = 3.1916
    nv_sig_1["rabi_HIGH"] =102.3
    nv_sig_1["t2_revival_time"] = 8.352e3

    nv_sig_4 = copy.deepcopy(sig_base)
    nv_sig_4["coords"] = [nv_sig_1["coords"][0] + 0.031, 
                          nv_sig_1["coords"][1] - 0.005,
                          nv_sig_1["coords"][2]]
    nv_sig_4["name"] = "{}-nv4_2022_08_10".format(sample_name,)
    nv_sig_4["expected_count_rate"] = 10
    nv_sig_4["resonance_LOW"] =2.5512
    nv_sig_4["rabi_LOW"] = 118.6
    nv_sig_4["resonance_HIGH"] = 3.1916
    nv_sig_4["rabi_HIGH"] =102.3
    nv_sig_4["t2_revival_time"] = 10.945e3

    nv_sig_5 = copy.deepcopy(sig_base)
    nv_sig_5["coords"] =  [nv_sig_1["coords"][0] + 0.023, 
                          nv_sig_1["coords"][1] -0.015,
                          nv_sig_1["coords"][2]]
    nv_sig_5["name"] = "{}-nv5_2022_08_10".format(sample_name,)
    nv_sig_5["expected_count_rate"] = 15
    nv_sig_5["resonance_LOW"] = 2.5512
    nv_sig_5["rabi_LOW"] = 118.6
    nv_sig_5["resonance_HIGH"] = 3.1916
    nv_sig_5["rabi_HIGH"] = 102.3
    nv_sig_5["t2_revival_time"] = 10.945e3

    nv_sig_8 = copy.deepcopy(sig_base)
    nv_sig_8["coords"] = [nv_sig_1["coords"][0] -0.038, 
                          nv_sig_1["coords"][1] -0.026,
                          nv_sig_1["coords"][2]]
    nv_sig_8["name"] = "{}-nv8_2022_08_10".format(sample_name,)
    nv_sig_8["expected_count_rate"] = 11
    nv_sig_8["resonance_LOW"] =  2.5512
    nv_sig_8["rabi_LOW"] = 118.6
    nv_sig_8["resonance_HIGH"] = 3.1916
    nv_sig_8["rabi_HIGH"] = 102.3
    nv_sig_8["t2_revival_time"] = 10.945e3

    nv_sig_10 = copy.deepcopy(sig_base)
    nv_sig_10["coords"] = [nv_sig_1["coords"][0] -0.050, 
                          nv_sig_1["coords"][1] -0.008,
                          nv_sig_1["coords"][2]]
    nv_sig_10["name"] = "{}-nv10_2022_08_10".format(sample_name,)
    nv_sig_10["expected_count_rate"] = 12
    nv_sig_10["resonance_LOW"] = 2.5512
    nv_sig_10["rabi_LOW"] = 118.6
    nv_sig_10["resonance_HIGH"] = 3.1916
    nv_sig_10["rabi_HIGH"] = 102.3
    nv_sig_10["t2_revival_time"] =10.945e3


    nv_sig_none = copy.deepcopy(sig_base)
    nv_sig_none["coords"] = [0.115, -0.472,
                          nv_sig_1["coords"][2]]
    nv_sig_none["name"] = "{}-no_nv".format(sample_name,)
    nv_sig_none["disable_opt"] = True
    nv_sig_none['collection_filter'] = 'no_filter'



    nv_sig = nv_sig_1


    # %% Functions to run
#
    try:
        # print(nv_sig['coords'])
        #tool_belt.init_safe_stop()
        # for dz in [0, 0.15,0.3, 0.45, 0.6, 0.75,0.9, 1.05, 1.2, 1.5, 1.7, 1.85, 2, 2.15, 2.3, 2.45]: #0.5,0.4, 0.3, 0.2, 0.1,0, -0.1,-0.2,-0.3, -0.4, -0.5
            # nv_sig_copy = copy.deepcopy(nv_sig)
            # coords = nv_sig["coords"]
            # new_coords= list(numpy.array(coords)+ numpy.array([0, 0, dz]))
            # # new_coords = numpy.array(coords) +[0, 0, dz]
            # # print(new_coords)
            # nv_sig_copy['coords'] = new_coords
            # do_image_sample(nv_sig_copy, apd_indices)
         #
        #
        # tool_belt.set_drift([0.0, 0.0, tool_belt.get_drift()[2]])  # Keep z
        # tool_belt.set_drift([0.0, 0.0, 0.0])
        # tool_belt.set_xyz(labrad.connect(), [0,0,5])
        
        # if True:
        if False:
            
            for nv_sig in [nv_sig_1, nv_sig_4, nv_sig_5, nv_sig_8, nv_sig_10]:
                
                do_optimize(nv_sig,apd_indices)
    
                # do_image_sample(nv_sig, apd_indices)
                     
                # do_pulsed_resonance_state(nv_sig, nv_sig,apd_indices, States.LOW)
                # do_pulsed_resonance_state(nv_sig, nv_sig,apd_indices, States.HIGH)
                # do_rabi(nv_sig, nv_sig, apd_indices, States.LOW, uwave_time_range=[0, 100])
                # do_rabi(nv_sig, nv_sig, apd_indices, States.HIGH, uwave_time_range=[0, 100])
                
        # do_optimize(nv_sig,apd_indices)
        # do_image_sample(nv_sig, apd_indices)
                
        # do_stationary_count(nv_sig, apd_indices)


        # do_image_sample_xz(nv_sig, apd_indices)
        # do_image_charge_states(nv_sig, apd_indices)


        # do_subtract_filter_image(nv_sig, apd_indices)
        # nv_sig["collection_filter"] = "740_bp"
        # do_image_sample(nv_sig, apd_indices)
        # do_g2_measurement(nv_sig, 0, 1)

        # num_runs = 20
        # num_steps_a = 81
        # num_steps_b = num_steps_a
        # img_range_1D = None#[[0.042, 0, 0],[0,0,0]]

        # img_range_2D = [0.1, 0.1, 0]
        # offset = [-0.22/83,0.25/83,0]
        # for t in [5e8]:
        #     nv_sig["CPG_laser_dur"] = t

            # do_SPaCE(nv_sig, nv_sig, apd_indices,num_runs, num_steps_a, num_steps_b,
            #  img_range_1D,img_range_2D, offset)
            
        # for nv_sig in [nv_sig_4,nv_sig_8]:
        # do_lifetime(nv_sig, apd_indices)
            

        #do_optimize_magnet_angle(nv_sig, apd_indices)

        # do_rabi(nv_sig, nv_sig, apd_indices, States.LOW, uwave_time_range=[0, 100])
        # do_rabi(nv_sig, nv_sig,apd_indices, States.HIGH, uwave_time_range=[0, 150])

        #do_pulsed_resonance(nv_sig, nv_sig, apd_indices, 2.87, 0.6) ###
        # do_pulsed_resonance_state(nv_sig, nv_sig,apd_indices, States.LOW)
        # do_pulsed_resonance_state(nv_sig, nv_sig,apd_indices, States.HIGH)
        # do_ramsey(nv_sig, nv_sig,apd_indices)

        # do_spin_echo(nv_sig, apd_indices)
        #do_relaxation(nv_sig_10, apd_indices)
        
        # for n in [2, 3, 4, 5, 6, 8, 9, 10, 25, 50]:
            
        #do_dd_cpmg(nv_sig, apd_indices, 4, 200 )
        # do_dd_xy8(nv_sig, apd_indices, 1 )
        
        # for N in [4, 2, 1]:
        #       do_dd_xy4_revivals(nv_sig_4, apd_indices, N)
        
        #do_dd_xy4(nv_sig, apd_indices, 1, 1, 100, 0, 90) 
        do_dd_xy4(nv_sig_8, apd_indices, 4, 2, 0, 260-50, 260+50) 

        #do_dd_xy8(nv_sig, apd_indices, 1 ) 
        # do_discrete_rabi(nv_sig, apd_indices, States.HIGH)

        # do_relaxation(nv_sig, apd_indices)
        
        # do_determine_standard_readout_params(nv_sig, apd_indices)
        # do_determine_charge_readout_params(nv_sig, apd_indices)

        # Operations that don't need an NV#
        # tool_belt.set_drift([0.0, 0.0, 0.0])  # Totally reset
        # tool_belt.set_drift([0.0, 0.0, tool_belt.get_drift()[2]])  # Keep z
        # tool_belt.set_xyz(labrad.connect(), [0,0,5])
#-0.243, -0.304,5.423
#ML -0.216, -0.115,5.417
    except Exception as exc:
        # Intercept the exception so we can email it out and re-raise it
        if not debug_mode:
            tool_belt.send_exception_email()
        raise exc

    finally:
        # Reset our hardware - this should be done in each routine, but
        # let's double check here
        tool_belt.reset_cfm()
        tool_belt.reset_safe_stop()
