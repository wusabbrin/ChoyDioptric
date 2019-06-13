# -*- coding: utf-8 -*-
"""
Template matching.
Gaussian blur?
Threshold to zero below background noise kcps.
TM_CCOEFF_NORMED at 0.75 or TM_CCORR_NORMED at 0.98 or something.
Find local maxima.

Created on Mon May  6 15:31:59 2019

@author: mccambria
"""

####################### Imports #######################

import cv2
import numpy
from matplotlib import pyplot as plt
import json
import sys
import utils.image_processing as image_processing

####################### Files #######################

# Gaussian tests
directory = 'G:\\Team Drives\\Kolkowitz Lab Group\\nvdata\\image_sample\\'
# directory = 'E:\\Team Drives\\Kolkowitz Lab Group\\nvdata\\image_sample\\'

# file_name = '2019-04-29_16-37-06_ayrton12.txt'
# file_name = '2019-04-29_16-37-56_ayrton12.txt'

#file_name = '2019-04-29_16-19-11_ayrton12.txt'
#file_name = '2019-04-30_14-45-29_ayrton12.txt'

#file_name = '2019-04-29_15-33-39_ayrton12.txt'
#file_name = '2019-05-01_15-55-20_ayrton12.txt'

# Lost NVs
# directory = 'C:\\Users\\Matt\\Desktop\\lost_nvs\\'
# file_name = '2019-05-28_16-37-29_ayrton12.txt'
# file_name = '2019-05-29_08-56-53_ayrton12.txt'
# file_name = '2019-05-29_11-38-15_ayrton12.txt'
# file_name = '2019-05-30_09-39-50_ayrton12.txt'  # 1.0 x 1.0
file_name = '2019-05-30_12-19-47_ayrton12.txt'  # 1.5 x 1.5

file_path = directory + file_name

####################### Parameters #######################

diff_lim_spot_diam = 0.0075  # expected st dev of the gaussian in volts

methods = ['cv2.TM_CCOEFF', 'cv2.TM_CCOEFF_NORMED',
           'cv2.TM_CCORR', 'cv2.TM_CCORR_NORMED',
           'cv2.TM_SQDIFF', 'cv2.TM_SQDIFF_NORMED']

# for method_ind in range(6):
for method_ind in [1]:

    ####################### Read the file #######################

    with open(file_path, 'r') as file:
        data = json.load(file)

    x_voltages = data['x_voltages']
    y_voltages = data['y_voltages']

    x_low = x_voltages[0]
    x_high = x_voltages[-1]
    y_low = y_voltages[0]
    y_high = y_voltages[-1]

    half_pixel_size = (x_voltages[1] - x_voltages[0]) / 2
    img_extent = [x_high + half_pixel_size, x_low - half_pixel_size,
                  y_low - half_pixel_size, y_high + half_pixel_size]

    x_range = data['x_range']
    y_range = data['y_range']
    min_range = min(x_range, y_range)
    num_steps = data['num_steps']
    volts_per_pixel = min_range / num_steps

    img_array = numpy.array(data['img_array'])
    img_array = image_processing.convert_to_8bit(img_array)

    img_array = cv2.GaussianBlur(img_array, (5, 5), 0)

    ####################### Initial calculations #######################

    # expected st dev of the gaussian in pixels - must be odd
    diff_lim_spot_pixels = int(diff_lim_spot_diam / volts_per_pixel)
    if diff_lim_spot_pixels % 2 == 1:
        diff_lim_spot_pixels += 1

    ####################### Template #######################

    # Gaussian
    # gaussian_num_pixels = diff_lim_spot_pixels  # 2 st devs out
    # single_axis = numpy.linspace(-1, 1, gaussian_num_pixels)
    # x, y = numpy.meshgrid(single_axis, single_axis)
    # pixel_distances = numpy.sqrt(x**2 + y**2)
    # var = diff_lim_spot_pixels**2
    # coeff = (2 * numpy.pi * var)**-1
    # gaussian = coeff * numpy.exp(-(pixel_distances**2) / (2 * var))
    # gaussian = image_processing.convert_to_8bit(gaussian)

    # Image
    # file_name = '2019-04-29_16-39-18_ayrton12.txt'
    file_name = '2019-05-10_11-47-17_ayrton12.txt'
    # file_name = '2019-05-07_18-23-21_ayrton12.txt'
    file_path = directory + file_name
    with open(file_path, 'r') as file:
        data = json.load(file)
    template_img = numpy.array(data['img_array'])
    template_img = image_processing.convert_to_8bit(template_img)

    # template = gaussian
    template = template_img

    ####################### Run the matching #######################

    method = eval(methods[method_ind])
    res = cv2.matchTemplate(img_array, template, method)

    processed_img_array = numpy.copy(img_array)
    processed_img_array = cv2.cvtColor(processed_img_array, cv2.COLOR_GRAY2RGB)
    res_size = len(res[0])
    clip_offset = int(numpy.floor((num_steps - res_size) / 2))
    red_pixel_vals = [255, 0, 0]
    for y_ind in range(res_size):
        for x_ind in range(res_size):
            if res[y_ind][x_ind] > 0.8:
                img_y_ind = y_ind + clip_offset
                img_x_ind = x_ind + clip_offset
                processed_img_array[img_y_ind][img_x_ind] = red_pixel_vals

    ####################### Plotting #######################

    plot_mode = 3
    if plot_mode == 1:
        fig, ax = plt.subplots(figsize=(5,5))
        # ax.imshow(img_array)
        ax.imshow(template)
    elif plot_mode == 2:
        fig, axes_pack = plt.subplots(1, 2, figsize=(10, 5))
        ax = axes_pack[0]
        ax.imshow(img_array, extent=tuple(img_extent))
        ax = axes_pack[1]
        # ax.imshow(processed_img_array, extent=tuple(imgExtent))
        ax.imshow(res)
    elif plot_mode == 3:
        fig, axes_pack = plt.subplots(1, 3, figsize=(15, 5))
        ax = axes_pack[0]
        ax.imshow(img_array, extent=tuple(img_extent))
        ax = axes_pack[1]
        ax.imshow(res)
        ax = axes_pack[2]
        ax.imshow(processed_img_array, extent=tuple(img_extent))

    fig.show()
    fig.tight_layout()
    # Maximize the window
    fig_manager = plt.get_current_fig_manager()
    fig_manager.window.showMaximized()