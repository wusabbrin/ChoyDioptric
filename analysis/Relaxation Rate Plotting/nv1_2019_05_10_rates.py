# -*- coding: utf-8 -*-
"""
Created on Wed Jun 12 14:36:23 2019

This file plots the relaxation rate data collected for the nv1_2019_05_10.

The data is input manually, and plotted on a loglog plot with error bars along
the y-axis. A 1/f**2 line is also fit to the gamma rates to show the behavior.

@author: Aedan
"""

'''
nv1_2019_05_10


'''
# %%
def fit_eq(f, amp):
    return amp*f**(-2)

# %%

import matplotlib.pyplot as plt
from scipy import asarray as ar, exp
from scipy.optimize import curve_fit
import numpy

# The data
nv1_splitting_list = [19.8, 28, 30, 32.7, 51.8, 97.8, 116]
nv1_omega_avg_list = [1.3, 1.7, 1.62, 1.48, 2.3, 1.8, 1.18]
nv1_omega_error_list = [0.2, 0.4, 0, 0.09, 0.4, 0.2, 0.13]
nv1_gamma_avg_list = [136, 68, 37, 50, 13.0, 3.5, 4.6]
nv1_gamma_error_list = [10, 7, 6, 3, 0.6, 0.2, 0.3]

# Try to fit the gamma to a 1/f^2

fit_params, cov_arr = curve_fit(fit_eq, nv1_splitting_list, nv1_gamma_avg_list, 
                                p0 = 100)

splitting_linspace = numpy.linspace(nv1_splitting_list[0], nv1_splitting_list[-1],
                                    1000)


fig, ax = plt.subplots(1, 1, figsize=(10, 8))

#ax.errorbar(splitting_list, omega_avg_list, yerr = omega_error_list)
ax.set_xscale("log", nonposx='clip')
ax.set_yscale("log", nonposy='clip')
ax.errorbar(nv1_splitting_list, nv1_gamma_avg_list, yerr = nv1_gamma_error_list, 
            label = 'Gamma', fmt='o', color='blue')
ax.errorbar(nv1_splitting_list, nv1_omega_avg_list, yerr = nv1_omega_error_list, 
            label = 'Omega', fmt='o', color='red')
ax.plot(splitting_linspace, fit_eq(splitting_linspace, *fit_params), 
            label = '1/f^2')
ax.grid()

ax.set_xlabel('Splitting (MHz)')
ax.set_ylabel('Relaxation Rate (kHz)')
ax.set_title('NV1_2019_05_10')
ax.legend()