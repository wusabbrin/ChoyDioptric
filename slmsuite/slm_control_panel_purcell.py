import os
import sys
import time

# Add slmsuite to the python path (for the case where it isn't installed via pip).
sys.path.append(os.path.join(os.getcwd(), "c:/Users/Saroj Chand/Documents/dioptric"))

import warnings

import cv2
import numpy as np
import pandas as pd
import scipy.ndimage as ndimage

warnings.filterwarnings("ignore")
import io

import imageio
import matplotlib as mpl
import matplotlib.pyplot as plt

# Generate a phase .gif
from IPython.display import Image
from scipy.optimize import curve_fit

from utils import tool_belt as tb

mpl.rc("image", cmap="Blues")

from slmsuite import example_library
from slmsuite.hardware.cameras.thorlabs import ThorCam
from slmsuite.hardware.cameraslms import FourierSLM
from slmsuite.hardware.slms.thorlabs import ThorSLM
from slmsuite.holography import analysis, toolbox
from slmsuite.holography.algorithms import FeedbackHologram, SpotHologram
from slmsuite.misc import fitfunctions


def plot_phase(phase, angle):
    # Initialize the figure and axes outside the loop
    fig, ax = plt.subplots(1, 3, figsize=(15, 5))
    blaze_vector = (np.cos(np.radians(angle)), np.sin(np.radians(angle)))

    # Update phase with live rotation
    delta_phase = toolbox.phase.blaze(grid=slm, vector=blaze_vector, offset=0)
    phase = None

    # Display the phase pattern on the SLM
    slm.write(phase, settle=True)

    # Capture image from the camera
    cam.set_exposure(0.0001)
    im = cam.get_image()

    # Clear the axes and plot the phase, delta phase, and camera image
    ax[0].clear()
    ax[0].imshow(phase, cmap="gray")
    ax[0].set_title("Total Phase")

    ax[1].clear()
    ax[1].imshow(delta_phase, cmap="gray")
    ax[1].set_title("Delta Phase")

    ax[2].clear()
    ax[2].imshow(im, cmap="gray")
    ax[2].set_title("Camera Image")

    plt.pause(0.01)


def cam_plot():
    cam.set_exposure(0.0001)
    img = cam.get_image()
    # Plot the result
    plt.figure(figsize=(12, 9))
    plt.imshow(img)
    plt.show()


def blaze():
    # Get .2 degrees in normalized units.
    vector_deg = (0.2, 0.2)
    vector = toolbox.convert_blaze_vector(vector_deg, from_units="deg", to_units="norm")

    # Get the phase for the new vector
    blaze_phase = toolbox.phase.blaze(grid=slm, vector=vector)

    plot_phase(blaze_phase, title="Blaze at {} deg".format(vector_deg))


# region "calibration"
def fourier_calibration():
    cam.set_exposure(0.001)  # Increase exposure because power will be split many ways
    fs.fourier_calibrate(
        array_shape=[20, 12],  # Size of the calibration grid (Nx, Ny) [knm]
        array_pitch=[20, 30],  # Pitch of the calibration grid (x, y) [knm]
        plot=True,
    )
    cam.set_exposure(0.001)
    # save calibation
    calibration_file = fs.save_fourier_calibration(
        path=r"C:\Users\matth\GitHub\dioptric\slmsuite\fourier_calibration"
    )
    print("Fourier calibration saved to:", calibration_file)


def test_wavefront_calibration():
    cam.set_exposure(0.001)
    movie = fs.wavefront_calibrate(
        interference_point=(600, 400),
        field_point=(0.25, 0),
        field_point_units="freq",
        superpixel_size=60,
        test_superpixel=(16, 16),  # Testing mode
        autoexposure=False,
        plot=3,  # Special mode to generate a phase .gif
    )
    imageio.mimsave("wavefront.gif", movie)
    Image(filename="wavefront.gif")


