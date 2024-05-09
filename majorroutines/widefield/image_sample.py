# -*- coding: utf-8 -*-
"""
Illuminate an area, collecting onto the camera

Created on April 9th, 2019

@author: mccambria
"""

import sys
import time
from multiprocessing import Pool

import matplotlib.pyplot as plt
import numpy as np

import majorroutines.optimize as optimize
from majorroutines.widefield.optimize import optimize_pixel
from utils import common, widefield
from utils import data_manager as dm
from utils import kplotlib as kpl
from utils import positioning as pos
from utils import tool_belt as tb
from utils.constants import LaserKey, NVSig


def single_nv(nv_sig, num_reps=1):
    nv_list = [nv_sig]
    return _nv_list_sub(nv_list, "single_nv", num_reps=num_reps)


def single_nv_ionization(nv_sig, num_reps=1):
    caller_fn_name = "single_nv_ionization"
    return _charge_state_prep_diff(nv_sig, caller_fn_name, num_reps)


def single_nv_polarization(nv_sig, num_reps=1):
    caller_fn_name = "single_nv_polarization"
    return _charge_state_prep_diff(nv_sig, caller_fn_name, num_reps)


def _charge_state_prep_diff(nv_sig, caller_fn_name, num_reps=1):
    if caller_fn_name == "single_nv_polarization":
        do_polarize_sig = True
        do_polarize_ref = False
        do_ionize_sig = False
        do_ionize_ref = False
    elif caller_fn_name == "single_nv_ionization":
        do_polarize_sig = True
        do_polarize_ref = True
        do_ionize_sig = True
        do_ionize_ref = False

    # Do the experiments
    sig_img_array = _charge_state_prep(
        nv_sig,
        caller_fn_name,
        num_reps,
        do_polarize=do_polarize_sig,
        do_ionize=do_ionize_sig,
    )
    ref_img_array = _charge_state_prep(
        nv_sig,
        caller_fn_name,
        num_reps,
        do_polarize=do_polarize_ref,
        do_ionize=do_ionize_ref,
    )

    # Calculate the difference and save
    fig, ax = plt.subplots()
    diff = sig_img_array - ref_img_array
    kpl.imshow(ax, diff, title="Difference", cbar_label="ADUs")
    timestamp = dm.get_time_stamp()
    file_path = dm.get_file_path(__file__, timestamp, nv_sig["name"])
    dm.save_figure(fig, file_path)

    ### Get the pixel values of the NV in both images and a background level

    bg_offset = [10, -10]
    img_arrays = [sig_img_array, ref_img_array]
    titles = ["Signal", "Reference"]

    for ind in range(2):
        img_array = img_arrays[ind]
        title = titles[ind]

        nv_pixel_coords = optimize_pixel(
            img_array,
            nv_sig,
            set_scanning_drift=False,
            set_pixel_drift=False,
            pixel_drift_adjust=False,
        )
        nv_counts = widefield.counts_from_img_array(
            img_array, nv_pixel_coords, drift_adjust=False
        )
        bg_pixel_coords = [
            nv_pixel_coords[0] + bg_offset[0],
            nv_pixel_coords[1] + bg_offset[1],
        ]
        bg_counts = widefield.counts_from_img_array(
            img_array, bg_pixel_coords, drift_adjust=False
        )

        print(title)
        print(f"nv_counts: {nv_counts}")
        print(f"bg_counts: {bg_counts}")
        print(f"diff: {nv_counts - bg_counts}")
        print()


def _charge_state_prep(
    nv_sig,
    caller_fn_name,
    num_reps=1,
    save_dict=None,
    do_polarize=False,
    do_ionize=False,
):
    return main(
        nv_sig,
        caller_fn_name,
        num_reps=num_reps,
        save_dict=save_dict,
        do_polarize=do_polarize,
        do_ionize=do_ionize,
    )


def nv_list(nv_list, num_reps=1):
    save_dict = {"nv_list": nv_list}
    return _nv_list_sub(nv_list, "nv_list", save_dict, num_reps)


def _nv_list_sub(nv_list, caller_fn_name, save_dict=None, num_reps=1):
    nv_sig = nv_list[0]
    laser_key = LaserKey.IMAGING
    laser_dict = tb.get_optics_dict(laser_key)
    laser_name = laser_dict["name"]
    adj_coords_list = [pos.get_nv_coords(nv, laser_name) for nv in nv_list]
    x_coords = [coords[0] for coords in adj_coords_list]
    y_coords = [coords[1] for coords in adj_coords_list]
    return main(nv_sig, caller_fn_name, num_reps, x_coords, y_coords, save_dict)


def widefield_image(nv_sig, num_reps=1):
    return main(nv_sig, "widefield", num_reps)


