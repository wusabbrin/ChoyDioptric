# -*- coding: utf-8 -*-
"""
Replot Gergo's ab initio spectral density spin-phonon couplings

Created on May 23rd, 2022

@author: mccambria
"""

# region Imports

import errno
import matplotlib
import numpy as np
import matplotlib.pyplot as plt
import csv
import matplotlib.patches as patches
import matplotlib.lines as mlines
from scipy.optimize import curve_fit
import pandas as pd
import utils.tool_belt as tool_belt
import utils.common as common
from scipy.odr import ODR, Model, RealData
import sys
from pathlib import Path
import math
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from matplotlib.gridspec import GridSpec
from numpy import pi

# endregion

# region Functions


def gaussian(val, center, std):
    inv_root_2_pi = 1 / np.sqrt(2 * pi)
    inv_std = 1 / std
    return (
        inv_std
        * inv_root_2_pi
        * np.exp(-(1 / 2) * ((val - center) * inv_std) ** 2)
    )


def parse_data_file(data_file):
    # ret_vals = freqs, couplings_0, couplings_1, couplings_2
    # First row is header
    # Columns: 2, frequency (meV); 4, g++=g-- (meV); 5, g+0=g-0=g0+=g0- (meV); 6, g+-=g-+ (meV)
    ret_vals = np.loadtxt(
        data_file, skiprows=1, usecols=(2, 4, 5, 6), unpack=True
    )
    return ret_vals


def smear(plot_linspace, smearing_range, freqs, couplings):
    smeared_couplings = []
    num_modes = len(freqs)
    for x_val in plot_linspace:
        gaussian_lambda = lambda freq: gaussian(freq, x_val, smearing_range)
        norm = 0
        smeared_coupling = 0
        for ind in range(num_modes):
            freq = freqs[ind]
            coupling = abs(couplings[ind])
            weight = gaussian_lambda(freq)
            smeared_coupling += weight * coupling
            norm += weight
        # smeared_couplings.append(smeared_coupling / norm)
        smeared_couplings.append(smeared_coupling)
    return smeared_couplings


# endregion

# region Main


def main(
    dosave=False,
):

    file_name = "2022_05_23-512_atom-spin_phonon.dat"
    file_name = "2022_05_25-512_atom-spin_phonon.dat"
    nvdata_dir = common.get_nvdata_dir()
    data_file = (
        nvdata_dir / "paper_materials/relaxation_temp_dependence" / file_name
    )

    freqs, couplings_0, couplings_1, couplings_2 = parse_data_file(data_file)
    plot_linspace = np.linspace(0, 200, 100)
    smearing_range = 5
    smear_couplings_0 = smear(
        plot_linspace, smearing_range, freqs, couplings_0
    )
    smear_couplings_1 = smear(
        plot_linspace, smearing_range, freqs, couplings_1
    )
    smear_couplings_2 = smear(
        plot_linspace, smearing_range, freqs, couplings_2
    )

    figsize = [7.0, 5.5]
    fig, ax = plt.subplots(figsize=figsize)

    line_width = 2.5
    ax.plot(
        plot_linspace, smear_couplings_0, label=r"\(S_{z}^{2}\)", lw=line_width
    )
    ax.plot(
        plot_linspace,
        smear_couplings_1,
        label=r"\(S_{z}S_{+}\)",
        lw=line_width,
    )
    ax.plot(
        plot_linspace, smear_couplings_2, label=r"\(S_{+}^{2}\)", lw=line_width
    )
    # gaussian_lambda = lambda freq: gaussian(freq, 150, 5)
    # ax.plot(plot_linspace, gaussian_lambda(plot_linspace))

    ax.set_title(r"\textit{Ab initio} spin-phonon couplings")
    ax.set_xlabel("Frequency (meV)")
    ax.set_ylabel(r"Spectral density (MHz\(^{\text{2}}\)/meV)")

    ax.legend(loc="upper left")
    # fig.tight_layout(pad=0.3)
    fig.tight_layout(pad=0.3)
    # tool_belt.non_math_ticks(ax)
    ax.set_xlim([-10, 210])
    ax.set_ylim([0, 130])

    if dosave:
        # ext = "png"
        ext = "svg"
        file_path = str(
            nvdata_dir
            / "paper_materials/relaxation_temp_dependence/figures/main3.{}".format(
                ext
            )
        )
        # fig.savefig(file_path, dpi=500)
        fig.savefig(file_path)


# endregion

# region Run the file

if __name__ == "__main__":

    tool_belt.init_matplotlib()

    main(dosave=False)

    plt.show(block=True)

# endregion