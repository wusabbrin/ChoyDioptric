# -*- coding: utf-8 -*-
"""
Optimize on an NV

Largely rewritten August 16th, 2023

@author: mccambria
"""


# region Imports and constant

import copy
import time

import matplotlib.pyplot as plt
import numpy as np
from numpy import inf
from scipy.optimize import curve_fit

from utils import common, widefield
from utils import data_manager as dm
from utils import kplotlib as kpl
from utils import positioning as pos
from utils import tool_belt as tb
from utils.constants import (
    CollectionMode,
    ControlMode,
    CoordsKey,
    CountFormat,
    LaserKey,
    LaserPosMode,
    NVSig,
)

# endregion
# region Plotting functions


def _create_figure():
    kpl.init_kplotlib(kpl.Size.SMALL)
    config = common.get_config_dict()
    fig, axes_pack = plt.subplots(1, 3, figsize=kpl.double_figsize)
    axis_titles = ["X axis", "Y axis", "Z axis"]
    for ind in range(3):
        ax = axes_pack[ind]
        ax.set_title(axis_titles[ind])
        xlabel = pos.get_axis_units(ind)
        ax.set_xlabel(xlabel)
        count_format = config["count_format"]
        if count_format == CountFormat.RAW:
            ylabel = "Counts"
        elif count_format == CountFormat.KCPS:
            ylabel = "Count rate (kcps)"
        ax.set_ylabel(ylabel)
    return fig


def _update_figure(fig, axis_ind, scan_vals, count_vals, text=None):
    axes = fig.get_axes()
    ax = axes[axis_ind]
    ax.plot(scan_vals, count_vals)
    if text is not None:
        kpl.anchored_text(ax, text, kpl.Loc.LOWER_RIGHT)
    kpl.show()


def _fit_gaussian(scan_vals, count_vals, axis_ind, positive_amplitude=True, fig=None):
    # Param order: amplitude, center, sd width, offset
    fit_func = tb.gaussian
    bg_guess = min(count_vals) if positive_amplitude else max(count_vals)
    low = np.min(scan_vals)
    high = np.max(scan_vals)
    scan_range = high - low
    center_guess = (high + low) / 2
    amplitude_guess = (
        max(count_vals) - bg_guess if positive_amplitude else min(count_vals) - bg_guess
    )
    guess = (amplitude_guess, center_guess, scan_range / 3, bg_guess)
    popt = None
    try:
        amplitude_lower = 0 if positive_amplitude else -inf
        amplitude_upper = inf if positive_amplitude else 0
        low_bounds = [amplitude_lower, low, 0, 0]
        high_bounds = [amplitude_upper, high, inf, inf]
        bounds = (low_bounds, high_bounds)
        popt, pcov = curve_fit(fit_func, scan_vals, count_vals, p0=guess, bounds=bounds)
        # Consider it a failure if we railed or somehow got out of bounds
        for ind in range(len(popt)):
            param = popt[ind]
            if not (low_bounds[ind] < param < high_bounds[ind]):
                popt = None
    except Exception as ex:
        print(ex)
        # pass

    if popt is None:
        print("Optimization failed for axis {}".format(axis_ind))

    # Plot
    if (fig is not None) and (popt is not None):
        # Plot the fit
        linspace_scan_vals = np.linspace(low, high, num=1000)
        fit_count_vals = fit_func(linspace_scan_vals, *popt)
        # Add popt to the axes
        text = "a={:.3f}\n $\mu$={:.3f}\n $\sigma$={:.3f}\n offset={:.3f}".format(*popt)
        _update_figure(fig, axis_ind, linspace_scan_vals, fit_count_vals, text)

    center = None
    if popt is not None:
        center = popt[1]

    return center


# endregion
# region Private axis optimization functions


def _read_counts_counter_stream(axis_ind=None, scan_vals=None):
    if axis_ind is not None:
        axis_stream_fn = pos.get_axis_stream_fn(axis_ind)
        axis_stream_fn(scan_vals)
    counter = tb.get_server_counter()
    pulse_gen = tb.get_server_pulse_gen()
    counts = []
    num_read_so_far = 0
    counter.start_tag_stream()
    if axis_ind is not None:
        num_steps = len(scan_vals)
    else:
        num_steps = 1
    pulse_gen.stream_start(num_steps)
    while num_read_so_far < num_steps:
        if tb.safe_stop():
            break
        new_samples = counter.read_counter_simple()
        num_new_samples = len(new_samples)
        if num_new_samples > 0:
            counts.extend(new_samples)
            num_read_so_far += num_new_samples
    counter.stop_tag_stream()
    return [np.array(counts, dtype=int)]


