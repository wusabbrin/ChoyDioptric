# -*- coding: utf-8 -*-
"""
Widefield extension of the standard optimize in majorroutines

Created Fall 2023

@author: mccambria
"""

import copy
import time

import matplotlib.pyplot as plt
import numpy as np
from numba import njit
from numpy import inf
from scipy.optimize import minimize

from majorroutines.optimize import main, prepare_microscope, stationary_count_lite
from utils import common, widefield
from utils import kplotlib as kpl
from utils import positioning as pos
from utils import tool_belt as tb
from utils.constants import LaserKey

# region Internal


@njit(cache=True)
def _2d_gaussian_exp(x0, y0, sigma, x_crop_mesh, y_crop_mesh):
    return np.exp(
        -(((x_crop_mesh - x0) ** 2) + ((y_crop_mesh - y0) ** 2)) / (2 * sigma**2)
    )


@njit(cache=True)
def _optimize_pixel_cost(fit_params, x_crop_mesh, y_crop_mesh, img_array_crop):
    amp, x0, y0, sigma, offset = fit_params
    gaussian_array = offset + amp * _2d_gaussian_exp(
        x0, y0, sigma, x_crop_mesh, y_crop_mesh
    )
    diff_array = gaussian_array - img_array_crop
    return np.sum(diff_array**2)


@njit(cache=True)
def _optimize_pixel_cost_jac(fit_params, x_crop_mesh, y_crop_mesh, img_array_crop):
    amp, x0, y0, sigma, offset = fit_params
    inv_twice_var = 1 / (2 * sigma**2)
    gaussian_exp = _2d_gaussian_exp(x0, y0, sigma, x_crop_mesh, y_crop_mesh)
    x_diff = x_crop_mesh - x0
    y_diff = y_crop_mesh - y0
    spatial_der_coeff = 2 * amp * gaussian_exp * inv_twice_var
    gaussian_jac_0 = gaussian_exp
    gaussian_jac_1 = spatial_der_coeff * x_diff
    gaussian_jac_2 = spatial_der_coeff * y_diff
    gaussian_jac_3 = amp * gaussian_exp * (x_diff**2 + y_diff**2) / (sigma**3)
    gaussian_jac_4 = 1
    coeff = 2 * ((offset + amp * gaussian_exp) - img_array_crop)
    cost_jac = [
        np.sum(coeff * gaussian_jac_0),
        np.sum(coeff * gaussian_jac_1),
        np.sum(coeff * gaussian_jac_2),
        np.sum(coeff * gaussian_jac_3),
        np.sum(coeff * gaussian_jac_4),
    ]
    return np.array(cost_jac)


# endregion


def optimize_pixel_to_scanning_calibration():
    """
    Update the coordinates for the pair of NVs used to convert between pixel and
    scanning coordinates. Also set the z drift
    """
    # Get the calibration NV sig shells from config

    config = common.get_config_dict()
    config_positioning = config["Positioning"]
    nv1 = config_positioning["laser_scanning_nv1"].copy()
    nv2 = config_positioning["laser_scanning_nv2"].copy()
    calibration_directory = ["State", "WidefieldCalibration"]

    # Calculate the differential drift and assign the NVs updated coordinates

    ret_vals = widefield.get_laser_scanning_params()
    (
        nv1_scanning_coords,
        nv1_pixel_coords,
        nv2_scanning_coords,
        nv2_pixel_coords,
    ) = ret_vals[0:4]
    last_scanning_drift, last_pixel_drift = ret_vals[4:6]

    current_scanning_drift = pos.get_drift()
    current_pixel_drift = widefield.get_pixel_drift()
    diff_scanning_drift = np.array(current_scanning_drift) - np.array(
        last_scanning_drift
    )
    diff_pixel_drift = np.array(current_pixel_drift) - np.array(last_pixel_drift)

    nv1["coords"] = nv1_scanning_coords + diff_scanning_drift
    nv1["pixel_coords"] = nv1_pixel_coords + diff_pixel_drift
    nv2["coords"] = nv2_scanning_coords + diff_scanning_drift
    nv2["pixel_coords"] = nv2_pixel_coords + diff_pixel_drift
    z_initial = nv1["coords"][2]

    # Optimize on the two NVs

    nvs = [nv1, nv2]
    pixel_coords_list = []
    scanning_coords_list = []
    for ind in range(2):
        nv = nvs[ind]

        # Optimize scanning coordinates
        if ind > 0:
            nv["coords"][2] = z_final
        ret_vals = main(nv, drift_adjust=False, set_drift=False)
        scanning_coords = ret_vals[0]
        if ind == 0:
            z_final = scanning_coords[2]
        scanning_coords_list.append(scanning_coords)

        # Optimize pixel coordinates
        img_array = stationary_count_lite(
            nv, scanning_coords, ret_img_array=True, scanning_drift_adjust=False
        )
        pixel_coords = optimize_pixel(
            img_array,
            nv["pixel_coords"],
            set_pixel_drift=False,
            set_scanning_drift=False,
            drift_adjust=False,
        )
        pixel_coords_list.append(pixel_coords)

    # Save the optimized coordinates to the registry
    widefield.set_calibration_coords(
        pixel_coords_list[0],
        scanning_coords_list[0],
        pixel_coords_list[1],
        scanning_coords_list[1],
    )

    # Update the z drift in the registry
    z_change = z_final - z_initial
    current_scanning_drift = pos.get_drift()
    current_scanning_drift = list(current_scanning_drift)
    current_scanning_drift[2] += z_change
    pos.set_drift(current_scanning_drift)

    # Save the current drifts to the registry for the next differential drift calculation
    current_scanning_drift = pos.get_drift()
    current_pixel_drift = widefield.get_pixel_drift()
    common.set_registry_entry(calibration_directory, "DRIFT", current_scanning_drift)
    common.set_registry_entry(calibration_directory, "PIXEL_DRIFT", current_pixel_drift)


