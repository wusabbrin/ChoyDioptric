# -*- coding: utf-8 -*-
"""
Intro figure for zfs vs t paper

Created on March 28th, 2023

@author: mccambria
"""


# region Import and constants

import numpy as np
from utils import common
from majorroutines.pulsed_resonance import return_res_with_error
import majorroutines.pulsed_resonance as pesr
import utils.tool_belt as tool_belt
from utils.tool_belt import bose
import matplotlib.pyplot as plt
from utils import kplotlib as kpl
from utils.kplotlib import KplColors
import matplotlib as mpl
from matplotlib.collections import PolyCollection
from scipy.optimize import curve_fit
import csv
import pandas as pd
import sys
from analysis import three_level_rabi
from figures.zfs_vs_t.zfs_vs_t_main import get_data_points
from figures.zfs_vs_t.thermal_expansion import fit_double_occupation


# endregion


def main():

    setpoint_temps = ["", 350, 400, 450]  # In increasing temp order
    skip_lambda = (
        lambda point: point["Skip"]
        or point["Sample"] != "Wu"
        or point["Setpoint temp (K)"] not in setpoint_temps
        or point["NV"] != "nv11_zfs_vs_t"
    )
    data_points = get_data_points(skip_lambda)

    # Blue, green, yellow, red
    edgecolors = ["#4db449", "#f1aa30", "#fb2e18", "#8c564b"]
    facecolors = [kpl.lighten_color_hex(el) for el in edgecolors]

    narrow_figsize = (0.55 * kpl.figsize[0], kpl.figsize[1])
    fig, ax = plt.subplots(figsize=narrow_figsize)

    for ind in [3, 2, 1, 0]:

        data_point = data_points[ind]

        fig_file = data_point["ZFS file"]
        edgecolor = edgecolors[ind]
        facecolor = facecolors[ind]
        temp = data_point["Monitor temp (K)"]

        popt = (
            data_point["Contrast"],
            data_point["Width (MHz)"],
            data_point["ZFS (GHz)"],
            data_point["Splitting (MHz)"],
        )

        data = tool_belt.get_raw_data(fig_file)
        freq_center = data["freq_center"]
        freq_range = data["freq_range"]
        num_steps = data["num_steps"]
        freqs = pesr.calculate_freqs(freq_center, freq_range, num_steps)
        smooth_freqs = pesr.calculate_freqs(freq_center, freq_range, 100)

        ref_counts = data["ref_counts"]
        sig_counts = data["sig_counts"]
        num_reps = data["num_reps"]
        nv_sig = data["nv_sig"]
        sample = nv_sig["name"].split("-")[0]
        readout = nv_sig["spin_readout_dur"]
        uwave_pulse_dur = data["uwave_pulse_dur"]

        try:
            norm_style = tool_belt.NormStyle[str.upper(nv_sig["norm_style"])]
        except Exception as exc:
            # norm_style = NormStyle.POINT_TO_POINT
            norm_style = tool_belt.NormStyle.SINGLE_VALUED

        ret_vals = tool_belt.process_counts(
            sig_counts, ref_counts, num_reps, readout, norm_style
        )
        (
            sig_counts_avg_kcps,
            ref_counts_avg_kcps,
            norm_avg_sig,
            norm_avg_sig_ste,
        ) = ret_vals

        fit_func = lambda f: 1 - three_level_rabi.coherent_line(
            f, *popt, uwave_pulse_dur
        )

        offset = 0.25 * ind
        # offset = 0
        kpl.plot_line(
            ax,
            freqs,
            offset + norm_avg_sig,
            color=edgecolor,
            # markerfacecolor=facecolor,
            label=f"{int(temp)} K",
            # size=kpl.Size.SMALL,
        )
        kpl.plot_line(
            ax,
            smooth_freqs,
            offset + fit_func(smooth_freqs),
            color=KplColors.DARK_GRAY,
            # color=facecolor,
        )
        # ax.legend(loc="upper right")
        ax.legend(handlelength=1.5, borderpad=0.3, borderaxespad=0.3, handletextpad=0.6)
        ax.set_xlabel("Frequency (GHz)")
        ax.set_ylabel("Normalized fluorescence")
        ax.tick_params(left=False, labelleft=False)
        # ax.get_yaxis().set_visible(False)