def _read_counts_counter_step(axis_ind=None, scan_vals=None):
    if axis_ind is not None:
        axis_write_fn = pos.get_axis_write_fn(axis_ind)
    counter = tb.get_server_counter()
    pulse_gen = tb.get_server_pulse_gen()
    counter.start_tag_stream()
    counts = []
    for ind in range(len(scan_vals)):
        if tb.safe_stop():
            break
        if axis_ind is not None:
            axis_write_fn(scan_vals[ind])
        pulse_gen.stream_start(1)
        new_samples = counter.read_counter_simple(1)
        counts.append(np.average(new_samples))
    counter.stop_tag_stream()
    return [np.array(counts, dtype=int)]


def _read_counts_camera_step(nv_sig, laser_key, axis_ind=None, scan_vals=None):
    if axis_ind is not None:
        axis_write_fn = pos.get_axis_write_fn(axis_ind)
    widefield.get_nv_pixel_coords(nv_sig)
    camera = tb.get_server_camera()
    pulse_gen = tb.get_server_pulse_gen()
    counts = []
    camera.arm()
    for ind in range(len(scan_vals)):
        if tb.safe_stop():
            break
        if axis_ind is not None:
            axis_write_fn(scan_vals[ind])
        pulse_gen.stream_start()
        img_str = camera.read()
        img_array = widefield.img_str_to_array(img_str)
        sample = widefield.integrate_counts_from_adus(img_array, pixel_coords)
        counts.append(sample)
    camera.disarm()
    return [np.array(counts, dtype=int), img_array]


def _read_counts_camera_sequence(
    nv_sig,
    laser_key,
    coords=None,
    coords_key=CoordsKey.GLOBAL,
    axis_ind=None,
    scan_vals=None,
):
    """
    Specific function for widefield setup - XY control from AODs,
    Z control from objective piezo, imaged onto a camera
    """
    # Basic setup
    pixel_coords = widefield.get_nv_pixel_coords(nv_sig)
    camera = tb.get_server_camera()
    pulse_gen = tb.get_server_pulse_gen()
    if axis_ind is not None:
        num_steps = len(scan_vals)
    else:
        num_steps = 1

    # Sequence setup

    if laser_key == LaserKey.IMAGING:
        imaging_laser_dict = tb.get_laser_dict(LaserKey.IMAGING)
        imaging_laser_name = imaging_laser_dict["name"]
        imaging_readout = imaging_laser_dict["duration"]
        if coords is None or coords_key != laser_key:
            laser_coords = pos.get_nv_coords(nv_sig, imaging_laser_name)
        else:
            laser_coords = coords
        seq_args = [
            imaging_readout,
            imaging_laser_name,
            [laser_coords[0]],
            [laser_coords[1]],
        ]
        seq_file_name = "simple_readout-scanning.py"
        num_reps = 1
    elif laser_key == LaserKey.IONIZATION:
        seq_args = widefield.get_base_scc_seq_args([nv_sig])
        seq_file_name = "optimize_ionization_laser_coords.py"
        num_reps = 50
    if axis_ind is None or axis_ind == 2:
        seq_args_string = tb.encode_seq_args(seq_args)
        pulse_gen.stream_load(seq_file_name, seq_args_string, num_reps)
    # For z the sequence is the same every time and z is moved manually
    if axis_ind == 2:
        axis_write_fn = pos.get_axis_write_fn(axis_ind)

    # print(seq_args)
    # return

    # Collect the counts
    counts = []
    camera.arm()
    for ind in range(num_steps):
        if tb.safe_stop():
            break

        # Modify the sequence as necessary and start the pulse generator
        if axis_ind is not None:
            val = scan_vals[ind]
            if axis_ind in [0, 1]:
                if laser_key == LaserKey.IMAGING:
                    seq_args[-2 + axis_ind] = [val]
                elif laser_key == LaserKey.IONIZATION:
                    seq_args[1][0][axis_ind] = val
                seq_args_string = tb.encode_seq_args(seq_args)
                # print(seq_args)

                pulse_gen.stream_load(seq_file_name, seq_args_string, num_reps)
            elif axis_ind == 2:
                axis_write_fn(val)
                # print(val)

        # Read the camera images
        img_array_list = []

        def rep_fn(rep_ind):
            img_str = camera.read()
            sub_img_array = widefield.img_str_to_array(img_str)
            img_array_list.append(sub_img_array)

        widefield.rep_loop(num_reps, rep_fn)

        # Process the result
        img_array = np.mean(img_array_list, axis=0)
        sample = widefield.integrate_counts_from_adus(img_array, pixel_coords)
        counts.append(sample)

    camera.disarm()

    return [np.array(counts, dtype=int), img_array]


