import os, sys, time
# Add slmsuite to the python path (for the case where it isn't installed via pip).
sys.path.append(os.path.join(os.getcwd(), 'c:/Users/Saroj Chand/Documents/dioptric/servers/inputs'))

import numpy as np
import pandas as pd
import cv2
import h5py
import scipy.ndimage as ndimage
import warnings
warnings.filterwarnings("ignore")
import matplotlib as mpl
import matplotlib.pyplot as plt
# Generate a phase .gif
from IPython.display import Image
import imageio
import io 
from slmsuite.holography import analysis, toolbox
mpl.rc('image', cmap='Blues')

def nuvu2thorcam_calibration(coords):
    """
    Calibrates and transforms coordinates from the Nuvu camera's coordinate system
    to the Thorlabs camera's coordinate system using an affine transformation.

    Parameters:
    coords (np.ndarray): An array of shape (N, 2) containing coordinates in the Nuvu camera's system.

    Returns:
    np.ndarray: An array of shape (N, 2) containing transformed coordinates in the Thorlabs camera's system.
    """
    # Define the corresponding points in both coordinate systems
    cal_coords_nuvu = np.array([[100, 100], [200, 100], [200, 200]], dtype='float32')  # Points in (512, 512) coordinate system
    cal_coords_thorcam = np.array([[281.25, 210.9375], [562.5, 210.9375], [562.5, 421.875]], dtype='float32')  # Corresponding points in (1480, 1020) coordinate system

    # Compute the affine transformation matrix
    M = cv2.getAffineTransform(cal_coords_nuvu, cal_coords_thorcam)

    # Append a column of ones to the input coordinates to facilitate affine transformation
    ones_column = np.ones((coords.shape[0], 1))
    coords_homogeneous = np.hstack((coords, ones_column))

    # Perform the affine transformation
    thorcam_coords = np.dot(coords_homogeneous, M.T)

    return thorcam_coords


def shift_phase(phase, shift_x, shift_y):
    for ind in range(phase.shape[0]):
        for jnd in range(phase.shape[1]):
            phase[ind, jnd] += np.dot((ind, jnd), (shift_x, shift_y))
    return phase

# Ensure the 'shift_phase' function is optimized and efficient
def shift_phase(phase, shift_x, shift_y):
    # Create a meshgrid of indices
    y_indices, x_indices = np.indices(phase.shape)
    # Compute the phase shift using vectorized operations
    phase_shift = shift_x * x_indices + shift_y * y_indices
    # Apply the phase shift
    shifted_phase = phase + phase_shift
    return shifted_phase

def selcted_shift_phase(phase, spot_indices, shift_x, shift_y):
    # Initialize phase shift array with zeros
    phase_shift = np.indices(phase.shape)
    # Apply shifts only to the specified spots
    for (y_idx, x_idx) in spot_indices:
        phase_shift[y_idx, x_idx] = shift_x * x_idx + shift_y * y_idx
    # Apply the phase shift
    shifted_phase = phase + phase_shift
    return shifted_phase

def square_tweezer_path(x1, x2, num_points=31):
    shifts = np.linspace(x1, x2, num=num_points)
    path = []
    for shift in shifts:
        path.append((shift, -x2))  # Right
    for shift in shifts:
        path.append((x2, shift))  # Up
    for shift in shifts[::-1]:
        path.append((shift, x2))  # Left
    for shift in shifts[::-1]:
        path.append((-x2, shift))  # Down
    return path

def triangular(x1, x2):
    # Define the three vertices of the triangle
    centeroid = (0,0)
    top_vertex = (x1, x1)
    right_vertex = (x2, -x2)
    left_vertex = (-x2, -x2)
    
    # Create the path by appending the vertices
    path = [centeroid, top_vertex, right_vertex, left_vertex, centeroid]
    
    return path

def circular_tweezer_path(num_points=100, radius=0.5):
    theta = np.linspace(0, 2*np.pi*radius, num=num_points)
    x = radius * np.cos(theta)
    y = radius * np.sin(theta)
    path = [(x[i], y[i]) for i in range(num_points)]
    return path

def spiral_tweezer_path(num_points=100, max_radius=0.5, num_turns=2):
    theta = np.linspace(0, 2*np.pi*num_turns, num=num_points)
    radius = np.linspace(0, max_radius, num=num_points)
    x = radius * np.cos(theta)
    y = radius * np.sin(theta)
    path = [(x[i], y[i]) for i in range(num_points)]
    return path

def calculate_phaseshifts(cam_coords):
    """
    Calibrates and transforms coordinates from the Nuvu camera's coordinate system
    to the Thorlabs camera's coordinate system using an affine transformation.

    Parameters:
    cam_coords (np.ndarray): Coordinates in the Nuvu camera's coordinate system.

    Returns:
    np.ndarray: Transformed coordinates in the Thorlabs camera's coordinate system.
    """
    # Define the corresponding points in both coordinate systems
    cam_pixel_coords = np.array([[1020, 862], [1019, 310], [460, 310]], dtype='float32')  # Points in Nuvu camera's coordinate system
    phaseshift_coords = np.array([[0.6, 0.6], [0.6, -0.6],  [-0.6, -0.6]], dtype='float32')  # Corresponding points in Thorlabs camera's coordinate system

    # Compute the affine transformation matrix
    M = cv2.getAffineTransform(cam_pixel_coords, phaseshift_coords)

    # Perform the affine transformation
    # Add a column of ones to cam_coords to make it compatible for affine transformation
    cam_coords_augmented = np.hstack([cam_coords, np.ones((cam_coords.shape[0], 1))])
    phase_shift_coords = np.dot(cam_coords_augmented, M.T)

    return phase_shift_coords[:, :2]

def plot_intensity():
    # Data from the image
    data = {
        "Power": [1, 1.2, 1.4, 1.6, 2, 2.4, 3, 4, 6, 8],
        "all_array_spot Intensity": [73240, 74239, 75155, 76969, 80057, 84386, 89551, 103747, 153496, 296225],
        "oth order": [13010, 13154, 13213, 13333, 13638, 14087, 14599, 15705, 20399, 33304]
    }

    df = pd.DataFrame(data)
    # Compute the relative intensity
    df['Relative Intensity'] = df['all_array_spot Intensity'] / df['oth order']
    # Plot the data
    plt.figure(figsize=(10, 6))
    # Plot relative intensity
    plt.plot(df['Power'], df['Relative Intensity'], label='Relative Intensity (All Array / 0th Order)', marker='s', color='blue')
    # plt.plot(df['Power'], df['all_array_spot Intensity'], label='Array Spots Integrated Intensity', marker='o', color='orange')
    # plt.plot(df['Power'], df['oth order'], label='0th Order Intensity', marker='x', color='red')
    plt.xlabel('Power')
    plt.ylabel('Intensity')
    plt.title('Intensity vs Power')
    plt.legend()
    plt.grid(True)
    plt.show()
# plot_intensity()