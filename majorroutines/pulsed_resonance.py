# -*- coding: utf-8 -*-
"""
Electron spin resonance routine. Scans the microwave frequency, taking counts
at each point.

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
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import labrad
from utils.tool_belt import States, NormStyle
from random import shuffle
import sys
from utils.positioning import get_scan_1d as calculate_freqs


# region Plotting


def create_fit_figure(
    freq_center,
    freq_range,
    num_steps,
    norm_avg_sig,
    norm_avg_sig_ste,
    fit_func=None,
    popt=None,
    guess_params=None,
):

    # Fitting
    if (fit_func is None) or (popt is None):
        fit_func, popt, pcov = fit_resonance(
            freq_center,
            freq_range,
            num_steps,
            norm_avg_sig,
            norm_avg_sig_ste,
            fit_func,
            guess_params,
        )

    # Plot setup
    fig, ax = plt.subplots()
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("Normalized fluorescence")
    freqs = calculate_freqs(freq_center, freq_range, num_steps)
    smooth_freqs = calculate_freqs(freq_center, freq_range, 1000)

    # Plotting
    if norm_avg_sig_ste is not None:
        kpl.plot_points(ax, freqs, norm_avg_sig, yerr=norm_avg_sig_ste)
    else:
        kpl.plot_line(ax, freqs, norm_avg_sig)
    kpl.plot_line(
        ax,
        smooth_freqs,
        fit_func(smooth_freqs, *popt),
        color=KplColors.RED,
    )

    # Text boxes to describe the fits
    low_text = None
    high_text = None
    base_text = "A = {:.3f} \nwidth = {:.1f} MHz \nf = {:.4f} GHz"
    if len(popt) == 3:
        contrast, hwhm, freq = popt[0:3]
        low_text = base_text.format(contrast, hwhm, freq)
        high_text = None
    elif len(popt) == 6:
        contrast, hwhm, freq = popt[0:3]
        low_text = base_text.format(contrast, hwhm, freq)
        contrast, hwhm, freq = popt[3:6]
        high_text = base_text.format(contrast, hwhm, freq)
    size = kpl.Size.SMALL
    if low_text is not None:
        kpl.anchored_text(ax, low_text, kpl.Loc.LOWER_LEFT, size=size)
    if high_text is not None:
        kpl.anchored_text(ax, high_text, kpl.Loc.LOWER_RIGHT, size=size)

    # Wrap up
    kpl.tight_layout(fig)
    return fig, ax, fit_func, popt, pcov


def create_raw_data_figure(
    freq_center,
    freq_range,
    num_steps,
    avg_sig_counts=None,
    avg_ref_counts=None,
    norm_avg_sig=None,
):

    # Plot setup
    fig, axes_pack = plt.subplots(1, 2, figsize=kpl.double_figsize)
    ax_sig_ref, ax_norm = axes_pack
    ax_sig_ref.set_xlabel("Frequency (GHz)")
    ax_sig_ref.set_ylabel("Count rate (kcps)")
    ax_norm.set_xlabel("Frequency (GHz)")
    ax_norm.set_ylabel("Normalized fluorescence")
    freqs = calculate_freqs(freq_center, freq_range, num_steps)

    # Plotting
    if avg_sig_counts is None:
        avg_sig_counts = np.empty(num_steps)
        avg_sig_counts[:] = np.nan
    kpl.plot_line(
        ax_sig_ref, freqs, avg_sig_counts, label="Signal", color=KplColors.GREEN
    )
    if avg_ref_counts is None:
        avg_ref_counts = np.empty(num_steps)
        avg_ref_counts[:] = np.nan
    kpl.plot_line(
        ax_sig_ref, freqs, avg_ref_counts, label="Reference", color=KplColors.RED
    )
    ax_sig_ref.legend(loc=kpl.Loc.LOWER_RIGHT)
    if norm_avg_sig is None:
        norm_avg_sig = np.empty(num_steps)
        norm_avg_sig[:] = np.nan
    kpl.plot_line(ax_norm, freqs, norm_avg_sig, color=KplColors.BLUE)

    # Wrap up
    kpl.tight_layout(fig)
    return fig, ax_sig_ref, ax_norm


# endregion
# region Math functions


def rabi_line(freq, constrast, rabi_freq, res_freq):
    """Lineshape for PESR under a pi pulse for the actual resonant frequency"""

    rabi_freq_ghz = rabi_freq / 1000
    detuning = freq - res_freq
    effective_rabi_freq = np.sqrt(detuning**2 + rabi_freq_ghz**2)
    effective_contrast = constrast * ((rabi_freq_ghz / effective_rabi_freq) ** 2)
    pulse_dur = np.pi / rabi_freq_ghz  # Assumed
    return effective_contrast * np.sin(effective_rabi_freq * pulse_dur / 2)


def rabi_line_hyperfine(freq, constrast, rabi_freq, res_freq):
    """Sum of 3 Rabi lineshapes separated by hyperfine splitting for N14"""

    hyperfine = 2.14 / 1000  # Hyperfine in GHz
    val = (1 / 3) * (
        rabi_line(freq, constrast, rabi_freq, res_freq - hyperfine)
        + rabi_line(freq, constrast, rabi_freq, res_freq)
        + rabi_line(freq, constrast, rabi_freq, res_freq + hyperfine)
    )
    return val


def gaussian(freq, constrast, sigma, center):
    sigma_ghz = sigma / 1000
    return constrast * np.exp(-((freq - center) ** 2) / (2 * (sigma_ghz**2)))


def lorentzian(freq, constrast, hwhm, center):
    """Normalized that the value at the center is the contrast"""
    hwhm_ghz = hwhm / 1000
    return constrast * (hwhm_ghz**2) / ((freq - center) ** 2 + hwhm_ghz**2)


def double_dip(
    freq,
    low_contrast,
    low_width,
    low_center,
    high_contrast,
    high_width,
    high_center,
    dip_func=rabi_line,
):
    low_dip = dip_func(freq, low_contrast, low_width, low_center)
    high_dip = dip_func(freq, high_contrast, high_width, high_center)
    return 1.0 - (low_dip + high_dip)


def single_dip(freq, contrast, width, center, dip_func=rabi_line):
    return 1.0 - dip_func(freq, contrast, width, center)


# endregion
# region Analysis functions


def return_res_with_error(data, fit_func=None, guess_params=None):
    """Returns the frequency/error of the resonance in a spectrum.
    Intended for extracting the frequency/error of a single resonance -
    if there's a double, we'll return the average. data should be some
    completed experiment file's raw data dictionary
    """

    freq_center = data["freq_center"]
    freq_range = data["freq_range"]
    num_steps = data["num_steps"]
    ref_counts = data["ref_counts"]
    sig_counts = data["sig_counts"]
    num_reps = data["num_reps"]
    nv_sig = data["nv_sig"]
    readout = nv_sig["spin_readout_dur"]
    try:
        norm_style = NormStyle[str.upper(nv_sig["norm_style"])]
    except Exception as exc:
        # norm_style = NormStyle.POINT_TO_POINT
        norm_style = NormStyle.SINGLE_VALUED

    _, _, norm_avg_sig, norm_avg_sig_ste = process_counts(
        sig_counts, ref_counts, num_reps, readout, norm_style
    )

    fit_func, popt, pcov = fit_resonance(
        freq_center,
        freq_range,
        num_steps,
        norm_avg_sig,
        norm_avg_sig_ste,
        fit_func,
        guess_params,
    )

    if len(popt) == 6:
        # print("Double resonance")
        low_res_ind = 2
        high_res_ind = low_res_ind + 3
        avg_res = (popt[low_res_ind] + popt[high_res_ind]) / 2
        low_res_err = np.sqrt(pcov[low_res_ind, low_res_ind])
        hig_res_err = np.sqrt(pcov[high_res_ind, high_res_ind])
        avg_res_err = np.sqrt(low_res_err**2 + hig_res_err**2) / 2
        return avg_res, avg_res_err
    else:
        # print("Single resonance")
        res_ind = 2
        # res_ind = 1  # MCC sigma
        res = popt[res_ind]
        res_err = np.sqrt(pcov[res_ind, res_ind])
        return res, res_err


def get_guess_params(
    freq_center, freq_range, num_steps, norm_avg_sig, norm_avg_sig_ste
):
    """Get guess params for line fitting. Most importantly how many resonances and what
    their frequencies are
    """

    # Setup for scipy's peak finding algorithm
    freqs = calculate_freqs(freq_center, freq_range, num_steps)
    inverted_norm_avg_sig = 1 - norm_avg_sig

    hwhm = 0.004  # GHz
    hwhm_mhz = hwhm * 1000
    fwhm = 2 * hwhm

    # Convert to index space
    fwhm_ind = fwhm * (num_steps / freq_range)
    if fwhm_ind < 1:
        fwhm_ind = 1

    # Peaks should have an SNR of at least 3
    height = 3 * np.average(norm_avg_sig_ste)

    # Peaks must be separated from each other by the estimated fwhm (rayleigh
    # criteria), have a contrast of at least the noise or 5% (whichever is
    # greater), and have a width of at least two points
    peak_inds, details = find_peaks(
        inverted_norm_avg_sig, distance=fwhm_ind, height=height, width=2
    )
    peak_inds = peak_inds.tolist()
    peak_heights = details["peak_heights"].tolist()

    low_freq_guess = None
    high_freq_guess = None

    # Find the location of the highest peak
    max_peak_height = max(peak_heights)
    max_peak_peak_ind = peak_heights.index(max_peak_height)
    max_peak_freq = freqs[peak_inds[max_peak_peak_ind]]

    if len(peak_inds) > 1:

        # Remove what we just found so we can find the second highest peak
        peak_inds.pop(max_peak_peak_ind)
        peak_heights.pop(max_peak_peak_ind)

        # Find the location of the next highest peak
        next_max_peak_height = max(peak_heights)
        next_max_peak_peak_inds = peak_heights.index(
            next_max_peak_height
        )  # Index in peak_inds
        next_max_peak_freq = freqs[peak_inds[next_max_peak_peak_inds]]

        # Only keep the smaller peak if it's at least 50% the height of the larger peak
        if next_max_peak_height > 0.5 * max_peak_height:
            # Sort by frequency
            if max_peak_freq < next_max_peak_freq:
                low_freq_guess = max_peak_freq
                high_freq_guess = next_max_peak_freq
                low_contrast_guess = max_peak_height
                high_contrast_guess = next_max_peak_height
            else:
                low_freq_guess = next_max_peak_freq
                high_freq_guess = max_peak_freq
                low_contrast_guess = next_max_peak_height
                high_contrast_guess = max_peak_height
        else:
            low_freq_guess = max_peak_freq
            low_contrast_guess = max_peak_height
            high_freq_guess = None

    elif len(peak_inds) == 1:
        low_freq_guess = max_peak_freq
        high_freq_guess = None
        low_contrast_guess = max_peak_height
    else:
        # print("Could not locate peaks, using center frequency")
        low_freq_guess = freq_center
        high_freq_guess = None
        low_contrast_guess = height

    ### Fit functions

    if high_freq_guess is None:
        fit_func = single_dip
        guess_params = [low_contrast_guess, hwhm_mhz, low_freq_guess]
    else:
        fit_func = double_dip
        guess_params = [
            low_contrast_guess,
            hwhm_mhz,
            low_freq_guess,
            high_contrast_guess,
            hwhm_mhz,
            high_freq_guess,
        ]

    return fit_func, guess_params


def fit_resonance(
    freq_center,
    freq_range,
    num_steps,
    norm_avg_sig,
    norm_avg_sig_ste,
    fit_func=None,
    guess_params=None,
):

    freqs = calculate_freqs(freq_center, freq_range, num_steps)

    # Guess the fit function and params if not provided
    if (fit_func is None) or (guess_params is None):
        algo_fit_func, algo_guess_params = get_guess_params(
            freq_center, freq_range, num_steps, norm_avg_sig, norm_avg_sig_ste
        )
    if fit_func is None:
        fit_func = algo_fit_func
    if guess_params is None:
        guess_params = algo_guess_params

    popt, pcov = curve_fit(
        fit_func,
        freqs,
        norm_avg_sig,
        p0=guess_params,
        sigma=norm_avg_sig_ste,
        absolute_sigma=True,
    )

    return fit_func, popt, pcov


def process_counts(
    sig_counts, ref_counts, num_reps, readout, norm_style=NormStyle.SINGLE_VALUED
):
    """Extract the normalized average signal at each data point.
    Since we sometimes don't do many runs (<10), we often will have an
    insufficient sample size to run stats on for norm_avg_sig calculation.
    We assume Poisson statistics instead.
    """

    ref_counts = np.array(ref_counts)
    sig_counts = np.array(sig_counts)

    num_runs, num_points = ref_counts.shape
    readout_sec = readout * 1e-9

    # Find the averages across runs
    sig_counts_avg = np.average(sig_counts, axis=0)
    single_ref_avg = np.average(ref_counts)
    ref_counts_avg = np.average(ref_counts, axis=0)

    sig_counts_ste = np.sqrt(sig_counts_avg) / np.sqrt(num_runs)
    single_ref_ste = np.sqrt(single_ref_avg) / np.sqrt(num_runs * num_points)
    ref_counts_ste = np.sqrt(ref_counts_avg) / np.sqrt(num_runs)

    if norm_style == NormStyle.SINGLE_VALUED:
        norm_avg_sig = sig_counts_avg / single_ref_avg
        norm_avg_sig_ste = norm_avg_sig * np.sqrt(
            (sig_counts_ste / sig_counts_avg) ** 2
            + (single_ref_ste / single_ref_avg) ** 2
        )
    elif norm_style == NormStyle.POINT_TO_POINT:
        norm_avg_sig = sig_counts_avg / ref_counts_avg
        norm_avg_sig_ste = norm_avg_sig * np.sqrt(
            (sig_counts_ste / sig_counts_avg) ** 2
            + (ref_counts_ste / ref_counts_avg) ** 2
        )

    sig_counts_avg_kcps = (sig_counts_avg / (num_reps * 1000)) / readout_sec
    ref_counts_avg_kcps = (ref_counts_avg / (num_reps * 1000)) / readout_sec

    return (
        sig_counts_avg_kcps,
        ref_counts_avg_kcps,
        norm_avg_sig,
        norm_avg_sig_ste,
    )


# endregion
# region Control panel functions


def state(
    nv_sig,
    state,
    freq_range,
    num_steps,
    num_reps,
    num_runs,
    composite=False,
    opti_nv_sig=None,
):

    freq_center = nv_sig["resonance_{}".format(state.name)]
    uwave_power = nv_sig["uwave_power_{}".format(state.name)]
    uwave_pulse_dur = tool_belt.get_pi_pulse_dur(nv_sig[f"rabi_{state.name}"])

    return main(
        nv_sig,
        freq_center,
        freq_range,
        num_steps,
        num_reps,
        num_runs,
        uwave_power,
        uwave_pulse_dur,
        state,
        composite,
        opti_nv_sig,
    )


def main(
    nv_sig,
    freq_center,
    freq_range,
    num_steps,
    num_reps,
    num_runs,
    uwave_power,
    uwave_pulse_dur,
    state=States.HIGH,
    composite=False,
    opti_nv_sig=None,
):

    with labrad.connect() as cxn:
        return main_with_cxn(
            cxn,
            nv_sig,
            freq_center,
            freq_range,
            num_steps,
            num_reps,
            num_runs,
            uwave_power,
            uwave_pulse_dur,
            state,
            composite,
            opti_nv_sig,
        )


def main_with_cxn(
    cxn,
    nv_sig,
    freq_center,
    freq_range,
    num_steps,
    num_reps,
    num_runs,
    uwave_power,
    uwave_pulse_dur,
    state=States.HIGH,
    composite=False,
    opti_nv_sig=None,
):

    ### Setup

    start_timestamp = tool_belt.get_time_stamp()

    kpl.init_kplotlib()
    tool_belt.reset_cfm(cxn)

    counter = tool_belt.get_server_counter(cxn)
    pulse_gen = tool_belt.get_server_pulse_gen(cxn)

    norm_style = nv_sig["norm_style"]
    polarization_time = nv_sig["spin_pol_dur"]
    readout = nv_sig["spin_readout_dur"]
    readout_sec = readout / (10**9)

    laser_key = "spin_laser"
    laser_name = nv_sig[laser_key]
    laser_power = tool_belt.set_laser_power(cxn, nv_sig, laser_key)

    freqs = calculate_freqs(freq_center, freq_range, num_steps)

    # Set up our data structure, an array of NaNs that we'll fill incrementally.
    # NaNs are ignored by matplotlib, which is why they're useful for us here.
    # We define 2D arrays, with the horizontal dimension for the frequency and
    # the veritical dimension for the index of the run.
    ref_counts = np.empty([num_runs, num_steps])
    ref_counts[:] = np.nan
    sig_counts = np.copy(ref_counts)

    # Sequence processing
    if composite:
        rabi_period = nv_sig[f"rabi_{state.name}"]
        pi_pulse = tool_belt.get_pi_pulse_dur(rabi_period)
        pi_on_2_pulse = tool_belt.get_pi_on_2_pulse_dur(rabi_period)
        seq_args = [
            polarization_time,
            readout,
            pi_pulse,
            pi_on_2_pulse,
            1,
            1,
            state.value,
            laser_name,
            laser_power,
        ]
        seq_args = [int(el) for el in seq_args]
        seq_name = "discrete_rabi2.py"
    else:
        seq_args = [
            uwave_pulse_dur,
            polarization_time,
            readout,
            uwave_pulse_dur,
            state.value,
            laser_name,
            laser_power,
        ]
        seq_name = "rabi.py"
    seq_args_string = tool_belt.encode_seq_args(seq_args)

    opti_coords_list = []

    # Create raw data figure for incremental plotting
    raw_fig, ax_sig_ref, ax_norm = create_raw_data_figure(
        freq_center, freq_range, num_steps
    )
    # Set up a run indicator for incremental plotting
    run_indicator_text = "Run #{}/{}"
    text = run_indicator_text.format(0, num_runs)
    run_indicator_obj = kpl.anchored_text(ax_norm, text, loc=kpl.Loc.UPPER_RIGHT)

    ### Collect the data

    # Create a list of indices to step through the freqs. This will be shuffled
    freq_index_master_list = [[] for i in range(num_runs)]
    freq_ind_list = list(range(0, num_steps))

    start_timestamp = tool_belt.get_time_stamp()

    # Start 'Press enter to stop...'
    tool_belt.init_safe_stop()

    for run_ind in range(num_runs):
        print("Run index: {}".format(run_ind))

        # Break out of the while if the user says stop
        if tool_belt.safe_stop():
            break

        # Optimize and save the coords we found
        if opti_nv_sig:
            ret_vals = optimize.main_with_cxn(cxn, opti_nv_sig)
            opti_coords = ret_vals[0]
        else:
            opti_coords = optimize.main_with_cxn(cxn, nv_sig)
        opti_coords_list.append(opti_coords)

        # Set up the microwaves and laser. Then load the pulse streamer
        # (must happen after optimize and iq_switch since run their
        # own sequences)
        sig_gen_cxn = tool_belt.get_server_sig_gen(cxn, state)
        sig_gen_cxn.set_amp(uwave_power)
        sig_gen_cxn.uwave_on()
        if composite:
            sig_gen_cxn.load_iq()
            awg_cxn = tool_belt.get_awg_server(cxn)
            awg_cxn.load_knill()
        tool_belt.set_filter(cxn, nv_sig, laser_key)
        laser_power = tool_belt.set_laser_power(cxn, nv_sig, laser_key)

        pulse_gen.stream_load(seq_name, seq_args_string)
        counter.start_tag_stream()

        # Take a sample and step through the shuffled frequencies
        shuffle(freq_ind_list)
        for freq_ind in freq_ind_list:

            # Break out of the while if the user says stop
            if tool_belt.safe_stop():
                break

            freq_index_master_list[run_ind].append(freq_ind)
            sig_gen_cxn.set_freq(freqs[freq_ind])

            counter.clear_buffer()
            pulse_gen.stream_start(int(num_reps))

            # Get and write the counts
            new_counts = counter.read_counter_modulo_gates(2, 1)
            sample_counts = new_counts[0]
            cur_run_sig_counts_summed = sample_counts[0]
            cur_run_ref_counts_summed = sample_counts[1]
            sig_counts[run_ind, freq_ind] = cur_run_sig_counts_summed
            ref_counts[run_ind, freq_ind] = cur_run_ref_counts_summed

        counter.stop_tag_stream()

        ### Incremental plotting

        # Update the run indicator
        text = run_indicator_text.format(run_ind + 1, num_runs)
        run_indicator_obj.txt.set_text(text)

        # Average the counts over the iterations
        inc_sig_counts = sig_counts[: run_ind + 1]
        inc_ref_counts = ref_counts[: run_ind + 1]
        ret_vals = process_counts(
            inc_sig_counts, inc_ref_counts, num_reps, readout, norm_style
        )
        (
            sig_counts_avg_kcps,
            ref_counts_avg_kcps,
            norm_avg_sig,
            norm_avg_sig_ste,
        ) = ret_vals

        kpl.plot_line_update(ax_sig_ref, line_ind=0, y=sig_counts_avg_kcps)
        kpl.plot_line_update(ax_sig_ref, line_ind=1, y=ref_counts_avg_kcps)
        kpl.plot_line_update(ax_norm, y=norm_avg_sig)

        ### Incremental saving

        data = {
            "start_timestamp": start_timestamp,
            "timestamp": tool_belt.get_time_stamp(),
            "nv_sig": nv_sig,
            "opti_coords_list": opti_coords_list,
            "opti_coords_list-units": "V",
            "freq_center": freq_center,
            "freq_center-units": "GHz",
            "freq_range": freq_range,
            "freq_range-units": "GHz",
            "uwave_pulse_dur": uwave_pulse_dur,
            "uwave_pulse_dur-units": "ns",
            "state": state.name,
            "num_steps": num_steps,
            "num_reps": num_reps,
            "num_runs": num_runs,
            "run_ind": run_ind,
            "uwave_power": uwave_power,
            "uwave_power-units": "dBm",
            "readout": readout,
            "readout-units": "ns",
            "freq_index_master_list": freq_index_master_list,
            "opti_coords_list": opti_coords_list,
            "opti_coords_list-units": "V",
            "sig_counts": sig_counts.astype(int).tolist(),
            "sig_counts-units": "counts",
            "ref_counts": ref_counts.astype(int).tolist(),
            "ref_counts-units": "counts",
            "norm_avg_sig": norm_avg_sig.astype(float).tolist(),
            "norm_avg_sig-units": "arb",
            "norm_avg_sig_ste": norm_avg_sig_ste.astype(float).tolist(),
            "norm_avg_sig_ste-units": "arb",
        }

        # This will continuously be the same file path so we will overwrite
        # the existing file with the latest version
        file_path = tool_belt.get_file_path(
            __file__, start_timestamp, nv_sig["name"], "incremental"
        )
        tool_belt.save_raw_data(data, file_path)
        tool_belt.save_figure(raw_fig, file_path)

    ### Process and plot the data

    ret_vals = process_counts(sig_counts, ref_counts, num_reps, readout, norm_style)
    (
        sig_counts_avg_kcps,
        ref_counts_avg_kcps,
        norm_avg_sig,
        norm_avg_sig_ste,
    ) = ret_vals

    # Raw data
    kpl.plot_line_update(ax_sig_ref, line_ind=0, y=sig_counts_avg_kcps)
    kpl.plot_line_update(ax_sig_ref, line_ind=1, y=ref_counts_avg_kcps)
    kpl.plot_line_update(ax_norm, y=norm_avg_sig)
    run_indicator_obj.remove()

    # Fits
    fit_fig, _, fit_func, popt, _ = create_fit_figure(
        freq_center, freq_range, num_steps, norm_avg_sig, norm_avg_sig_ste
    )

    ### Clean up, save the data, return

    tool_belt.reset_cfm(cxn)

    timestamp = tool_belt.get_time_stamp()

    # If you update this, also update the incremental data above if necessary
    data = {
        "start_timestamp": start_timestamp,
        "timestamp": timestamp,
        "nv_sig": nv_sig,
        "opti_coords_list": opti_coords_list,
        "opti_coords_list-units": "V",
        "freq_center": freq_center,
        "freq_center-units": "GHz",
        "freq_range": freq_range,
        "freq_range-units": "GHz",
        "uwave_pulse_dur": uwave_pulse_dur,
        "uwave_pulse_dur-units": "ns",
        "state": state.name,
        "num_steps": num_steps,
        "num_reps": num_reps,
        "num_runs": num_runs,
        "uwave_power": uwave_power,
        "uwave_power-units": "dBm",
        "readout": readout,
        "readout-units": "ns",
        "freq_index_master_list": freq_index_master_list,
        "opti_coords_list": opti_coords_list,
        "opti_coords_list-units": "V",
        "sig_counts": sig_counts.astype(int).tolist(),
        "sig_counts-units": "counts",
        "ref_counts": ref_counts.astype(int).tolist(),
        "ref_counts-units": "counts",
        "norm_avg_sig": norm_avg_sig.astype(float).tolist(),
        "norm_avg_sig-units": "arb",
        "norm_avg_sig_ste": norm_avg_sig_ste.astype(float).tolist(),
        "norm_avg_sig_ste-units": "arb",
    }

    nv_name = nv_sig["name"]

    file_path = tool_belt.get_file_path(__file__, timestamp, nv_name)
    data_file_name = file_path.stem()
    tool_belt.save_figure(raw_fig, file_path)
    tool_belt.save_raw_data(data, file_path)

    file_path = tool_belt.get_file_path(__file__, timestamp, nv_name + "-fit")
    tool_belt.save_figure(fit_fig, file_path)

    single_res = return_res_with_error(data)
    return single_res, data_file_name


# endregion


if __name__ == "__main__":

    kpl.init_kplotlib()

    file_name = "2022_11_19-09_14_08-wu-nv1_zfs_vs_t"
    data = tool_belt.get_raw_data(file_name)
    freq_center = data["freq_center"]
    freq_range = data["freq_range"]
    num_steps = data["num_steps"]
    ref_counts = data["ref_counts"]
    sig_counts = data["sig_counts"]
    num_reps = data["num_reps"]
    nv_sig = data["nv_sig"]
    readout = nv_sig["spin_readout_dur"]
    try:
        norm_style = NormStyle[str.upper(nv_sig["norm_style"])]
    except Exception as exc:
        # norm_style = NormStyle.POINT_TO_POINT
        norm_style = NormStyle.SINGLE_VALUED

    ret_vals = process_counts(sig_counts, ref_counts, num_reps, readout, norm_style)
    (
        sig_counts_avg_kcps,
        ref_counts_avg_kcps,
        norm_avg_sig,
        norm_avg_sig_ste,
    ) = ret_vals
    # create_raw_data_figure(
    #     freq_center,
    #     freq_range,
    #     num_steps,
    #     sig_counts_avg_kcps,
    #     ref_counts_avg_kcps,
    #     norm_avg_sig,
    # )
    create_fit_figure(
        freq_center,
        freq_range,
        num_steps,
        norm_avg_sig,
        norm_avg_sig_ste,
    )

    plt.show(block=True)