def wavefront_calibration():
    cam.set_exposure(0.001)
    fs.wavefront_calibrate(
        interference_point=(600, 400),
        field_point=(0.25, 0),
        field_point_units="freq",
        superpixel_size=40,
        autoexposure=False,
    )
    # save calibation
    calibration_file = fs.save_wavefront_calibration(
        path=r"C:\Users\matth\GitHub\dioptric\slmsuite\wavefront_calibration"
    )
    print("Fourier calibration saved to:", calibration_file)


def load_fourier_calibration():
    calibration_file_path = r"C:\Users\matth\GitHub\dioptric\slmsuite\fourier_calibration\26438-SLM-fourier-calibration_00003.h5"
    fs.load_fourier_calibration(calibration_file_path)
    print("Fourier calibration loaded from:", calibration_file_path)


def load_wavefront_calibration():
    calibration_file_path = r"C:\Users\matth\GitHub\dioptric\slmsuite\wavefront_calibration\26438-SLM-wavefront-calibration_00004.h5"
    fs.load_wavefront_calibration(calibration_file_path)
    print("Wavefront calibration loaded from:", calibration_file_path)


# region "evaluate" function
def evaluate_uniformity(vectors=None, size=25):
    # Set exposure and capture image
    cam.set_exposure(0.001)
    img = cam.get_image()
    # Extract subimages
    if vectors is None:
        subimages = analysis.take(img, vectors=None, size=size)
    else:
        subimages = analysis.take(img, vectors=vectors, size=size)

    # Plot subimages
    analysis.take_plot(subimages)

    # Normalize subimages and compute powers
    powers = analysis.image_normalization(subimages)

    # Plot histogram of powers
    plt.hist(powers / np.mean(powers))
    plt.show()


# Test pattern
def circles():
    cam.set_exposure(0.1)
    # Define parameters for the circle
    center = (750, 530)  # Center of the circle
    # Generate circles with radii ranging from 10 to 200
    radii = np.linspace(50, 200, num=4)  # Adjust the number of circles as needed
    # Generate points for each circle and create the hologram
    circle_points = []
    for radius in radii:
        num_points = int(
            2 * np.pi * radius / 60
        )  # Adjust the number of points based on the radius

        # Generate points within the circle using polar coordinates
        theta = np.linspace(0, 2 * np.pi, num_points)  # Angle values
        x_circle = center[0] + radius * np.cos(theta)  # X coordinates
        y_circle = center[1] + radius * np.sin(theta)  # Y coordinates

        # Convert to grid format for the current circle
        circle = np.vstack((x_circle, y_circle))

        circle_points.append(circle)

    # Combine the points of all circles
    circles = np.concatenate(circle_points, axis=1)
    hologram = SpotHologram(
        shape=(2048, 2048), spot_vectors=circles, basis="ij", cameraslm=fs
    )

    # # Precondition computationally.
    hologram.optimize(
        "WGS-Kim",
        maxiter=20,
        feedback="computational_spot",
        stat_groups=["computational_spot"],
    )
    phase = hologram.extract_phase()
    slm.write(phase, settle=True)
    cam_plot()
    # evaluate_uniformity(vectors=circle)

    # Hone the result with experimental feedback.
    hologram.optimize(
        "WGS-Kim",
        maxiter=20,
        feedback="experimental_spot",
        stat_groups=["computational_spot", "experimental_spot"],
        fixed_phase=False,
    )
    phase = hologram.extract_phase()
    slm.write(phase, settle=True)
    cam_plot()
    # evaluate_uniformity(vectors=circle)


def calibration_triangle():
    cam.set_exposure(0.1)

    # Define parameters for the equilateral triangle
    center = (750, 530)  # Center of the triangle
    side_length = 120  # Length of each side of the triangle

    # Calculate the coordinates of the three vertices of the equilateral triangle
    theta = np.linspace(0, 2 * np.pi, 4)[:-1]  # Exclude the last point to avoid overlap
    x_triangle = center[0] + side_length * np.cos(theta + np.pi / 6)  # X coordinates
    y_triangle = center[1] + side_length * np.sin(theta + np.pi / 6)  # Y coordinates

    # Combine the coordinates into a grid format
    triangle_points = np.vstack((x_triangle, y_triangle))
    print("thorcam coords:", triangle_points)
    hologram = SpotHologram(
        shape=(2048, 2048), spot_vectors=triangle_points, basis="ij", cameraslm=fs
    )

    # Precondition computationally
    hologram.optimize(
        "WGS-Kim",
        maxiter=20,
        feedback="computational_spot",
        stat_groups=["computational_spot"],
    )
    phase = hologram.extract_phase()
    slm.write(phase, settle=True)
    cam_plot()


