# -*- coding: utf-8 -*-
"""
Model decsription figure for zfs vs t paper

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
import matplotlib as mpl
from utils import kplotlib as kpl
from utils.kplotlib import KplColors
from scipy.optimize import curve_fit
import csv
import pandas as pd
import sys
from analysis import three_level_rabi
from figures.zfs_vs_t.zfs_vs_t_main import get_data_points
from figures.zfs_vs_t.thermal_expansion import (
    fit_double_occupation,
    jacobson_lattice_constant,
)
from figures.zfs_vs_t.deconvolve_spectral_function import deconvolve


# endregion


def fig():
    max_temp = 1000
    temp_linspace = np.linspace(1, 1000, 1000)
    min_energy = 0
    max_energy = 175
    energy_linspace = np.linspace(0, max_energy, 1000)
    kpl_figsize = kpl.figsize
    adj_figsize = (kpl_figsize[0], 1.2 * kpl_figsize[1])
    fig, axes_pack = plt.subplots(2, 1, figsize=adj_figsize)
    ax1, ax2 = axes_pack
    ax3 = ax2.twinx()

    double_occupation_lambda = fit_double_occupation()

    # First order effects (lattice constant)
    kpl.plot_line(
        ax1,
        temp_linspace,
        jacobson_lattice_constant(temp_linspace),
        label="Jacobson",
        color=KplColors.BLACK,
        # color="#5A5A5A",
        # linestyle="dashed",
        # linestyle="dotted",
        # linestyle=(0, (5, 10)),
        linestyle=(0, (4, 5)),
        # color=kpl.KplColors.GRAY,
        # linewidth=2,
        zorder=5,
    )
    kpl.plot_line(
        ax1,
        temp_linspace,
        double_occupation_lambda(temp_linspace),
        label="This work",
        color=KplColors.CYAN,
        # color="#cb2222",
        # linewidth=2,
        zorder=0,
    )
    # print(max(diffs))
    ax1.set_ylabel(r"Lattice constant ($\si{\angstrom}$)", usetex=True)
    ax1.set_xlabel("Temperature (K)")
    ax1.legend()
    ax1.set_xlim(0, 1000)
    ax1.set_yticks([3.567, 3.570, 3.573])
    ax1.set_ylim(3.5658, None)
    text = r"\noindent$a(T) = a_{0} + b_{1}n_{1} + b_{2}n_{2}$"
    text += r"\\"
    text += r"$n=\left(\exp(\Delta_{i} / k_{\mathrm{B}}T)-1\right)^{-1}$"
    kpl.anchored_text(ax1, text, kpl.Loc.LOWER_RIGHT, kpl.Size.SMALL, usetex=True)

    # Second order effects
    sigma = np.sqrt(7.5)
    density_of_states, spectral_functions, mean_couplings = deconvolve(
        energy_linspace, sigma
    )
    # labels = [r"$\mathit{S_{z}}$", r"$\mathit{S_{+}}$", r"$\mathit{S_{+}^{2}}$"]
    color = KplColors.ORANGE
    plot_vals = np.array(spectral_functions[0])
    kpl.plot_line(ax2, energy_linspace, plot_vals, color=color)
    ax2.set_ylabel("Spectral function \n(MHz / meV)", color=color)
    ax2.tick_params(axis="y", color=color, labelcolor=color)
    # ax2.spines["left"].set_color(color)
    ax3.spines["left"].set_color(color)  # ax3 vs 2 because 3 is written on top of 2
    ax2.set_xlabel("Energy $\hbar\omega$ (meV)", usetex=True)
    ax2.set_xlim(min_energy, max_energy)
    ax2.set_ylim(0, None)

    # DOS
    color = KplColors.GREEN
    plot_vals = density_of_states
    kpl.plot_line(ax3, energy_linspace, plot_vals, color=color)
    ax3.set_ylabel("DOS (1 / meV)", color=color)
    ax3.tick_params(axis="y", color=color, labelcolor=color)
    ax3.spines["right"].set_color(color)
    ax3.set_ylim(0, None)

    # Energies from ZFS vs T fit

    energies = [58.9, 146.9]
    energy_errs = [2.2, 8.5]
    for ind in range(len(energies)):
        energy = energies[ind]
        energy_err = energy_errs[ind]
        ax2.axvline(energy, color=KplColors.DARK_GRAY, zorder=-10)
        ax2.axvspan(
            energy - energy_err,
            energy + energy_err,
            color=KplColors.LIGHT_GRAY,
            zorder=-11,
        )

    ### Wrap up

    fig.text(0.07, 0.965, "(a)")
    fig.text(0.07, 0.465, "(b)")
    # print(jacobson_lattice_constant(257))

    ### Lattice constant diffs
    if True:
        diffs = [
            np.abs(jacobson_lattice_constant(temp) - double_occupation_lambda(temp))
            for temp in temp_linspace
        ]
        #
        rel_diffs = []
        a_zero_k = jacobson_lattice_constant(5)  # Below 5 you get NaN
        a_max_k = jacobson_lattice_constant(max_temp)
        total_change = np.abs(a_max_k - a_zero_k)
        for temp in temp_linspace:
            diff_val = np.abs(
                jacobson_lattice_constant(temp) - double_occupation_lambda(temp)
            )
            rel_diffs.append(diff_val / total_change)
        #
        fig, ax = plt.subplots()
        # ax.plot(temp_linspace, diffs)
        ax.plot(temp_linspace, rel_diffs)


if __name__ == "__main__":
    kpl.init_kplotlib()

    fig()
    # fig_three_panel()

    plt.show(block=True)
