# -*- coding: utf-8 -*-
"""
Fit circles to superresolution rings in images demonstrating resolved
images of two NVs separated by less than the diffraction limit.

Created on February 25, 2022

@author: mccambria
"""

# region Imports

import utils.tool_belt as tool_belt
import utils.common as common
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize, brute
from numpy import pi
from matplotlib.patches import Circle
import cv2 as cv
import sys

# endregion

# region Constants

num_circle_samples = 1000

phi_linspace = np.linspace(0, 2 * pi, num_circle_samples, endpoint=False)
cos_phi_linspace = np.cos(phi_linspace)
sin_phi_linspace = np.sin(phi_linspace)

# endregion

# region Functions


def cost0(params, image, x_lim, y_lim, x_restrict, y_restrict, debug):
    """
    Faux-integrate the pixel values around the circle. Then muliply by -1 so that
    lower values are better and we can use scipy.optimize.minimize.
    By faux-integrate I mean average the values under a 1000 point, linearly spaced
    sampling of the circle.
    """

    circle_center_x, circle_center_y, circle_radius = params

    if not x_restrict and not y_restrict:
        weights = np.ones(num_circle_samples)
    elif x_restrict and not y_restrict:
        weights = np.abs(sin_phi_linspace)
    elif not x_restrict and y_restrict:
        weights = np.abs(cos_phi_linspace)
    else:
        raise RuntimeError("You really blew it this time...")

    circle_samples_x = (
        circle_center_x + circle_radius * cos_phi_linspace
    )
    circle_samples_y = (
        circle_center_y + circle_radius * sin_phi_linspace
    )
    circle_samples_x_round = [round(el) for el in circle_samples_x]
    circle_samples_y_round = [round(el) for el in circle_samples_y]
    circle_samples = zip(circle_samples_x_round, circle_samples_y_round)

    check_valid = lambda el: (0 <= el[1] < x_lim) and (0 <= el[0] < y_lim)
    # integrand = [(image[el] * weights[el], weights[el]) for el in circle_samples if check_valid(el)]
    ind = 0
    integrand = []
    for el in circle_samples:
        ind += 1
        if ind == 1000:
            break
        if not check_valid(el):
            continue
        image_val = image[el]
        weights_val = weights[ind]
        integrand.append((image_val * weights_val, weights_val,))
    
    integral, norm = np.sum(integrand, axis=0)
    cost = integral / norm

    return cost


def sigmoid_quotient(laplacian, gradient):

    # Get the zeros from the gradient so we can avoid divide by zeros.
    # At the end we'll just set the sigmoid to the sign of the Laplacian
    # for these values.
    gradient_zeros = gradient < 1e-10
    gradient_not_zeros = np.logical_not(gradient_zeros)
    masked_gradient = (gradient * gradient_not_zeros) + gradient_zeros
    quotient = laplacian / masked_gradient
    sigmoid = 1 / (1 + np.exp(-1 * quotient))
    laplacian_positive = np.sign(laplacian) == 1
    sigmoid = (sigmoid * gradient_not_zeros) + (
        laplacian_positive * gradient_zeros
    )
    return sigmoid


def calc_errors(image_file_name, circle_a, circle_b):

    cost_func = cost0

    # Get the image as a 2D ndarray
    image_file_dict = tool_belt.get_raw_data(image_file_name)
    image = np.array(image_file_dict["readout_image_array"])
    image_domain = image.shape
    image_len_x = image_domain[1]
    image_len_y = image_domain[0]

    ret_vals = process_image(image)
    sigmoid_image = ret_vals[-1]

    fig, axes_pack = plt.subplots(1, 3)
    fig.set_tight_layout(True)

    num_points = 1000
    sweep_half_range = 10
    for circle in [circle_a, circle_b]:

        print(circle)
        args = [sigmoid_image, image_len_x, image_len_y, False, False, False]
        opti_cost = cost_func(circle, *args)

        for param_ind in range(3):

            # Y
            if param_ind == 0:
                x_restrict = False
                y_restrict = True
            # X
            if param_ind == 1:
                x_restrict = True
                y_restrict = False
            # R
            if param_ind == 2:
                x_restrict = False
                y_restrict = False

            args[3] = x_restrict
            args[4] = y_restrict

            ax = axes_pack[param_ind]
            sweep_center = circle[param_ind]
            sweep_vals = np.linspace(
                sweep_center - sweep_half_range,
                sweep_center + sweep_half_range,
                num_points,
            )

            cost_vals = []
            for sweep_ind in range(num_points):
                test_circle = list(circle)
                test_circle[param_ind] = sweep_vals[sweep_ind]
                cost_vals.append(0.5 - cost_func(test_circle, *args))

            ax.plot(sweep_vals, cost_vals)

            left_width = None
            right_width = None
            half_max = (0.5 - opti_cost) / 2
            half_ind = num_points // 2
            for delta in range(half_ind):
                test_ind = half_ind - delta
                if (cost_vals[test_ind] < half_max) and (left_width is None):
                    left_width = sweep_vals[test_ind]
                test_ind = half_ind + delta
                if (cost_vals[test_ind] < half_max) and (right_width is None):
                    right_width = sweep_vals[test_ind]
                if (left_width is not None) and (right_width is not None):
                    break
            half_width_at_half_max = (right_width - left_width) / 2
            print(half_width_at_half_max)

    print()