def waterfall():

    width = 1.0 * kpl.figsize[0]
    height = 0.8 * width
    fig = plt.figure(figsize=(width, height))
    ax = fig.add_subplot(projection="3d")

    setpoint_temps = np.arange(310, 500, 10)
    setpoint_temps = setpoint_temps.tolist()
    setpoint_temps.insert(0, "")
    min_temp = 296
    max_temp = setpoint_temps[-1]

    min_freq = 2.84
    max_freq = 2.881
    freq_center = (min_freq + max_freq) / 2
    freq_range = max_freq - min_freq
    smooth_freqs = pesr.calculate_freqs(freq_center, freq_range, 100)

    skip_lambda = (
        lambda point: point["Skip"]
        or point["Sample"] != "Wu"
        or point["Setpoint temp (K)"] not in setpoint_temps
        or point["NV"] != "nv7_zfs_vs_t"
    )
    data_points = get_data_points(skip_lambda)

    # cmap_name = "coolwarm"
    # cmap_name = "autumn_r"
    # cmap_name = "magma_r"
    cmap_name = "plasma"
    cmap = mpl.colormaps[cmap_name]
    cmap_offset = 0

    poly_zero = 0.75
    poly = lambda x, y: [(x[0], 1.0), *zip(x, y), (x[-1], 1.0)]
    # verts[i] is a list of (x, y) pairs defining polygon i.
    verts = []
    colors = []
    temps = []

    num_sets = len(setpoint_temps)
    for ind in range(num_sets):

        # Reverse
        ind = num_sets - 1 - ind

        data_point = data_points[ind]
        fig_file = data_point["ZFS file"]
        temp = data_point["Monitor temp (K)"]
        temps.append(temp)
        norm_temp = (temp - min_temp + cmap_offset) / (
            max_temp - min_temp + cmap_offset + 25
        )
        color = cmap(norm_temp)

        popt = (
            data_point["Contrast"],
            data_point["Width (MHz)"],
            data_point["ZFS (GHz)"],
            data_point["Splitting (MHz)"],
        )

        data = tool_belt.get_raw_data(fig_file)
        freq_center = data["freq_center"]
        freq_range = data["freq_range"]
        num_steps = data["num_steps"]
        freqs = pesr.calculate_freqs(freq_center, freq_range, num_steps)

        ref_counts = data["ref_counts"]
        sig_counts = data["sig_counts"]
        num_reps = data["num_reps"]
        nv_sig = data["nv_sig"]
        sample = nv_sig["name"].split("-")[0]
        readout = nv_sig["spin_readout_dur"]
        uwave_pulse_dur = data["uwave_pulse_dur"]

        try:
            norm_style = tool_belt.NormStyle[str.upper(nv_sig["norm_style"])]
        except Exception as exc:
            # norm_style = NormStyle.POINT_TO_POINT
            norm_style = tool_belt.NormStyle.SINGLE_VALUED

        ret_vals = tool_belt.process_counts(
            sig_counts, ref_counts, num_reps, readout, norm_style
        )
        norm_avg_sig = ret_vals[2]

        ax.plot(
            freqs,
            norm_avg_sig,
            zs=temp,
            zdir="x",
            color=color,
            linestyle="None",
            marker="o",
            markersize=2,
            # alpha=0.5,
        )

        fit_func = lambda f: 1 - three_level_rabi.coherent_line(
            f, *popt, uwave_pulse_dur
        )
        verts.append(poly(smooth_freqs, fit_func(smooth_freqs)))
        colors.append(color)
        ax.plot(
            smooth_freqs,
            fit_func(smooth_freqs),
            zs=temp,
            # color=KplColors.DARK_GRAY,
            zdir="x",
            color=color,
            # alpha=0.5,
        )

    # poly = PolyCollection(verts, facecolors=colors, alpha=0.7)
    # ax.add_collection3d(poly, zs=temps, zdir="x")

    ax.set(
        xlim=(510, 290),
        ylim=(min_freq, max_freq),
        zlim=(poly_zero, 1.03),
        xlabel="\n$T$ (K)",
        ylabel="\n$f$ (GHz)",
        zlabel="$C$",
        yticks=[2.84, 2.86, 2.88],
        zticks=[0.8, 0.9, 1.0],
    )
    ax.view_init(elev=38, azim=-22, roll=0)
    # ax.tick_params(left=False, labelleft=False)
    # ax.get_yaxis().set_visible(False)

    fig.tight_layout()
    # fig.tight_layout(rect=(-0.05, 0, 0.95, 1))


def quasiharmonic_sketch():

    kpl_figsize = kpl.figsize
    adj_figsize = (kpl_figsize[0], 0.8 * kpl_figsize[1])
    fig, ax = plt.subplots(figsize=adj_figsize)

    min_temp = 170
    max_temp = 230
    temp_linspace = np.linspace(min_temp, max_temp, 1000)

    lattice_constant = fit_double_occupation()

    parabola_points = np.linspace(180, 220, 5)

    for point in parabola_points:
        parabola_linspace = np.linspace(point - 5, point + 5, 100)
        parabola_lambda = lambda t: 1.25e-6 * (t - point) ** 2 + lattice_constant(point)
        if point == 200:
            color = KplColors.DARK_GRAY
        else:
            color = KplColors.LIGHT_GRAY
        kpl.plot_line(
            ax, parabola_linspace, parabola_lambda(parabola_linspace), color=color
        )

    kpl.plot_line(
        ax, temp_linspace, lattice_constant(temp_linspace), color=KplColors.RED
    )

    ax.set_xlim(min_temp, max_temp)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("Temperature T (K)")
    ax.set_ylabel(r"Lattice constant ($\si{\angstrom}$)")


if __name__ == "__main__":

    kpl.init_kplotlib(latex=False, constrained_layout=False)

    # main()
    waterfall()
    # quasiharmonic_sketch()

    plt.show(block=True)
