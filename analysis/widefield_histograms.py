# -*- coding: utf-8 -*-
"""
Histogram plots for widefield charge state ssr

Created on November 14th, 2023

@author: mccambria
"""


import matplotlib.pyplot as plt
import numpy as np
import majorroutines.optimize as optimize
from utils import tool_belt as tb
from utils import common
from utils import widefield as widefield_utils
from utils.constants import LaserKey
from utils import kplotlib as kpl
from utils import positioning as pos
from scipy import ndimage
import os
import time
from majorroutines.widefield.optimize_pixel_coords import (
    main_with_img_array as optimize_pixel_coords,
)
from pathlib import Path
from utils.kplotlib import HistType


def main(file_name):
    ### Get the data out

    home = Path.home()

    data = tb.get_raw_data(file_name, "Downloads", home)

    sig_img_array_list = data["sig_img_array_list"]
    ref_img_array_list = data["ref_img_array_list"]

    nv_sig = data["nv_sig"]
    pixel_coords = nv_sig["pixel_coords"]
    # pixel_coords[0] += 15

    num_reps = data["num_reps"]

    ### Process the counts

    sig_counts_list = []
    ref_counts_list = []

    for ind in range(num_reps):
        sig_img_array = sig_img_array_list[ind]
        sig_counts = widefield_utils.counts_from_img_array(
            sig_img_array, pixel_coords, drift_adjust=False
        )
        ref_img_array = ref_img_array_list[ind]
        ref_counts = widefield_utils.counts_from_img_array(
            ref_img_array, pixel_coords, drift_adjust=False
        )
        sig_counts_list.append(sig_counts)
        ref_counts_list.append(ref_counts)

    ### Plot images

    sig_img_array = np.sum(sig_img_array_list, axis=0) / num_reps
    ref_img_array = np.sum(ref_img_array_list, axis=0) / num_reps

    fig, ax = plt.subplots()
    widefield_utils.imshow(ax, sig_img_array, title="sig")
    fig, ax = plt.subplots()
    widefield_utils.imshow(ax, ref_img_array, title="ref")
    fig, ax = plt.subplots()
    widefield_utils.imshow(ax, sig_img_array - ref_img_array, title="diff")

    ### Plot histograms

    num_bins = 50

    labels = ["sig", "ref"]
    counts_lists = [sig_counts_list, ref_counts_list]
    fig, ax = plt.subplots()
    ax.set_title(f"Ionization histogram, {num_bins} bins, {num_reps} reps")
    ax.set_xlabel(f"Integrated counts")
    ax.set_ylabel("Number of occurrences")
    for ind in range(2):
        kpl.histogram(
            ax, counts_lists[ind], HistType.STEP, nbins=num_bins, label=labels[ind]
        )
    ax.legend()


if __name__ == "__main__":
    file_name = "2023_11_14-14_41_51-johnson-nv0_2023_11_09-diff"

    kpl.init_kplotlib()

    main(file_name)
    plt.show(block=True)
