# -*- coding: utf-8 -*-
"""
Scans the laser frequency, taking counts at a point.

Created on April 11th, 2019

@author: mccambria
"""

import utils.tool_belt as tool_belt
import utils.kplotlib as kpl
from utils.kplotlib import KplColors
import majorroutines.optimize as optimize
import numpy as np
import matplotlib.pyplot as plt
import time
from scipy.optimize import curve_fit, brute
from scipy.signal import find_peaks
import labrad
from utils.tool_belt import States, NormStyle
from random import shuffle
import sys
from utils.positioning import get_scan_1d as calculate_freqs
from pathlib import Path
from inspect import signature
from scipy.special import voigt_profile as scipy_voigt
import json
import socket
import utils.positioning as positioning
import matplotlib.ticker as ticker

# region Control panel functions
    
def main(
    nv_sig,
    freq_center,
    freq_range,
    num_steps,
    num_reps,
    num_runs,
):
    """Pulsed electron spin resonance measurement

    Parameters
    ----------
    nv_sig : dict
        Dictionary with the properties of the NV to work with
    freq_center : numeric
        Center of the frequency range used in the ESR scan
    freq_range : numeric
        Frequency range of the ESR scan
    num_steps : numeric
        Number of steps in the ESR scan
    num_reps : int
        Number of times to repeat each experiment at each frequency per run
    num_runs : int
        Number of times to scan through the frequencies under test
    """

    with labrad.connect() as cxn:
        return main_with_cxn(
            cxn,
            nv_sig,
            freq_center,
            freq_range,
            num_steps,
            num_reps,
            num_runs
        )


