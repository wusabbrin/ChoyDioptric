# -*- coding: utf-8 -*-
"""
Optimize SCC parameters

Created on December 6th, 2023

@author: mccambria
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator
from scipy.optimize import curve_fit

from majorroutines.widefield import base_routine
from majorroutines.widefield.scc_snr_check import process_and_print
from utils import data_manager as dm
from utils import kplotlib as kpl
from utils import tool_belt as tb
from utils import widefield as widefield
from utils.constants import NVSig


def process_and_plot(data):
    nv_list = data["nv_list"]
    # counts = np.array(data["counts"])
    counts = np.array(data["states"])
    num_runs = counts.shape[2]
    counts = counts[:, :, num_runs // 2 :]

    # exclude_inds = (6, 9, 13)
    exclude_inds = ()
    num_nvs = len(nv_list)
    nv_list = [nv_list[ind] for ind in range(num_nvs) if ind not in exclude_inds]
    num_nvs = len(nv_list)
    counts = np.delete(counts, exclude_inds, axis=1)

    # Break down the counts array
    # experiment, nv, run, step, rep
    sig_counts = np.array(counts[0])
    ref_counts = np.array(counts[1])

    # sig_counts, ref_counts = widefield.threshold_counts(nv_list, sig_counts, ref_counts)

    # Calculate the correlations
    flattened_sig_counts = [sig_counts[ind].flatten() for ind in range(num_nvs)]
    flattened_ref_counts = [ref_counts[ind].flatten() for ind in range(num_nvs)]
    num_shots = len(flattened_ref_counts[0])
    sig_corr_coeffs = np.corrcoef(flattened_sig_counts)
    ref_corr_coeffs = np.corrcoef(flattened_ref_counts)

    diff_corr_coeffs = np.cov(flattened_sig_counts) - np.cov(flattened_ref_counts)
    # stddev = np.sqrt(np.diag(sig_corr_coeffs).real + np.diag(ref_corr_coeffs).real)
    # diff_corr_coeffs /= stddev[:, None]
    # diff_corr_coeffs /= stddev[None, :]
    # diff_corr_coeffs = sig_corr_coeffs - ref_corr_coeffs

    spin_flips = np.array([-1 if nv.spin_flip else +1 for nv in nv_list])
    ideal_sig_corr_coeffs = np.outer(spin_flips, spin_flips)
    ideal_sig_corr_coeffs = ideal_sig_corr_coeffs.astype(float)

    ### Plot

    vals = [sig_corr_coeffs, diff_corr_coeffs, ref_corr_coeffs, ideal_sig_corr_coeffs]

    # Replace diagonals (Cii=1) with nan so they don't show
    for val in vals:
        np.fill_diagonal(val, np.nan)

    # Make the colorbar symmetric about 0
    sig_max = np.nanmax(np.abs(sig_corr_coeffs))
    ref_max = np.nanmax(np.abs(ref_corr_coeffs))
    diff_max = np.nanmax(np.abs(diff_corr_coeffs))

    figs = []
    titles = ["Signal", "Difference", "Reference", "Ideal signal"]
    cbar_maxes = [sig_max, diff_max, sig_max, 1]
    for ind in range(len(vals)):
        coors = vals[ind]  # Replace diagonals (Cii=1) with nan so they don't show
        np.fill_diagonal(coors, np.nan)
        fig, ax = plt.subplots()
        cbar_max = cbar_maxes[ind]
        # cbar_max = 0.032
        kpl.imshow(
            ax,
            vals[ind],
            title=titles[ind],
            cbar_label="Covariance" if ind == 1 else "Correlation coefficient",
            cmap="RdBu_r",
            vmin=-cbar_max,
            vmax=cbar_max,
            nan_color=kpl.KplColors.GRAY,
        )
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        figs.append(fig)

    return figs

    ### Spurious correlations offset

    # offsets = np.array(range(15000))
    offsets = list(range(1000))
    # offsets = [500]
    spurious_vals = []
    for offset in offsets:
        ref_corr_coeffs = np.array(
            [[None for ind in range(num_nvs)] for ind in range(num_nvs)],
            dtype=float,
        )
        for ind in range(num_nvs):
            for jnd in range(num_nvs):
                if jnd <= ind:
                    continue
                val = np.corrcoef(
                    [
                        flattened_ref_counts[ind][: num_shots - offset],
                        flattened_ref_counts[jnd][offset:],
                    ]
                )[0, 1]
                ref_corr_coeffs[ind, jnd] = val
                ref_corr_coeffs[jnd, ind] = val
        ref_corr_coeffs = np.array(ref_corr_coeffs)
        np.fill_diagonal(ref_corr_coeffs, np.nan)
        spurious_vals.append(np.nanmean(ref_corr_coeffs))

    fig, ax = plt.subplots()
    kpl.plot_points(ax, offsets, spurious_vals, label="Data")
    ax.set_xlabel("Shot offset")
    ax.set_ylabel("Average spurious correlation")
    window = 20
    avg = tb.moving_average(spurious_vals, window)
    avg_x_vals = np.array(range(len(avg))) + window // 2
    kpl.plot_line(
        ax,
        avg_x_vals,
        avg,
        color=kpl.KplColors.RED,
        zorder=10,
        linewidth=3,
        label="Moving average",
    )

    def fit_fn(offset, amp1, amp2, d1, d2):
        return (
            amp1 * np.exp(-offset / d1) + amp2 * np.exp(-offset / d2)
            # + amp3 * np.exp(offset / d3)
        )

    # # popt, pcov = curve_fit(fit_fn, avg_x_vals, avg, p0=(0.001, 20))
    # popt, pcov = curve_fit(fit_fn, avg_x_vals, avg, p0=(0.001, 0.0015, 20, 3000))
    # kpl.plot_line(
    #     ax,
    #     offsets,
    #     fit_fn(offsets, *popt),
    #     color=kpl.KplColors.ORANGE,
    #     zorder=10,
    #     linewidth=3,
    #     label="Fit",
    # )
    # print(popt)
    # ax.legend()

    return figs


def main(nv_list, num_reps, num_runs):
    ### Some initial setup
    uwave_ind_list = [0, 1]
    seq_file = "simple_correlation_test.py"
    num_steps = 1

    pulse_gen = tb.get_server_pulse_gen()

    ### Collect the data

    def run_fn(shuffled_step_inds):
        seq_args = [widefield.get_base_scc_seq_args(nv_list, uwave_ind_list)]
        seq_args_string = tb.encode_seq_args(seq_args)
        pulse_gen.stream_load(seq_file, seq_args_string, num_reps)

    raw_data = base_routine.main(
        nv_list,
        num_steps,
        num_reps,
        num_runs,
        run_fn=run_fn,
        uwave_ind_list=uwave_ind_list,
    )

    ### Process and plot

    # process_and_print(nv_list, counts)
    try:
        sig_fig, ref_fig = process_and_plot(raw_data)
    except Exception:
        sig_fig = None
        ref_fig = None

    ### Clean up and save data

    tb.reset_cfm()

    kpl.show()

    timestamp = dm.get_time_stamp()
    raw_data |= {
        "timestamp": timestamp,
    }

    repr_nv_sig = widefield.get_repr_nv_sig(nv_list)
    repr_nv_name = repr_nv_sig.name
    file_path = dm.get_file_path(__file__, timestamp, repr_nv_name)
    dm.save_raw_data(raw_data, file_path)
    if sig_fig is not None:
        file_path = dm.get_file_path(__file__, timestamp, repr_nv_name + "-sig")
        dm.save_figure(sig_fig, file_path)
    if ref_fig is not None:
        file_path = dm.get_file_path(__file__, timestamp, repr_nv_name + "-ref")
        dm.save_figure(ref_fig, file_path)


if __name__ == "__main__":
    kpl.init_kplotlib()

    data = dm.get_raw_data(file_id=1538271354881)  # Checkerboard
    # data = dm.get_raw_data(file_id=1519615059736)  # Block

    process_and_plot(data)

    plt.show(block=True)
