# -*- coding: utf-8 -*-
"""This file contains functions to control the CFM. Just change the function call
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
import majorroutines.image_sample as image_sample
import majorroutines.optimize as optimize
import majorroutines.stationary_count as stationary_count
import majorroutines.resonance as resonance
import majorroutines.pulsed_resonance as pulsed_resonance
import majorroutines.optimize_magnet_angle as optimize_magnet_angle
import majorroutines.rabi as rabi
import majorroutines.g2_measurement as g2_measurement
import majorroutines.t1_double_quantum as t1_double_quantum
import majorroutines.t1_interleave as t1_interleave
import majorroutines.ramsey as ramsey
import majorroutines.spin_echo as spin_echo
import majorroutines.lifetime_v2 as lifetime
import majorroutines.set_drift_from_reference_image as set_drift_from_reference_image
import debug.test_major_routines as test_major_routines
from utils.tool_belt import States


# %% Minor Routines


def set_xyz(nv_sig):

    with labrad.connect() as cxn:
        tool_belt.set_xyz(cxn, nv_sig)

def set_xyz_zero():

    with labrad.connect() as cxn:
        tool_belt.set_xyz_zero(cxn)


# %% Major Routines


def do_image_sample(nv_sig, apd_indices):
    
#    scan_range = 1.0
#    num_steps = 200
#    num_steps = 120
#    num_steps = 90
#    scan_range = 0.5
#    num_steps = 150
    scan_range = 0.2
#    num_steps = 90
#    scan_range = 0.1
    num_steps = 60
#    scan_range = 0.05
#    num_steps = 60
#    scan_range = 0.025
#    num_steps = 60

    # For now we only support square scans so pass scan_range twice
    image_sample.main(nv_sig, scan_range, scan_range, num_steps, apd_indices)

def do_optimize(nv_sig, apd_indices):

    optimize.main(nv_sig, apd_indices,
              set_to_opti_coords=False, save_data=True, plot_data=True)

def do_optimize_list(nv_sig_list, apd_indices):

    optimize.optimize_list(nv_sig_list, apd_indices)

def do_stationary_count(nv_sig, apd_indices):

    run_time = 90 * 10**9  # ns

    stationary_count.main(nv_sig, run_time, apd_indices)

def do_g2_measurement(nv_sig, apd_a_index, apd_b_index):

    run_time = 60 * 5  # s
    diff_window = 150  # ns

    g2_measurement.main(nv_sig, run_time, diff_window,
                        apd_a_index, apd_b_index)

def do_resonance(nv_sig, apd_indices, freq_center=2.87, freq_range=0.2):

    num_steps = 51
    num_runs = 3
    uwave_power = -13.0  # -13.0 with a 1.5 ND is a good starting point

    resonance.main(nv_sig, apd_indices, freq_center, freq_range,
                   num_steps, num_runs, uwave_power)

def do_resonance_state(nv_sig, apd_indices, state):

    freq_center = nv_sig['resonance_{}'.format(state.name)]
    freq_range = 0.07
    num_steps = 51
    num_runs = 15
    uwave_power = -13.0  # -13.0 with a 1.5 ND is a good starting point
#    uwave_power = -5.0  # After inserting mixer

    resonance.main(nv_sig, apd_indices, freq_center, freq_range,
                   num_steps, num_runs, uwave_power)

def do_pulsed_resonance(nv_sig, apd_indices,
                        freq_center=2.87, freq_range=0.2):

    num_steps = 51
    num_reps = 10**5
    num_runs = 1
    uwave_power = 9.0
    uwave_pulse_dur = 200

    pulsed_resonance.main(nv_sig, apd_indices, freq_center, freq_range,
                          num_steps, num_reps, num_runs,
                          uwave_power, uwave_pulse_dur)

def do_pulsed_resonance_state(nv_sig, apd_indices, state):

    freq_range = 0.02
#    num_steps = 101
#    freq_range = 0.025
    num_steps = 51
    num_reps = 10**5
    num_runs = 2

    pulsed_resonance.state(nv_sig, apd_indices, state, freq_range,
                          num_steps, num_reps, num_runs)

def do_optimize_magnet_angle(nv_sig, apd_indices):

    angle_range = [0, 150]
    num_angle_steps = 6
    freq_center = 2.87
    freq_range = 0.150
    num_freq_steps = 76
    num_freq_runs = 2
    uwave_power = 9.0
    uwave_pulse_dur = 200  # Set to None for CWESR
    num_freq_reps = 10**5

    optimize_magnet_angle.main(nv_sig, apd_indices,
               angle_range, num_angle_steps, freq_center, freq_range,
               num_freq_steps, num_freq_reps, num_freq_runs,
               uwave_power, uwave_pulse_dur)

def do_rabi(nv_sig, apd_indices, state, uwave_time_range=[0, 200]):

    num_steps = 51
    num_reps = 10**5
    num_runs = 2

    rabi.main(nv_sig, apd_indices, uwave_time_range,
              state, num_steps, num_reps, num_runs)

def do_t1_battery(nv_sig, apd_indices):

    # T1 experiment parameters, formatted:
    # [[init state, read state], relaxation_time_range, num_steps, num_reps, num_runs]
        
    t1_exp_array = numpy.array([
            [[States.ZERO, States.HIGH], [0, 7*10**6], 26, 0.3*10**4, 230],
            [[States.ZERO, States.ZERO], [0, 7*10**6], 26, 0.3*10**4, 230]
            ])

    # Loop through the experiments
    for exp_ind in range(len(t1_exp_array)):

        init_read_states = t1_exp_array[exp_ind, 0]
        relaxation_time_range = t1_exp_array[exp_ind, 1]
        num_steps = t1_exp_array[exp_ind, 2]
        num_reps = t1_exp_array[exp_ind, 3]
        num_runs = t1_exp_array[exp_ind, 4]

        t1_double_quantum.main(nv_sig, apd_indices, relaxation_time_range,
                           num_steps, num_reps, num_runs, init_read_states)

def do_t1_interleave(nv_sig, apd_indices):
    # T1 experiment parameters, formatted:
    # [[init state, read state], relaxation_time_range, num_steps, num_reps]
    # ~18 hrs
    num_runs = 40
    t1_exp_array = numpy.array([
                        [[States.HIGH, States.LOW], [0, 10*10**3], 51, 8*10**4, num_runs],
                        [[States.HIGH, States.LOW], [0, 50*10**3], 51, 8*10**4, num_runs],
                        [[States.HIGH, States.LOW], [0, 150*10**3], 26, 8*10**4, num_runs],
                        [[States.HIGH, States.HIGH], [0, 10*10**3], 51, 8*10**4, num_runs],
                        [[States.HIGH, States.HIGH], [0, 50*10**3], 51, 8*10**4, num_runs],
                        [[States.HIGH, States.HIGH], [0, 150*10**3], 26, 8*10**4, num_runs],
                        [[States.ZERO, States.HIGH], [0, 2*10**6], 26, 1.3*10**4, num_runs],
                        [[States.ZERO, States.ZERO], [0, 2*10**6], 26, 1.3*10**4, num_runs]
                        ])

    t1_interleave.main(nv_sig, apd_indices, t1_exp_array, num_runs)

def do_lifetime(nv_sig, apd_indices):
    
    num_reps = 10**6
    num_runs = 1
    num_bins = 100
#    readout_time = 1.2 * 10**6
    readout_time = 500
    
    lifetime.main(nv_sig, apd_indices, readout_time,
                  num_reps, num_runs, num_bins)
    
def do_ramsey(nv_sig, apd_indices):

    detuning = 2.5  # MHz
    precession_time_range = [0, 4 * 10**3]
    num_steps = 151
    num_reps = 3 * 10**5
    num_runs = 1

    ramsey.main(nv_sig, apd_indices, detuning, precession_time_range,
                num_steps, num_reps, num_runs)

def do_spin_echo(nv_sig, apd_indices):

    # T2 in nanodiamond NVs without dynamical decoupling is just a couple
    # us so don't bother looking past 10s of us
#    precession_time_range = [0, 100 * 10**3]
    precession_time_range = [0, 10 * 10**3]
    num_steps = 101
    num_reps = int(8.0 * 10**4)
    num_runs = 150
    state = States.HIGH

    spin_echo.main(nv_sig, apd_indices, precession_time_range,
                   num_steps, num_reps, num_runs, state)

def do_sample_nvs(nv_sig_list, apd_indices):

    # g2 parameters
    run_time = 60 * 5
    diff_window = 150

    # PESR parameters
    num_steps = 101
    num_reps = 10**5
    num_runs = 5
    uwave_power = 9.0
    uwave_pulse_dur = 100

    g2 = g2_measurement.main_with_cxn
    pesr = pulsed_resonance.main_with_cxn

    with labrad.connect() as cxn:
        for nv_sig in nv_sig_list:
            g2_zero = g2(cxn, nv_sig, run_time, diff_window,
                         apd_indices[0], apd_indices[1])
            if g2_zero < 0.5:
                pesr(cxn, nv_sig, apd_indices, 2.87, 0.1, num_steps,
                     num_reps, num_runs, uwave_power, uwave_pulse_dur)

def find_resonance_and_rabi(nv_sig, apd_indices):
    # Given resonances and rabi periods in the nv_sig, automatically remeasures
    state_list = [States.LOW, States.HIGH]
    num_steps = 51
    num_runs = 2

    fail_bool = False

    value_list = []
    for state in state_list:

        # Run resonance and save the resonance found
        num_reps = 10**5
        freq_range = 0.018

        print('Measureing pESR on {}\n'.format(state.name))
        resonance_list = pulsed_resonance.state(nv_sig, apd_indices, state, freq_range,
                              num_steps, num_reps, num_runs)
        resonance = resonance_list[0]
        value_list.append('%.4f'%resonance)

        if resonance is None:
            print('Resonance fitting failed')
            fail_bool = True
            return

        # If the resonance has shifted more than 1 MHz in either direction, stop
        shift_res = 10/1000
        limit_high_res = (nv_sig['resonance_{}'.format(state.name)] + shift_res)
        limit_low_res =  (nv_sig['resonance_{}'.format(state.name)] - shift_res)

        if resonance > limit_high_res or resonance < limit_low_res:
            print('Resonance has shifted more than {} MHz'.format(float(shift_res)))
            fail_bool = True
            return
        else:
            nv_sig['resonance_{}'.format(state.name)] = float('%.4f'%resonance)

        # Run rabi and save the rabi period
        uwave_time_range = [0, 400]
        num_reps = 2*10**5

        print('Measureing rabi on {}\n'.format(state.name))
        rabi_per = rabi.main(nv_sig, apd_indices, uwave_time_range,
                  state, num_steps, num_reps, num_runs)
        value_list.append('%.1f'%rabi_per)

        if rabi_per is None:
            print('Rabi fitting failed')
            fail_bool = True
            return

        # If the rabi period has shifted more than 50 ns in either direction, stop
        shift_per =50
        limit_high_per = (nv_sig['rabi_{}'.format(state.name)] + shift_per)
        limit_low_per =  (nv_sig['rabi_{}'.format(state.name)] - shift_per)

        if rabi_per > limit_high_per or rabi_per < limit_low_per:
            print('Rabi period has changed more than {} ns'.format(shift_per))
            fail_bool = True
            return
        else:
            nv_sig['rabi_{}'.format(state.name)] = float('%.1f'%rabi_per)

    print(value_list)

    timestamp = tool_belt.get_time_stamp()
    raw_data = {'nv_sig': nv_sig,
                'nv_sig-units': tool_belt.get_nv_sig_units(),
                'value_list': value_list,
                'value_list-units': 'GHz, ns, GHz, ns'
                }

    file_path = 'E:/Shared drives/Kolkowitz Lab Group/nvdata/auto_pESR_rabi/' + '{}-{}'.format(timestamp, nv_sig['name'])
    tool_belt.save_raw_data(raw_data, file_path)

    return fail_bool

def do_set_drift_from_reference_image(nv_sig, apd_indices):

    # ref_file_name = '2019-06-10_15-22-25_ayrton12'  # 60 x 60
    ref_file_name = '2019-06-27_16-37-18_johnson1' # bulk nv, first one we saw

    set_drift_from_reference_image.main(ref_file_name, nv_sig, apd_indices)

def do_test_major_routines(nv_sig, apd_indices):
    """Run this whenver you make a significant code change. It'll make sure
    you didn't break anything in the major routines.
    """

    test_major_routines.main(nv_sig, apd_indices)


# %% Run the file


if __name__ == '__main__':

    # %% Shared parameters

    apd_indices = [0]
#    apd_indices = [0, 1]
    
    sample_name = 'goeppert_mayer'

    NV_search = { 'coords': [0.0, 0.0, 5.0],
            'name': '{}-lifetime'.format(sample_name),
            'expected_count_rate': None, 'nd_filter': 'nd_1.0',
            'pulsed_readout_dur': 450, 'magnet_angle': None,
            'resonance_LOW': None, 'rabi_LOW': None, 'uwave_power_LOW': 9.0,
            'resonance_HIGH': None, 'rabi_HIGH': None, 'uwave_power_HIGH': 10.0}

    lifetime_test = { 'coords': [-0.051, 0.005, 5.00],
            'name': '{}-lifetime_test'.format(sample_name),
            'expected_count_rate': 55, 'nd_filter': 'nd_1.0',
            'pulsed_readout_dur': 450, 'magnet_angle': None,
            'resonance_LOW': None, 'rabi_LOW': None, 'uwave_power_LOW': 9.0,
            'resonance_HIGH': None, 'rabi_HIGH': None, 'uwave_power_HIGH': 10.0}
    
    nv_sig_list = [lifetime_test]
    

    # %% Functions to run

    try:
        
        # Operations that don't need an NV
#         set_xyz_zero()
#        set_xyz([-0.063, -0.210, 5.69]) # On NV 
#        set_xyz([-0.122, -0.151, 5.69]) # Off NV 
#        set_xyz([0.0, 0.0, 5.0,])
#        drift = tool_belt.get_drift()
#        print(drift)
#        tool_belt.set_drift([0.0, 0.0, 0.0])
#        set_xyz([0.0, 0.0, 5.02 + tool_belt.get_drift()[2]])
#        with labrad.connect() as cxn:
#            cxn.filter_slider_ell9k.set_filter('nd_0.5')
#            cxn.pulse_streamer.constant([])
#            input('Press enter to stop...')
        
#        with labrad.connect() as cxn:
#            cxn.pulse_treamer.constant([3], 0.0, 0.0)        
        

        # Routines that expect lists of NVs
#        do_optimize_list(nv_sig_list, apd_indices)
#        do_sample_nvs(nv_sig_list, apd_indices)
#        do_g2_measurement(nv_sig_list, apd_indices[0], apd_indices[1])

        
        # Routines that expect single NVs
        for ind in range(len(nv_sig_list)):
            nv_sig = nv_sig_list[ind]                
#            for z in numpy.linspace(5.5, 6.5, 6):
#                nv_sig_copy = copy.deepcopy(nv_sig)
#                coords = nv_sig_copy['coords']
#                nv_sig_copy['coords'] = [coords[0], coords[1], z]
#                do_image_sample(nv_sig_copy, apd_indices)
#            do_image_sample(nv_sig, apd_indices)
#            do_optimize(nv_sig, apd_indices)
#            do_stationary_count(nv_sig, apd_indices)
#            do_g2_measurement(nv_sig, apd_indices[0], apd_indices[1])
#            do_optimize_magnet_angle(nv_sig, apd_indices)
#            do_resonance(nv_sig, apd_indices)
#            do_resonance(nv_sig, apd_indices, freq_center=2.87, freq_range=0.1)
#            do_resonance_state(nv_sig, apd_indices, States.LOW)
#            do_resonance_state(nv_sig, apd_indices, States.HIGH)
#            do_pulsed_resonance(nv_sig, apd_indices)
#            do_pulsed_resonance(nv_sig, apd_indices, freq_center=2.87, freq_range=0.1)
#            do_pulsed_resonance(nv_sig, apd_indices, freq_center=3.200, freq_range=0.100)
#            do_pulsed_resonance_state(nv_sig, apd_indices, States.LOW)
#            do_pulsed_resonance_state(nv_sig, apd_indices, States.HIGH)
#            do_pulsed_resonance(nv_sig, apd_indices,
#                        freq_center=nv_sig['resonance_LOW'], freq_range=0.15)
#            do_pulsed_resonance(nv_sig, apd_indices,
#                        freq_center=nv_sig['resonance_HIGH'], freq_range=0.1)
#            do_pulsed_resonance(nv_sig, apd_indices, freq_center=2.87, freq_range=0.15)
#            do_pulsed_resonance(nv_sig, apd_indices, freq_center=3.0, freq_range=0.15)
#            do_rabi(nv_sig, apd_indices, States.LOW, [0, 300])
#            do_rabi(nv_sig, apd_indices, States.HIGH, [0, 400])
#            find_resonance_and_rabi(nv_sig, apd_indices)
#            do_t1_battery(nv_sig, apd_indices)
#            do_t1_interleave(nv_sig, apd_indices)
            do_lifetime(nv_sig, apd_indices)
#            find_resonance_and_rabi(nv_sig, apd_indices)
            
#            fail_bool = find_resonance_and_rabi(nv_sig, apd_indices)
#            if fail_bool == True:
#                print('Failed to record pESR and Rabi')
#                break
#            else:
#                do_t1_battery(nv_sig, apd_indices)
            
#            do_ramsey(nv_sig, apd_indices)
#            do_spin_echo(nv_sig, apd_indices)
#            do_set_drift_from_reference_image(nv_sig, apd_indices)
#            do_test_major_routines(nv_sig, apd_indices)
#            with labrad.connect() as cxn:
#                tool_belt.set_xyz_on_nv(cxn, nv_sig)

    finally:
        # Reset our hardware - this should be done in each routine, but
        # let's double check here
        tool_belt.reset_cfm()
        # Kill safe stop
        if tool_belt.check_safe_stop_alive():
            print('\n\nRoutine complete. Press enter to exit.')
            tool_belt.poll_safe_stop()