def main_with_cxn(
    cxn,
    nv_sig,
    freq_center,
    freq_range,
    num_steps,
    num_reps,
    num_runs,
):
    ### Setup

    start_timestamp = tool_belt.get_time_stamp()

    kpl.init_kplotlib()

    counter = tool_belt.get_server_counter(cxn)
    laser_msquared = tool_belt.get_server_laser_msquared(cxn)
    pulsegen_server = tool_belt.get_server_pulse_gen(cxn)
    tool_belt.reset_cfm(cxn)

    # readout = nv_sig["spin_readout_dur"]
    

    freqs = calculate_freqs(freq_center, freq_range, num_steps)
    print("freqs: ", freqs)
    # Set up our data structure, an array of NaNs that we'll fill incrementally.
    # NaNs are ignored by matplotlib, which is why they're useful for us here.
    # We define 2D arrays, with the horizontal dimension for the frequency and
    # the veritical dimension for the index of the run.
    sig_counts = np.empty([num_runs, num_steps])

    # Sequence processing
    readout = 1e8
    readout_sec=readout/10**9
    seq_args = [readout]
    seq_name = "siv_frequency_sweep.py"
    # seq_args = [0, readout, 'laserglow_532', -1]
    # seq_name = "siv_sweep_532.py"
    seq_args_string = tool_belt.encode_seq_args(seq_args)
    pulsegen_server.stream_load(seq_name, seq_args_string)  
    
    # print(seq_args)   
    
    ### Collect the data

    # Create a list of indices to step through the freqs. This will be shuffled
    freq_index_master_list = [[] for i in range(num_runs)]
    freq_ind_list = list(range(0, num_steps))
    print("freq_ind_lis: ", freq_ind_list)
    original_freq_ind_list = freq_ind_list.copy()
    
    
    # start_timestamp = tool_belt.get_time_stamp()
    # Start 'Press enter to stop...'
    tool_belt.init_safe_stop()
    

    for run_ind in range(num_runs):
        print("Run index: {}".format(run_ind))
        # shuffle(freq_ind_list)

        # Break out of the while if the user says stop
        # Optimize and save the coords we found
        # opti_coords = optimize.main_with_cxn(cxn, nv_sig)
        # opti_coords_list.append(opti_coords)

        # Set up the microwaves and laser. Then load the pulse streamer
        # (must happen after optimize and iq_switch since run their
        # own sequences)
        counter.start_tag_stream()
        
        # Take a sample and step through the shuffled frequencies
        # shuffle(freq_ind_list)
        for freq_ind, wavelength in enumerate(freqs):
            print("freq_ind: {}, wavelength: {}".format(freq_ind, wavelength))
            # laser_msquared.etalon_status(27)
            laser_msquared.start_table_tuning(wavelength,430)        
            # Break out of the while if the user says stop
            if tool_belt.safe_stop():
                break
            freq_response=laser_msquared.poll_table_tuning(102)
            freq_response_data = json.loads(freq_response.decode('utf-8'))
            actual_freq_ind=freq_response_data.get("message", {}).get("parameters", {}).get("wavelength")
            print(actual_freq_ind)
            freq_index_master_list[run_ind].append(actual_freq_ind)   
            counter.clear_buffer()
            pulsegen_server.stream_start(1)        
            counts = counter.read_counter_simple(1)
            # sample to read=1
            sig_counts[run_ind, freq_ind] = counts[0]
            
        counter.stop_tag_stream()

    ### Process and plot the data

    # raw_fig = plt(actual_freq_ind, sig_counts)

    avg_counts = np.mean(sig_counts, axis=0)

    # Conversion from nm to THz
    # speed_of_light_nm_per_THz = 299792.458
    wl = [ wavelength for wavelength in freqs]
    # freqs_THz = [speed_of_light_nm_per_THz / wavelength for wavelength in freqs]
    raw_fig, ax = plt.subplots()
    # ax.plot(freqs_THz, avg_counts)
    ax.plot(wl, avg_counts)
    # ax.plot(freqs.tolist(), avg_counts)

    # avg_counts = np.mean(sig_counts, axis=0)
    
    # raw_fig, ax = plt.subplots()
    # ax.plot(freqs_MHz, avg_counts)
    
    # Or, if you prefer a scatter plot
    # plt.scatter(actual_freq_ind, sig_counts)
    
    # Add labels and title, if desired
    # ax.set_xlabel('Frequency (THz)')
    ax.set_xlabel('Wavelength(nm)')
    ax.set_ylabel('Mean signal Counts')
    ax.set_title('Signal Counts vs. Frequency')
    
    ax.xaxis.set_major_locator(ticker.MultipleLocator(0.25))  
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(0.05)) 
    
    # Show the plot
    plt.show()

    ### Clean up, save the data, return

    tool_belt.reset_cfm(cxn)

    timestamp = tool_belt.get_time_stamp()

    # If you update this, also update the incremental data above if necessary
    data = {
        "start_timestamp": start_timestamp,
        "timestamp": timestamp,
        "nv_sig": nv_sig,
        # "opti_coords_list": opti_coords_list,
        # "opti_coords_list-units": "V",
        "freq_center": freq_center,
        "freq_center-units": "GHz",
        "freq_range": freq_range,
        "freq_range-units": "GHz",
        "num_steps": num_steps,
        "num_reps": num_reps,
        "num_runs": num_runs,
        "readout": readout,
        "readout-units": "ns",
        # "freqs":freqs_THz,
        "wavelength":wl,
        "freq_index_master_list": freq_index_master_list,
        # "opti_coords_list": opti_coords_list,
        # "opti_coords_list-units": "V",
        "sig_counts": sig_counts.astype(int).tolist(),
        "sig_counts-units": "counts",
    }

    nv_name = nv_sig["name"]

    file_path = tool_belt.get_file_path(__file__, timestamp, nv_name)
    data_file_name = file_path.stem
    tool_belt.save_figure(raw_fig, file_path)

    tool_belt.save_raw_data(data, file_path)
    # tool_belt.poll_safe_stop()

# endregion


if __name__ == "__main__":
    file_name = "2023_12_19-12_00_24-wu-nv22_region5"

    kpl.init_kplotlib()

    data = tool_belt.get_raw_data(file_name)

    plt.show(block=True)
