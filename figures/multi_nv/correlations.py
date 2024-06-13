# -*- coding: utf-8 -*-
"""
Main text fig 3

Created on June 5th, 2024

@author: mccambria
"""

import time

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

from majorroutines.widefield import simple_correlation_test
from utils import common
from utils import data_manager as dm
from utils import kplotlib as kpl
from utils import tool_belt as tb
from utils import widefield as widefield
from utils.constants import NVSig


def main(block_data, checkerboard_data, orientation_data):
    figsize = kpl.figsize
    figsize[1] = 1.2 * figsize[0]
    main_fig = plt.figure(figsize=figsize)

    seq_fig, data_fig = main_fig.subfigures(nrows=2, height_ratios=(0.3, 0.8), hspace=0)
    seq_fig.get_layout_engine().set(w_pad=0, h_pad=0, hspace=0, wspace=0)

    ### Seq

    global_alpha = 0.8

    # NV-specific axes
    nrows = 6
    seq_axes_pack = seq_fig.subplots(
        nrows=nrows,
        sharex=True,
        sharey=True,
        height_ratios=[1, 1, 1, 0.25, 1, 1],
        gridspec_kw={"hspace": 0.01},
    )
    global_ax = seq_axes_pack[-1]

    # Global pulse axis
    seq_ax = seq_fig.add_subplot(111)
    seq_ax.set_ylabel(" ", rotation="horizontal", labelpad=40, loc="bottom")
    seq_ax.sharex(seq_axes_pack[0])
    # seq_ax.sharey(seq_axes_pack[0])
    global_ax = seq_ax

    for ax in [*seq_axes_pack, seq_ax]:
        ax.tick_params(
            which="both",
            top=False,
            bottom=False,
            left=False,
            right=False,
            labelbottom=False,
            labelleft=False,
        )
        ax.spines[["left", "right", "top"]].set_visible(False)

    seq_axes_pack[-3].spines[["bottom"]].set_visible(False)
    seq_ax.spines[["bottom"]].set_visible(False)
    seq_ax.patch.set_alpha(0)

    labels = [*[f"NV {ind}" for ind in range(3)], "...", "NV $\it{n}$", "Global"]
    for ind in range(nrows):
        ax = seq_axes_pack[ind]
        if ind == nrows - 3:
            ax.set_ylabel(labels[ind])
        else:
            ax.set_ylabel(labels[ind], rotation="horizontal", labelpad=50, loc="bottom")
    global_ax.set_ylabel(" ", labelpad=50, loc="bottom")

    ax = seq_axes_pack[0]
    # ax.set_xlim([16, 49])
    ax.set_ylim([0.1, 1.01])
    seq_ax.set_ylim([0.1, 1.01])

    # Annotations
    seq_axes_pack[0].set_title(" ")
    seq_ax.set_title(" ")
    seq_axes_pack[-1].set_xlabel(" ")
    seq_ax.set_xlabel(" ")
    seq_fig.text(0.4, 0.3, "Spin pol.", horizontalalignment="center", rotation=90)
    seq_fig.text(
        0.6,
        0.3,
        r"$\pi_{\mathregular{A}}$ pulse",
        horizontalalignment="center",
        rotation=90,
    )
    seq_fig.text(
        0.5,
        0.3,
        r"$\pi_{\mathregular{B}}$ pulse",
        horizontalalignment="center",
        rotation=90,
    )
    seq_fig.text(
        0.9, 0.3, "Charge state\nreadout", horizontalalignment="center", rotation=90
    )

    row_skip_inds = [nrows - 3, nrows - 1]

    # Spin polarization
    start = 10
    stop = start + 10
    kpl.plot_sequence(
        global_ax, [0, start, stop, 0], [0, 1, 0], color="#d9d900", alpha=global_alpha
    )

    # Microwaves A
    # start = stop + 2
    # stop = start + 1
    # # kpl.plot_sequence(
    # # seq_ax, [0, start, stop, 0], [0, 1, 0], color=kpl.KplColors.BROWN
    # # )
    # start = stop + 1
    # stop = start + 1
    # # kpl.plot_sequence(
    # # seq_ax, [0, start, stop, 0], [0, 1, 0], color=kpl.KplColors.BROWN
    # # )
    for color in [kpl.KplColors.BROWN, kpl.KplColors.ORANGE]:
        start = stop + 0.3
        stop = start + 2
        kpl.plot_sequence(
            global_ax,
            [0, start, stop, 0],
            [0, 1, 0],
            color=color,
            facecolor="none",
            alpha=global_alpha,
            linestyle="--",
        )

    # SCC
    for ind in range(nrows - 2):
        if ind in row_skip_inds:
            start += 2
            continue
        ax = seq_axes_pack[ind]
        start = stop + 4
        stop = start + 1
        kpl.plot_sequence(ax, [0, start, stop, 0], [0, 1, 0], color=kpl.KplColors.RED)

    # Anticorrelation microwaves
    stop += 2
    for color in [kpl.KplColors.BROWN, kpl.KplColors.ORANGE]:
        start = stop + 0.3
        stop = start + 2
        kpl.plot_sequence(
            global_ax,
            [0, start, stop, 0],
            [0, 1, 0],
            color=color,
            # facecolor="none",
            alpha=global_alpha,
            # linestyle="--",
        )

    # Final SCC pulse
    start = stop + 3
    stop = start + 1
    ax = seq_axes_pack[-2]
    kpl.plot_sequence(ax, [0, start, stop, 0], [0, 1, 0], color=kpl.KplColors.RED)

    # Charge state readout
    start = stop + 1
    stop = 200
    kpl.plot_sequence(
        global_ax, [0, start, stop, 0], [0, 1, 0], color="#f5f556", alpha=global_alpha
    )

    ax.set_xlim([17, start + 4])

    ### Data

    axes_pack = data_fig.subplots(
        2,
        2,
        sharex=True,
        sharey=True,
        gridspec_kw={"hspace": 0.02, "wspace": 0.02},
    )
    ((ref_ax, block_ax), (checkerboard_ax, orientation_ax)) = axes_pack

    datas = [block_data, block_data, checkerboard_data, orientation_data]
    axes = [ref_ax, block_ax, checkerboard_ax, orientation_ax]
    for ind in range(4):
        data = datas[ind]
        ax = axes[ind]
        sig_or_ref = ind > 0
        simple_correlation_test.process_and_plot(
            data,
            ax=ax,
            sig_or_ref=sig_or_ref,
            no_cbar=True,
            cbar_max=0.04,
            no_labels=True,
        )
    ax = checkerboard_ax
    kpl.set_shared_ax_xlabel(ax, "NV index")
    kpl.set_shared_ax_ylabel(ax, "NV index")
    img = ax.get_images()[0]
    cbar = data_fig.colorbar(img, ax=axes_pack, shrink=0.7, aspect=25)
    cbar.set_label("Correlation coefficient", size=16)
    cbar.ax.set_title(r"$\times 10^{-2}$", fontsize=14)
    cbar.ax.locator_params(axis="y", nbins=5)
    cbar.ax.set_yticklabels([-4, -2, 0, 2, 4], fontsize=16)
    # cbar.ax.set_yticks([-0.004, -0.002, 0.000, 0.002, 0.004], labels=[-4, -2, 0, 2, 4])
    # cbar.ax.tick_params(rotation=90)


if __name__ == "__main__":
    kpl.init_kplotlib()

    # block_data = dm.get_raw_data(file_id=1540048047866)  # Straight order
    block_data = dm.get_raw_data(file_id=1541938921939)  # Reversed
    checkerboard_data = dm.get_raw_data(file_id=1538271354881)
    orientation_data = dm.get_raw_data(file_id=1540558251818)

    main(block_data, checkerboard_data, orientation_data)

    plt.show(block=True)
