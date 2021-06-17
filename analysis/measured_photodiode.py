# -*- coding: utf-8 -*-
"""
Created on Mon Mar  8 09:56:42 2021

@author: kolkowitz
"""


from matplotlib import pyplot as plt



# for yellow 589nm
AOM_power_list = [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]

# for 0 nd filter
measured_poewr_0_list = [0.1*10**-3, 0.2*10**-3, 3.1*10**-3, 0.013, 0.035, 0.071, 0.12, 0.16, 0.22, 0.27, 0.31, 0.34, 0.37]
photodiode_0_list = [-0.004615, -0.004615, -0.004583, -0.004454, -0.004004, -0.003359, -0.002635, -0.001766, -0.00081607, 5.0529*10**-6, 0.0007456, 0.001277, 0.001776]
# for 0.5 nd filter
measured_power_05_list = [0.1*10**-3, 0.00, 0.8*10**-3, 3.8*10**-3, 0.01, 0.02, 0.034, 0.049, 0.065, 0.079, 0.089, 0.1, 0.106]
photodiode_05_list = [-0.004664, -0.004680, -0.004567, -0.004664, -0.004519, -0.004261, -0.004020, -0.003842, -0.003440, -0.003198, -0.003134, -0.002909, -0.002893]
# for 1.0 nd filter
measured_power_1_list = [-0.13*10**-3, -0.1*10**-3, 0.14*10**-3, 1*10**-3, 2.7*10**-3, 5.6*10**-3, 9.4*10**-3, 0.013, 0.018, 0.022, 0.025, 0.028, 0.03]
photodiode_1_list = [-0.004696, -0.004631, -0.004680, -0.004615, -0.004519, -0.004406, -0.004293, -0.004342, -0.004245, -0.004132, -0.004181]
#for 1.5 nd filter
measured_power_15_list = [-0.13*10**-3, -0.12*10**-3, -0.07*10**-3, 0.09*10**-3, 0.45*10**-3, 1.01*10**-3, 1.79*10**-3, 2.64*10**-3, 3.49*10**-3, 4.3*10**-3, 4.98*10**-3, 5.49*10**-3, 5.83*10**-3]
photodiode_15_list = [-0.004583, -0.004631, -0.004696, -0.004680, -0.004615, -0.004664, -0.004648, -0.004583, -0.004680, -0.004583, -0.004519, -0.004567, -0.004551]

# for red 638nm
laser_setting_red_list = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100, 110, 120, 130, 140, 150, 160, 170, 180]
measured_power_red_list = [0.005, 0.006, 0.007, 0.008, 0.01, 0.011, 0.013, 0.015, 0.018, 0.027, 0.045, 0.084, 0.149, 0.29, 1.70, 3.16, 4.46, 5.40, 6.45, 7.54, 8.63, 9.68, 10.11, 10.44, 10.79, 11.36, 9.05, 6.38, 5.13, 6.83, 2.52]
photodiode_red_list = [-0.004470, -0.004438, -0.004358, -0.004229, -0.004197, -0.004197, -0.004213, -0.004084, -0.003939, -0.003907, -0.003553, -0.002909, -0.001315, 0.0009227, 0.005704, 0.05407, 0.1058, 0.1540, 0.2115, 0.2728, 0.3345, 0.3969, 0.4371, 0.5124, 0.5921, 0.6428, 0.6947, 0.6166, 0.4810, 0.3709, 0.4627, 0.1812]

# for green 515nm
laser_setting_green_list = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
measured_power_green_list = [0.004, 0.005, 0.006, 0.007, 0.011, 0.043, 0.18, 0.29, 0.38, 0.47, 0.66, 0.84, 1.01, 1.18, 1.34, 3.00, 4.65, 6.31, 7.90, 9.42, 10.84, 12.09]
photodiode_green_list = [-0.004487, -0.00447, -0.00437, -0.00426, -0.00419, -0.00335, 0.000681, 0.00541, 0.00744, 0.01182, 0.01776, 0.02668, 0.0319, 0.0401, 0.04399, 0.1319, 0.2318, 0.3697, 0.5082, 0.6620, 0.8006, 0.8924]


plt.plot(photodiode_green_list, measured_power_green_list)
plt.xlabel('Photodiode(V)')
plt.ylabel('Measured power(mW)')