def scanning(nv_sig, x_range, y_range, num_steps):
    laser_key = LaserKey.IMAGING
    laser_dict = tb.get_optics_dict(laser_key)
    laser_name = laser_dict["name"]
    center_coords = pos.get_nv_coords(nv_sig, laser_name)
    x_center, y_center = center_coords[0:2]
    ret_vals = pos.get_scan_grid_2d(
        x_center, y_center, x_range, y_range, num_steps, num_steps
    )
    x_coords, y_coords, x_coords_1d, y_coords_1d, _ = ret_vals
    x_coords = list(x_coords)
    y_coords = list(y_coords)
    save_dict = {
        "x_range": x_range,
        "y_range": y_range,
        "x_coords_1d": x_coords_1d,
        "y_coords_1d": y_coords_1d,
    }
    num_reps = 1
    return main(nv_sig, "scanning", num_reps, x_coords, y_coords, save_dict)


def main(
    nv_sig: NVSig,
    caller_fn_name,
    num_reps=1,
    x_coords=None,
    y_coords=None,
    save_dict=None,
    do_polarize=False,
    do_ionize=False,
):
    ### Some initial setup

    tb.reset_cfm()
    laser_key = (
        LaserKey.WIDEFIELD_IMAGING
        if caller_fn_name == "widefield"
        else LaserKey.IMAGING
    )
    optimize.prepare_microscope(nv_sig)
    camera = tb.get_server_camera()
    pulse_gen = tb.get_server_pulse_gen()

    laser_dict = tb.get_optics_dict(laser_key)
    readout_laser = laser_dict["name"]

    pos.set_xyz_on_nv(nv_sig)

    ### Load the pulse generator

    readout = laser_dict["duration"]
    readout_ms = readout / 10**6

    if caller_fn_name in ["scanning", "nv_list", "single_nv"]:
        seq_args = [readout, readout_laser, list(x_coords), list(y_coords)]
        seq_file = "simple_readout-scanning.py"

    elif caller_fn_name == "widefield":
        seq_args = [readout, readout_laser]
        seq_file = "simple_readout-widefield.py"

    elif caller_fn_name in ["single_nv_ionization", "single_nv_polarization"]:
        nv_list = [nv_sig]
        pol_coords_list = widefield.get_pol_coords_list(nv_list)
        ion_coords_list = widefield.get_ion_coords_list(nv_list)
        seq_args = [pol_coords_list, ion_coords_list]
        raise RuntimeError(
            "The sequence simple_readout-charge_state_prep needs to be updated "
            "to match the format of the seq_args returned by get_base_scc_seq_args"
        )
        seq_args.extend([do_polarize, do_ionize])
        seq_file = "simple_readout-charge_state_prep.py"

    # print(seq_args)
    # print(seq_file)
    # return

    ### Set up the image display

    title = f"{caller_fn_name}, {readout_laser}, {readout_ms} ms"

    ### Collect the data

    img_array_list = []

    def rep_fn(rep_ind):
        img_str = camera.read()
        sub_img_array, _ = widefield.img_str_to_array(img_str)
        img_array_list.append(sub_img_array)

    seq_args_string = tb.encode_seq_args(seq_args)
    pulse_gen.stream_load(seq_file, seq_args_string, num_reps)
    camera.arm()
    widefield.rep_loop(num_reps, rep_fn)
    camera.disarm()

    img_array = np.mean(img_array_list, axis=0)
    fig, ax = plt.subplots()
    kpl.imshow(ax, img_array, title=title, cbar_label="ADUs")

    ### Clean up and save the data

    tb.reset_cfm()

    plt.show()

    kpl.show()

    timestamp = dm.get_time_stamp()
    raw_data = {
        "timestamp": timestamp,
        "caller_fn_name": caller_fn_name,
        "nv_sig": nv_sig,
        "num_reps": num_reps,
        "readout": readout_ms,
        "readout-units": "ms",
        "title": title,
        "img_array": img_array,
        "img_array-units": "counts",
    }
    if save_dict is not None:
        raw_data |= save_dict  # Add in the passed info to save

    nv_name = nv_sig.name
    file_path = dm.get_file_path(__file__, timestamp, nv_name)
    dm.save_figure(fig, file_path)
    dm.save_raw_data(raw_data, file_path, keys_to_compress=["img_array"])

    return img_array


if __name__ == "__main__":
    kpl.init_kplotlib()

    data = dm.get_raw_data(file_id=1525081713075, load_npz=True)
    img_array = np.array(data["ref_img_array"])
    nv_list = data["nv_list"]

    # img_array = widefield.adus_to_photons(img_array)

    # Clean up dead pixel by taking average of nearby pixels
    # dead_pixel = [142, 109]
    # dead_pixel_x = dead_pixel[1]
    # dead_pixel_y = dead_pixel[0]
    # img_array[dead_pixel_y, dead_pixel_x] = np.mean(
    #     img_array[
    #         dead_pixel_y - 1 : dead_pixel_y + 1 : 2,
    #         dead_pixel_x - 1 : dead_pixel_x + 1 : 2,
    #     ]
    # )

    fig, ax = plt.subplots()
    kpl.imshow(ax, img_array, cbar_label="Photons")
    scale = widefield.get_camera_scale()
    kpl.scale_bar(ax, scale, "1 µm", kpl.Loc.UPPER_RIGHT)

    widefield.draw_circles_on_nvs(ax, nv_list, drift=(-38, -19))

    plt.show(block=True)