def process_image(image):

    # Blur
    gaussian_size = 7
    blur_image = cv.GaussianBlur(image, (gaussian_size, gaussian_size), 0)

    gradient_root = blur_image

    laplacian_image = cv.Laplacian(
        gradient_root, cv.CV_64F, ksize=gaussian_size
    )

    sobel_x = cv.Sobel(gradient_root, cv.CV_64F, 1, 0, ksize=gaussian_size)
    sobel_y = cv.Sobel(gradient_root, cv.CV_64F, 0, 1, ksize=gaussian_size)
    gradient_image = np.sqrt(sobel_x ** 2 + sobel_y ** 2)

    sigmoid_image = sigmoid_quotient(laplacian_image, gradient_image)
    # sigmoid_image = cv.GaussianBlur(
    #     sigmoid_image, (gaussian_size, gaussian_size), 0
    # )

    return blur_image, laplacian_image, gradient_image, sigmoid_image


def calc_distance(x0, x1, y0, y1, sx0, sx1, sy0, sy1):

    dx = x1 - x0
    dy = y1 - y0
    distance = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
    err = np.sqrt(
        ((dx / distance) ** 2) * (sx0 ** 2 + sx1 ** 2)
        + ((dy / distance) ** 2) * (sy0 ** 2 + sy1 ** 2)
    )

    print(distance)
    print(err)
    print()


# endregion