def _optimize_on_axis(nv_sig: NVSig, laser_key, coords, coords_key, axis_ind, fig=None):
    """Optimize on just one axis (0, 1, 2) for (x, y, z)"""

    ### Basic setup and definitions

    num_steps = 20
    # config = common.get_config_dict()
    # laser_dict = tb.get_laser_dict(laser_key)
    scan_range = pos.get_axis_optimize_range(axis_ind, coords_key)

    # The opti_offset flag allows a different NV at a specified offset to be used as a proxy for
    # optimizing on the actual target NV. Useful if the real target NV is poorly isolated.
    # Only works with global coordinates
    opti_offset = nv_sig.opti_offset
    if opti_offset is not None and coords_key == CoordsKey.GLOBAL:
        coords += np.array(opti_offset)
    axis_center = coords[axis_ind]
    scan_vals = pos.get_scan_1d(axis_center, scan_range, num_steps)

    ### Record the counts

    ret_vals = _read_counts(nv_sig, laser_key, coords, coords_key, axis_ind, scan_vals)
    counts = ret_vals[0]

    ### Plot, fit, return

    f_counts = counts
    # count_format = config["count_format"]
    # if count_format == CountFormat.RAW:
    #     f_counts = counts
    # elif count_format == CountFormat.KCPS:
    #     readout = laser_dict["duration"]
    #     f_counts = (counts / 1000) / (readout / 10**9)
    if fig is not None:
        _update_figure(fig, axis_ind, scan_vals, f_counts)
    positive_amplitude = laser_key != LaserKey.IONIZATION
    opti_coord = _fit_gaussian(scan_vals, f_counts, axis_ind, positive_amplitude, fig)

    return opti_coord, scan_vals, f_counts


def _read_counts(
    nv_sig,
    laser_key=LaserKey.IMAGING,
    coords=None,
    coords_key=CoordsKey.GLOBAL,
    axis_ind=None,
    scan_vals=None,
):
    # How we conduct the scan depends on the config
    config = common.get_config_dict()
    collection_mode = config["collection_mode"]
    pulse_gen = tb.get_server_pulse_gen()

    laser_dict = tb.get_laser_dict(laser_key)
    laser_name = laser_dict["name"]
    laser_power = tb.set_laser_power(nv_sig, laser_key)
    if axis_ind is not None:
        delay = pos.get_axis_delay(axis_ind, coords_key=coords_key)
        control_mode = pos.get_axis_control_mode(axis_ind, coords_key)

    # Position us at the starting point
    if coords is not None:
        if scan_vals is None:
            pos.set_xyz(coords, coords_key)
        else:
            start_coords = np.copy(coords)
            start_coords[axis_ind] = np.min(scan_vals)
            pos.set_xyz(start_coords, coords_key)

    # Assume the lasers are sequence controlled if using camera
    if collection_mode == CollectionMode.CAMERA:
        ret_vals = _read_counts_camera_sequence(
            nv_sig, laser_key, coords, coords_key, axis_ind, scan_vals
        )

    else:
        if laser_key != LaserKey.IMAGING:
            raise NotImplementedError(
                "Optimization is currently only implemented for imaging lasers."
            )
        seq_file_name = "simple_readout.py"
        readout = laser_dict["duration"]
        seq_args = [delay, readout, laser_name, laser_power]
        seq_args_string = tb.encode_seq_args(seq_args)

        pulse_gen.stream_load(seq_file_name, seq_args_string)

        if collection_mode == CollectionMode.COUNTER:
            if control_mode == ControlMode.STEP:
                ret_vals = _read_counts_counter_step(axis_ind, scan_vals)
            elif control_mode == ControlMode.STREAM:
                ret_vals = _read_counts_counter_stream(axis_ind, scan_vals)

        elif collection_mode == CollectionMode.CAMERA:
            ret_vals = _read_counts_camera_step(nv_sig, laser_key, axis_ind, scan_vals)

    return ret_vals


# endregion
# region General public functions


