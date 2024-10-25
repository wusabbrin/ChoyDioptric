import os
import sys
import warnings
from datetime import datetime

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

from utils import data_manager as dm
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


def blaze(vector_deg=(0.2, 0.2)):
    # Get .2 degrees in normalized units.
    vector = toolbox.convert_blaze_vector(vector_deg, from_units="deg", to_units="norm")
    blaze_phase = toolbox.phase.blaze(grid=slm, vector=vector)
    plot_phase(blaze_phase, title="Blaze at {} deg".format(vector_deg))


# region "calibration"
def fourier_calibration():
    cam.set_exposure(0.1)  # Increase exposure because power will be split many ways
    fs.fourier_calibrate(
        array_shape=[20, 12],  # Size of the calibration grid (Nx, Ny) [knm]
        array_pitch=[30, 40],  # Pitch of the calibration grid (x, y) [knm]
        plot=True,
    )
    cam.set_exposure(0.01)
    # save calibation
    calibration_file = fs.save_fourier_calibration(path="slmsuite/fourier_calibration")
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
        path="slmsuite/wavefront_calibration"
    )
    print("Fourier calibration saved to:", calibration_file)


def load_fourier_calibration():
    calibration_file_path = (
        "slmsuite/fourier_calibration/26438-SLM-fourier-calibration_00003.h5"
    )
    fs.load_fourier_calibration(calibration_file_path)
    print("Fourier calibration loaded from:", calibration_file_path)


def load_wavefront_calibration():
    calibration_file_path = (
        "slmsuite/wavefront_calibration/26438-SLM-wavefront-calibration_00004.h5"
    )
    fs.load_wavefront_calibration(calibration_file_path)
    print("Wavefront calibration loaded from:", calibration_file_path)


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
    center = (750, 530)  # Center of the circle
    radii = np.linspace(50, 200, num=4)  # Adjust the number of circles as needed
    circle_points = []
    for radius in radii:
        num_points = int(2 * np.pi * radius / 60)

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


# region "nv phase calulation"
def calibration_triangle():
    cam.set_exposure(0.1)

    # Define parameters for the equilateral triangle
    center = (750, 600)  # Center of the triangle
    side_length = 240  # Length of each side of the triangle

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


def nuvu2thorcam_calibration(coords):
    """
    Calibrates and transforms coordinates from the Nuvu camera's coordinate system
    to the Thorlabs camera's coordinate system using an affine transformation.

    Parameters:
    coords (np.ndarray): An array of shape (N, 2) containing coordinates in the Nuvu camera's system.

    Returns:
    np.ndarray: An array of shape (N, 2) containing transformed coordinates in the Thorlabs camera's system.
    """
    # cal_coords_thorcam = np.array(
    #     [[853.92, 590.0], [646.07, 590.0], [750.0, 410.0]], dtype="float32"
    # )
    # cal_coords_nuvu = np.array(
    #     [[128.706, 72.789], [128.443, 140.826], [69.922, 104.404]], dtype="float32"
    # )
    cal_coords_thorcam = np.array(
        [[957.846, 720.0], [542.153, 720.0], [750.0, 360.0]], dtype="float32"
    )
    cal_coords_nuvu = np.array(
        [[187.721, 49.52], [193.469, 192.543], [63.039, 123.164]], dtype="float32"
    )

    # Compute the affine transformation matrix
    M = cv2.getAffineTransform(cal_coords_nuvu, cal_coords_thorcam)
    # Append a column of ones to the input coordinates to facilitate affine transformation
    ones_column = np.ones((coords.shape[0], 1))
    coords_homogeneous = np.hstack((coords, ones_column))
    thorcam_coords = np.dot(
        coords_homogeneous, M.T
    )  # Perform the affine transformation

    return thorcam_coords


def load_nv_coords(
    file_path="slmsuite/nv_blob_detection/nv_blob_filtered_128nvs_updated.npz",
    # file_path="slmsuite/nv_blob_detection/nv_coords_integras_counts_162nvs.npz",
    # file_path="slmsuite/nv_blob_detection/nv_coords_updated_spot_weights.npz",
    # file_path="slmsuite/nv_blob_detection/nv_coords_updated_spot_weights_manual_update.npz",
):
    # data = np.load(file_path)
    data = np.load(file_path, allow_pickle=True)
    nv_coordinates = data["nv_coordinates"]
    spot_weights = data["spot_weights"]
    return nv_coordinates, spot_weights


# Set the threshold for x and y coordinates, assuming the SLM has a 2048x2048 pixel grid
nuvu_pixel_coords, spot_weights = load_nv_coords()
# nuvu_pixel_coords = np.array(
#     [
#         [121.354, 159.075],
#         [134.394, 102.232],
#         [170.84, 131.657],
#         [67.855, 208.226],
#         [87.583, 101.898],
#         [168.499, 196.189],
#     ]
# )
print(f"Total NV coordinates: {len(nuvu_pixel_coords)}")
thorcam_coords = nuvu2thorcam_calibration(nuvu_pixel_coords).T


def compute_nvs_phase():
    hologram = SpotHologram(
        shape=(4096, 2048),
        spot_vectors=thorcam_coords,
        basis="ij",
        spot_amp=spot_weights,
        cameraslm=fs,
    )
    # Precondition computationally
    hologram.optimize(
        "WGS-Kim",
        maxiter=30,
        feedback="computational_spot",
        stat_groups=["computational_spot"],
    )

    initial_phase = hologram.extract_phase()
    # Define the path to save the phase data
    file_path = r"slmsuite\computed_phase"
    num_nvs = len(nuvu_pixel_coords)
    now = datetime.now()
    date_time_str = now.strftime("%Y%m%d_%H%M%S")  # Format: YYYYMMDD_HHMMSS
    filename = f"slm_phase_{num_nvs}nvs_{date_time_str}.npy"
    # file_path = dm.get_file_path(__file__, filename)
    # Save the phase data
    save(initial_phase, file_path, filename)
    slm.write(initial_phase, settle=True)
    cam_plot()


def write_nvs_phase():
    # phase = np.load(
    #     r"C:\Users\matth\GitHub\dioptric\slmsuite\Initial_phase\initial_phase.npy"
    # )
    # phase = np.load("slmsuite\computed_phase\slm_phase_77nvs_20240926_182348.npy")
    phase = np.load("slmsuite\computed_phase\slm_phase_77nvs_20241001_181243.npy")
    slm.write(phase, settle=True)
    cam_plot()


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
    compute_nvs_phase()
    # write_nvs_phase()
    # calibration_triangle()
    # circle_pattern()
    # circles()
    # smiley()
    # cam_plot()
finally:
    print("Closing")
    slm.close_window()
    slm.close_device()
    cam.close()
# endregions