def optimize_calibration():
    pass

    # region coords


# Example usage with a list of Nuvu pixel coordinates
nuvu_pixel_coords = [
    [110.186, 129.281],
    [128.233, 88.007],
    [86.294, 103.0],
    # [197.151, 56.105],  # not targeted
    # [199.151, 26.105],  # not targeted
]
# thesre are coord at which
# 87.614, 104.484
# 129.637, 89.599
# 111.651, 130.532
nuvu_pixel_coords_array = np.array(nuvu_pixel_coords)
# Calibrate the coordinates from Nuvu to Thorlabs system
thorcam_coords = example_library.nuvu2thorcam_calibration(nuvu_pixel_coords_array)
# thorcam_coords = thorcam_coords.T  #Transpose


def nvs_demo():
    # Ensure thorcam_coords has shape (2, n)
    thorcam_coords = example_library.nuvu2thorcam_calibration(nuvu_pixel_coords_array).T

    if thorcam_coords.shape[0] != 2:
        raise ValueError(
            f"Expected thorcam_coords to have shape (2, n), but got {thorcam_coords.shape}"
        )

    hologram = SpotHologram(
        shape=(2048, 2048), spot_vectors=thorcam_coords, basis="ij", cameraslm=fs
    )

    # Precondition computationally
    hologram.optimize(
        "WGS-Kim",
        maxiter=20,
        feedback="computational_spot",
        stat_groups=["computational_spot"],
    )

    initial_phase = hologram.extract_phase()
    slm.write(initial_phase, settle=True)
    cam_plot()


def initial_phase():
    xlist = np.arange(650, 750, 10)  # X coordinates for the grid
    ylist = np.arange(340, 440, 10)  # Y coordinates for the grid
    xgrid, ygrid = np.meshgrid(xlist, ylist)
    square = np.vstack((xgrid.ravel(), ygrid.ravel()))
    hologram = SpotHologram(
        shape=(2048, 2048), spot_vectors=square, basis="ij", cameraslm=fs
    )

    # Precondition computationally
    hologram.optimize(
        "WGS-Kim",
        maxiter=20,
        feedback="computational_spot",
        stat_groups=["computational_spot"],
    )
    initial_phase = hologram.extract_phase()

    # Define the path to save the phase data
    path = r"C:\Users\Saroj Chand\Documents\slm_phase"
    filename = "initial_phase.npy"

    # Save the phase data
    save(initial_phase, path, filename)


# Define the save function
def save(data, path, filename):
    if not os.path.exists(path):
        os.makedirs(path)
    np.save(os.path.join(path, filename), data)


# region run funtions
try:
    slm = ThorSLM(serialNumber="00429430")
    cam = ThorCam(serial="26438", verbose=True)
    fs = FourierSLM(cam, slm)
    # cam = tb.get_server_thorcam()
    # slm = tb.get_server_thorslm()
    # blaze()
    # fourier_calibration()
    load_fourier_calibration()
    # test_wavefront_calibration()
    # wavefront_calibration()
    # load_wavefront_calibration()
    # fs.process_wavefront_calibration(r2_threshold=.9, smooth=True, plot=True)
    # square_array()
    # square_array_cirle()
    # save_initial_phase()
    # animate_wavefront_shifts()
    # selected_dynamical_tweezers()
    # camp2phase_calibration()
    # initial_phase()
    # optimize_array()
    # plot_laguerre_gaussian_phase()
    nvs_demo()
    # circles()
    # calibration_triangle()
    # circle_pattern()
    # smiley()
    # cam_plot()
finally:
    print("Closing")
    slm.close_window()
    slm.close_device()
    cam.close()
# endregions