def stationary_count_lite(
    nv_sig,
    laser_key=LaserKey.IMAGING,
    coords=None,
    coords_key=CoordsKey.GLOBAL,
    ret_img_array=False,
):
    # Set up
    config = common.get_config_dict()
    tb.set_filter(nv_sig, laser_key)
    prepare_microscope(nv_sig)

    ret_vals = _read_counts(nv_sig, laser_key, coords, coords_key)
    counts = ret_vals[0]

    # Return
    avg_counts = np.average(counts)
    config = common.get_config_dict()
    count_format = config["count_format"]
    if ret_img_array:
        return ret_vals[1]
    if count_format == CountFormat.RAW:
        return avg_counts
    elif count_format == CountFormat.KCPS and laser_key == LaserKey.IMAGING:
        readout = tb.get_common_duration("imaging_readout")
        count_rate = (avg_counts / 1000) / (readout / 10**9)
        return count_rate


def prepare_microscope(nv_sig: NVSig):
    """
    Prepares the microscope for a measurement. In particular, sets up the
    optics (filters, etc) and magnet, and sets the global coordinates. The
    laser set up must be handled by each routine
    """

    # MCC to do
    # Set filters according to config

    # Set the global positioners on this NV
    pos.set_xyz_on_nv(nv_sig)

    # Set the magnet rotation mount to the correct angle
    magnet_angle = nv_sig.magnet_angle
    if magnet_angle is not None:
        rotation_stage_server = tb.get_server_magnet_rotation()
        rotation_stage_server.set_angle(magnet_angle)


