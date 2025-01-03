# -*- coding: utf-8 -*-
"""
Created on Jan 3 2023

@author: agardill
"""


import time
from random import shuffle

import labrad
import matplotlib.pyplot as plt
import numpy
from numpy import pi
from numpy.linalg import eigvals
from scipy.optimize import curve_fit

import majorroutines.targeting as targeting
import utils.kplotlib as kpl
import utils.tool_belt as tool_belt
from utils.kplotlib import KplColors
from utils.tool_belt import NormStyle, States


def cosine_fit(x, offset, amp, freq, phase):
    return offset + amp * numpy.cos(x * freq + phase)


def plot(x_data, y_data, title):
    kpl.init_kplotlib()

    x_smooth = numpy.linspace(x_data[0], x_data[-1], 1000)

    fit_func = lambda x, offset, amp, freq, phase: cosine_fit(
        x, offset, amp, freq, phase
    )
    init_params = [0.5, 1, numpy.pi / 180, 1]
    popt, pcov = curve_fit(
        fit_func,
        x_data,
        y_data,
        # sigma=t2_sq_unc,
        # absolute_sigma=True,
        p0=init_params,
    )
    print(popt)

    # Plot setup
    fig, ax = plt.subplots(1, 1)
    ax.set_xlabel("Phase (rad)")
    ax.set_ylabel("IF voltage (mV)")
    ax.set_title(title)

    # Plotting
    kpl.plot_points(ax, x_data, y_data, label="data", color=KplColors.BLACK)

    kpl.plot_line(
        ax, x_smooth, fit_func(x_smooth, *popt), label="fit", color=KplColors.RED
    )

    ax.legend()


phases = numpy.linspace(0, 360, 8)
voltages = [
    -0.20181405895691606,
    0.31550802139037426,
    0.47468354430379756,
    0.09135802469135812,
    -0.21126760563380287,
    -1.0919540229885056,
    -0.6466666666666667,
    0.060109289617486406,
]

plot(
    phases,
    voltages,
    "",
)