def main(
    image_file_name, circle_a, circle_b, fast_recursive=False, brute_range=None
):

    # region Setup

    cost_func = cost0
    # minimize_type = "manual"
    # minimize_type = "auto"
    # minimize_type = "recursive"
    minimize_type = "none"

    # Get the image as a 2D ndarray
    image_file_dict = tool_belt.get_raw_data(image_file_name)
    image = np.array(image_file_dict["readout_image_array"])

    image_domain = image.shape
    image_len_x = image_domain[1]
    image_len_y = image_domain[0]

    ret_vals = process_image(image)
    blur_image, laplacian_image, gradient_image, sigmoid_image = ret_vals

    opti_image = sigmoid_image
    plot_image = image
    # plot_image = sigmoid_image

    # Plot the image
    fig, ax = plt.subplots()
    fig.set_tight_layout(True)
    img = ax.imshow(plot_image, cmap="inferno")
    _ = plt.colorbar(img)
    # return

    # endregion

    # region Circle finding

    args = (opti_image, image_len_x, image_len_y, False)
    plot_circles = []

    if minimize_type == "manual":

        x_linspace = np.linspace(0, image_len_x, image_len_x, endpoint=False)
        y_linspace = np.linspace(0, image_len_x, image_len_y, endpoint=False)
        rad_linspace = np.linspace(20, 35, 16)

        left_best_circle = None
        left_best_cost = 1
        right_best_circle = None
        right_best_cost = 1
        half_x = image_len_x / 2

        # Manual brute force optimization for left/right halves
        for x in x_linspace:
            for y in y_linspace:
                for r in rad_linspace:
                    circle = [y, x, r]
                    cost = cost_func(circle, *args)
                    if x < half_x:
                        if cost < left_best_cost:
                            left_best_circle = circle
                            left_best_cost = cost
                    else:
                        if cost < right_best_cost:
                            right_best_circle = circle
                            right_best_cost = cost

        brute_circles = [left_best_circle, right_best_circle]
        for circle in brute_circles:
            print(circle)
            bounds = [(val - 1, val + 1) for val in circle]
            res = minimize(
                cost_func, circle, bounds=bounds, args=args, method="L-BFGS-B"
            )
            opti_circle = res.x
            plot_circles.append(opti_circle)

    elif minimize_type == "auto":

        # Define the bounds of the optimization
        bounds_a = [(el - brute_range, el + brute_range) for el in circle_a]
        bounds_b = [(el - brute_range, el + brute_range) for el in circle_b]
        # Assume one circle is in the left half of the image and the other
        # is in the right half
        mid_x = (bounds_a[1][1] + bounds_b[1][0]) / 2
        bounds_a[1] = (bounds_a[1][0], mid_x)
        bounds_b[1] = (mid_x, bounds_b[1][1])
        bounds_a = tuple(bounds_a)
        bounds_b = tuple(bounds_b)

        for bounds in [bounds_a, bounds_b]:

            # Run a brute force optimization to avoid local minima. This function
            # automatically includes a fine tuning minimization at the end
            opti_circle = brute(
                cost_func,
                bounds,
                Ns=20,
                args=args,
                # finish=None
            )

            plot_circles.append(opti_circle)

    elif minimize_type == "recursive":

        # Define the bounds of the optimization
        if fast_recursive:
            bounds_a = [(el - 1, el + 1) for el in circle_a]
            bounds_b = [(el - 1, el + 1) for el in circle_b]
        else:
            bounds_a = [
                ((1 / 4) * image_len_y, (3 / 4) * image_len_y),
                (0, image_len_x / 2),
                (20, 35),
            ]
            bounds_b = [
                ((1 / 4) * image_len_y, (3 / 4) * image_len_y),
                (image_len_x / 2, image_len_x),
                (20, 35),
            ]

        for bounds in [bounds_a, bounds_b]:

            best_cost = 1
            while True:

                opti_circle = brute(
                    cost_func, bounds, Ns=20, args=args, finish=None
                )
                new_best_cost = cost_func(opti_circle, *args)

                threshold = 0.0001 * best_cost
                if best_cost - new_best_cost < threshold:
                    break
                best_cost = new_best_cost

                bounds_span = [el[1] - el[0] for el in bounds]
                half_new_span = [0.1 * el for el in bounds_span]
                bounds = [
                    (
                        opti_circle[ind] - half_new_span[ind],
                        opti_circle[ind] + half_new_span[ind],
                    )
                    for ind in range(3)
                ]
                # print(new_best_cost)
                # print(bounds)

            plot_circles.append(opti_circle)

    # Just use the passed circles
    else:
        plot_circles = [circle_a, circle_b]

    # endregion

    # region Circle plotting

    for circle in plot_circles:

        # Debug tweak
        # circle[0] -= 0.5

        # Report what we found
        rounded_circle = [round(el, 2) for el in circle]
        rounded_cost = round(cost_func(circle, *args), 5)
        # print("{} & {} & {} & {}".format(*rounded_circle, rounded_cost))
        print("{}, {}, {}, {}".format(*rounded_circle, rounded_cost))

        # Plot the circle
        circle_patch = Circle(
            (circle[1], circle[0]),
            circle[2],
            fill=False,
            color="w",
        )
        ax.add_patch(circle_patch)

    # endregion


# region Run the file

if __name__ == "__main__":

    # # Fig 3
    # calc_distance(36.85, 43.87, 41.74, 39.05, 1.4, 0.9, 1.3, 1.6)
    # # Fig 4
    # calc_distance(45.79, 56.32, 50.98, 51.2, 1.3, 1.1, 1.4, 1.7)

    # sys.exit()

    tool_belt.init_matplotlib()

    # circles = [3]
    # circles = [4]
    circles = [3, 4]
    for circle in circles:

        # Fig. 3
        if circle == 3:
            image_file_name = "2021_09_30-13_18_47-johnson-dnv7_2021_09_23"
            # Best circles by hand
            # circle_a = [41.5, 37, 27.5]
            # circle_b = [40, 44, 27.75]
            # Recursive brute results, 1000 point circle
            circle_a = [41.74, 36.85, 27.73]  # 0.31941
            # errs_a = [1.3, 1.4, 1.2]
            circle_b = [39.05, 43.87, 27.59]  # 0.36108
            # errs_b = [1.6, 0.9, 1.0]

        # Fig. 4
        elif circle == 4:
            image_file_name = "2021_10_17-19_02_22-johnson-dnv5_2021_09_23"
            # Best circles by hand
            # circle_a = [50, 46, 26]
            # circle_b = [51.7, 56.5, 27.3]
            # Recursive brute results, 1000 point circle
            circle_a = [50.98, 45.79, 26.14]  # 0.3176
            # errs_a = [1.4, 1.3, 1.3]
            circle_b = [51.2, 56.32, 27.29]  # 0.35952
            # errs_b = [1.7, 1.1, 1.2]

        # main(image_file_name, circle_a, circle_b, fast_recursive=True)
        calc_errors(image_file_name, circle_a, circle_b)

    # plt.show(block=True)

# endregion


 # 0.0004375 V, for Fig 4 each pixel is 0.0005 V. And the conversion is 34.8 um/V
 
 # Fig 3: 15.225 nm / pixel
 # Fig 4: 17.4 nm / pixel