def main(
    nv_sig: NVSig,
    laser_key=LaserKey.IMAGING,
    coords_key=CoordsKey.GLOBAL,
    axes_to_optimize=[0, 1, 2],
    no_crash=False,
    do_plot=False,
):
    # If optimize is disabled, just do prep and return
    if nv_sig.disable_opt:
        prepare_microscope(nv_sig)
        return [], None

    ### Setup

    # Default routine operations
    set_drift = True
    drift_adjust = True
    do_save = do_plot

    tb.reset_cfm()
    tb.init_safe_stop()
    config = common.get_config_dict()

    initial_coords = pos.get_nv_coords(nv_sig, coords_key, drift_adjust)
    expected_counts = nv_sig.expected_counts
    if expected_counts is not None:
        lower_bound = 0.9 * expected_counts
        upper_bound = 1.2 * expected_counts

    start_time = time.time()

    # Filter sets for imaging
    tb.set_filter(nv_sig, "collection")
    tb.set_filter(nv_sig, laser_key)

    # Default values for status variables
    opti_succeeded = False
    opti_necessary = True
    opti_coords = initial_coords.copy()

    def count_check(coords):
        return stationary_count_lite(nv_sig, laser_key, coords, coords_key)

    ### Check if we even need to optimize by reading counts at current coordinates

    count_format = config["count_format"]
    if count_format == CountFormat.RAW:
        print(f"Expected counts: {expected_counts}")
    elif count_format == CountFormat.KCPS:
        print(f"Expected count rate: {expected_counts} kcps")
    current_counts = count_check(initial_coords)
    print(f"Counts at initial coordinates: {current_counts}")
    if (expected_counts is not None) and (lower_bound < current_counts < upper_bound):
        print("No need to optimize.")
        opti_necessary = False

    ### Try to optimize.

    if opti_necessary:
        # Check if z optimization is disabled
        if nv_sig.disable_z_opt and 2 in axes_to_optimize:
            axes_to_optimize.remove(2)

        # Loop through attempts until we succeed or give up
        num_attempts = 10
        for ind in range(num_attempts):
            ### Attempt setup

            if opti_succeeded or tb.safe_stop():
                break
            print(f"Attempt number {ind+1}")

            # Create a figure with a plot for each axis
            fig = _create_figure() if do_plot else None

            # Tracking lists for each axis
            opti_coords = initial_coords.copy()
            scan_vals_by_axis = [None] * 3
            counts_by_axis = [None] * 3
            axis_failed = False

            ### Loop through the axes

            for axis_ind in axes_to_optimize:
                # Check if z optimization is necessary after xy optimization
                if axis_ind == 2 and axes_to_optimize == [0, 1, 2]:
                    current_counts = count_check(opti_coords)
                    if lower_bound < current_counts < upper_bound:
                        print("Z optimization unnecessary.")
                        scan_vals_by_axis.append(np.array([]))
                        opti_succeeded = True
                        break

                # Perform the optimization
                ret_vals = _optimize_on_axis(
                    nv_sig, laser_key, opti_coords, coords_key, axis_ind, fig
                )
                opti_coord = ret_vals[0]
                if opti_coord is not None:
                    opti_coords[axis_ind] = opti_coord
                else:
                    axis_failed = True
                scan_vals_by_axis[axis_ind] = ret_vals[1]
                counts_by_axis[axis_ind] = ret_vals[2]

            ### Attempt wrap-up

            # Try again if any individual axis failed
            if axis_failed:
                continue

            # Check the counts - if the threshold is not set, we just do one pass and succeed
            current_counts = count_check(opti_coords)
            print(f"Value at optimized coordinates: {round(current_counts, 1)}")
            if expected_counts is None:
                opti_succeeded = True
            else:
                if lower_bound < current_counts < upper_bound:
                    opti_succeeded = True
                else:
                    print("Value at optimized coordinates out of bounds.")

    ### Calculate the drift relative to the passed coordinates

    passed_coords = pos.get_nv_coords(nv_sig, coords_key, drift_adjust=False)
    drift = []
    for ind in range(len(passed_coords)):
        opti_coord = opti_coords[ind]
        passed_coord = passed_coords[ind]
        if opti_coord is None or passed_coord is None:
            drift_coord = 0.0
        else:
            drift_coord = opti_coords[ind] - passed_coords[ind]
        drift.append(drift_coord)
    if opti_succeeded and set_drift:
        pos.set_drift(drift, coords_key=coords_key)

    ### Report the results and set to the optimized coordinates if requested

    if opti_succeeded:
        print("Optimization succeeded!")
    prepare_microscope(nv_sig)
    if not opti_necessary or opti_succeeded:
        r_opti_coords = []
        r_drift = []
        for ind in range(len(drift)):
            opti_coord = opti_coords[ind]
            drift_coord = drift[ind]
            if opti_coord is None:
                r_opti_coords.append(None)
            else:
                r_opti_coords.append(round(opti_coord, 3))
            if drift_coord is None:
                r_drift.append(None)
            else:
                r_drift.append(round(drift_coord, 3))
        print(f"Optimized coordinates: {r_opti_coords}")
        print(f"Drift: {r_drift}")
    # Just crash if we failed
    elif not no_crash:
        raise RuntimeError("Optimization failed.")

    print("\n")

    ### Clean up and save the data

    tb.reset_cfm()
    end_time = time.time()
    time_elapsed = end_time - start_time

    if do_save and opti_necessary:
        timestamp = dm.get_time_stamp()
        for ind in range(3):
            scan_vals = scan_vals_by_axis[ind]
            if scan_vals is not None:
                scan_vals = scan_vals.tolist()
            counts = counts_by_axis[ind]
            if counts is not None:
                counts = counts.tolist()
        rawData = {
            "timestamp": timestamp,
            "time_elapsed": time_elapsed,
            "nv_sig": nv_sig,
            "opti_coords": opti_coords,
            "axes_to_optimize": axes_to_optimize,
            "laser_key": laser_key,
            "x_scan_vals": scan_vals_by_axis[0],
            "y_scan_vals": scan_vals_by_axis[1],
            "z_scan_vals": scan_vals_by_axis[2],
            "x_counts": counts_by_axis[0],
            "x_counts-units": "number",
            "y_counts": counts_by_axis[1],
            "y_counts-units": "number",
            "z_counts": counts_by_axis[2],
            "z_counts-units": "number",
        }

        nv_name = nv_sig.name
        filePath = dm.get_file_path(__file__, timestamp, nv_name)
        if fig is not None:
            dm.save_figure(fig, filePath)
        dm.save_raw_data(rawData, filePath)

    # Return the optimized coordinates we found and the final counts
    return opti_coords, current_counts


# endregion

if __name__ == "__main__":
    file_name = "2023_09_21-21_07_51-widefield_calibration_nv1"
    data = dm.get_raw_data(file_name)
    laser_key = data["laser_key"]
    positive_amplitude = laser_key != LaserKey.IONIZATION

    fig = _create_figure()
    nv_sig = data["nv_sig"]
    keys = ["x", "y", "z"]
    for axis_ind in range(3):
        scan_vals = data[f"{keys[axis_ind]}_scan_vals"]
        count_vals = data[f"{keys[axis_ind]}_counts"]
        _update_figure(fig, axis_ind, scan_vals, count_vals)
        _fit_gaussian(scan_vals, count_vals, axis_ind, positive_amplitude, fig)

    plt.show(block=True)