def optimize_pixel(nv_sig, do_plot=False):
    img_array = stationary_count_lite(nv_sig, ret_img_array=True)
    return optimize_pixel_with_img_array(img_array, nv_sig, None, do_plot)


def optimize_pixel_with_img_array(
    img_array, nv_sig=None, pixel_coords=None, do_plot=False
):
    if do_plot:
        fig, ax = plt.subplots()
        kpl.imshow(ax, img_array, cbar_label="Counts")

    # Default operations of the routine
    set_pixel_drift = nv_sig is not None
    set_scanning_drift = set_pixel_drift
    pixel_drift_adjust = True
    pixel_drift = None
    radius = None
    do_print = True

    if nv_sig is not None and pixel_coords is not None:
        raise RuntimeError(
            "nv_sig and pixel_coords cannot both be passed to optimize_pixel_with_img_array"
        )

    # Get coordinates
    if nv_sig is not None:
        original_pixel_coords = widefield.get_nv_pixel_coords(nv_sig, False)
        pixel_coords = widefield.get_nv_pixel_coords(
            nv_sig, pixel_drift_adjust, pixel_drift
        )
    if radius is None:
        radius = widefield._get_camera_spot_radius()
    initial_x = pixel_coords[0]
    initial_y = pixel_coords[1]

    # Limit the range to the NV we're looking at
    half_range = radius
    left = round(initial_x - half_range)
    right = round(initial_x + half_range)
    top = round(initial_y - half_range)
    bottom = round(initial_y + half_range)
    x_crop = np.linspace(left, right, right - left + 1)
    y_crop = np.linspace(top, bottom, bottom - top + 1)
    x_crop_mesh, y_crop_mesh = np.meshgrid(x_crop, y_crop)
    img_array_crop = img_array[top : bottom + 1, left : right + 1]

    # Bounds and guesses
    min_img_array_crop = np.min(img_array_crop)
    max_img_array_crop = np.max(img_array_crop)
    bg_guess = min_img_array_crop
    amp_guess = int(img_array[round(initial_y), round(initial_x)] - bg_guess)
    radius_guess = radius / 2
    guess = (amp_guess, initial_x, initial_y, radius_guess, bg_guess)
    diam = radius * 2

    bounds = (
        (0, max_img_array_crop - min_img_array_crop),
        (left, right),
        (top, bottom),
        (1, diam),
        (0, max_img_array_crop),
    )

    args = (x_crop_mesh, y_crop_mesh, img_array_crop)
    res = minimize(
        _optimize_pixel_cost,
        guess,
        bounds=bounds,
        args=args,
        jac=_optimize_pixel_cost_jac,
    )
    popt = res.x

    # Testing
    # opti_pixel_coords = popt[1:3]
    # print(_optimize_pixel_cost(guess, *args))
    # print(_optimize_pixel_cost(popt, *args))
    # print(guess)
    # print(popt)
    # fig, ax = plt.subplots()
    # # gaussian_array = _circle_gaussian(x, y, *popt)
    # # ax.plot(popt[2], popt[1], color="white", zorder=100, marker="o", ms=6)
    # ax.plot(*opti_pixel_coords, color="white", zorder=100, marker="o", ms=6)
    # if type(radius) is list:
    #     for ind in range(len(radius)):
    #         for sub_radius in radius[ind]:
    #             circle = plt.Circle(opti_pixel_coords, sub_radius, fill=False, color="white")
    #             ax.add_patch(circle)
    # else:
    #     circle = plt.Circle(opti_pixel_coords, single_radius, fill=False, color="white")
    #     ax.add_patch(circle)
    # kpl.imshow(ax, img_array)
    # ax.set_xlim([pixel_coords[0] - 15, pixel_coords[0] + 15])
    # ax.set_ylim([pixel_coords[1] + 15, pixel_coords[1] - 15])
    # plt.show(block=True)

    opti_pixel_coords = popt[1:3]
    if set_pixel_drift:
        drift = (np.array(opti_pixel_coords) - np.array(original_pixel_coords)).tolist()
        widefield.set_pixel_drift(drift)
    if set_scanning_drift:
        # widefield.set_scanning_drift_from_pixel_drift()
        widefield.set_all_scanning_drift_from_pixel_drift()
    opti_pixel_coords = opti_pixel_coords.tolist()

    if do_print:
        r_opti_pixel_coords = [round(el, 3) for el in opti_pixel_coords]
        print(f"Optimized pixel coordinates: {r_opti_pixel_coords}")
        counts = widefield.integrate_counts_from_adus(img_array, opti_pixel_coords)
        r_counts = round(counts, 3)
        print(f"Counts at optimized coordinates: {r_counts}")
        print()

    return opti_pixel_coords
