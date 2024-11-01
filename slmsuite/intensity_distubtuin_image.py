import os

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.patches import Circle
from scipy.optimize import curve_fit
from skimage.draw import disk

from utils import data_manager as dm
from utils import kplotlib as kpl


# Define the 2D Gaussian function
def gaussian_2d(xy, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
    x, y = xy
    xo = float(xo)
    yo = float(yo)
    a = (np.cos(theta) ** 2) / (2 * sigma_x**2) + (np.sin(theta) ** 2) / (
        2 * sigma_y**2
    )
    b = -(np.sin(2 * theta)) / (4 * sigma_x**2) + (np.sin(2 * theta)) / (4 * sigma_y**2)
    c = (np.sin(theta) ** 2) / (2 * sigma_x**2) + (np.cos(theta) ** 2) / (
        2 * sigma_y**2
    )
    g = offset + amplitude * np.exp(
        -(a * ((x - xo) ** 2) + 2 * b * (x - xo) * (y - yo) + c * ((y - yo) ** 2))
    )
    return g.ravel()


# Function to fit a 2D Gaussian around NV coordinates
def fit_gaussian(image, coord, window_size=2):
    x0, y0 = coord
    img_shape_y, img_shape_x = image.shape

    # Ensure the window is within image bounds
    x_min = max(int(x0 - window_size), 0)
    x_max = min(int(x0 + window_size + 1), img_shape_x)
    y_min = max(int(y0 - window_size), 0)
    y_max = min(int(y0 + window_size + 1), img_shape_y)

    if (x_max - x_min) <= 1 or (y_max - y_min) <= 1:
        print(
            f"Invalid cutout for NV at ({x0}, {y0}): Region too small or out of bounds"
        )
        return x0, y0

    # Extract cutout and mesh grid
    x_range = np.arange(x_min, x_max)
    y_range = np.arange(y_min, y_max)
    x, y = np.meshgrid(x_range, y_range)
    image_cutout = image[y_min:y_max, x_min:x_max]

    # Check for valid cutout size
    if image_cutout.size == 0:
        print(f"Zero-size cutout for NV at ({x0}, {y0})")
        return x0, y0

    # Normalize the image cutout
    image_cutout = (image_cutout - np.min(image_cutout)) / (
        np.max(image_cutout) - np.min(image_cutout)
    )

    # Initial guess parameters
    initial_guess = (1, x0, y0, 3, 3, 0, 0)  # Amplitude normalized to 1

    try:
        # Apply bounds to avoid unreasonable parameter values
        bounds = (
            (0, x_min, y_min, 0, 0, -np.pi, 0),  # Lower bounds
            (np.inf, x_max, y_max, np.inf, np.inf, np.pi, np.inf),  # Upper bounds
        )

        # Perform the Gaussian fit
        popt, _ = curve_fit(
            gaussian_2d, (x, y), image_cutout.ravel(), p0=initial_guess, bounds=bounds
        )
        amplitude, fitted_x, fitted_y, _, _, _, _ = popt

        return fitted_x, fitted_y, amplitude

    except Exception as e:
        print(f"Fit failed for NV at ({x0}, {y0}): {e}")
        return x0, y0, 0


def integrate_intensity(image_array, nv_coords, sigma):
    """
    Integrate the intensity around each NV coordinate within a circular region
    defined by sigma, with a Gaussian weighting if needed.
    """
    intensities = []
    for coord in nv_coords:
        # Define a larger radius to ensure full capture of intensity around bright spots
        rr, cc = disk((coord[0], coord[1]), radius=sigma, shape=image_array.shape)

        # Integrate (sum) the intensity values within the disk
        intensity = np.sum(image_array[rr, cc])

        # Append integrated intensity to the list
        intensities.append(intensity)
    return intensities


def remove_outliers(intensities, nv_coords):
    # Calculate Q1 (25th percentile) and Q3 (75th percentile)
    Q1 = np.percentile(intensities, 25)
    Q3 = np.percentile(intensities, 75)
    IQR = Q3 - Q1

    # Define bounds for identifying outliers
    lower_bound = Q1 - 1.0 * IQR
    upper_bound = Q3 + 6.5 * IQR
    # lower_bound = 10
    # upper_bound = 100

    # Filter out the outliers and corresponding NV coordinates
    filtered_intensities = []
    filtered_nv_coords = []

    for intensity, coord in zip(intensities, nv_coords):
        if lower_bound <= intensity <= upper_bound:
            filtered_intensities.append(intensity)
            filtered_nv_coords.append(coord)

    return filtered_intensities, filtered_nv_coords


def remove_manual_indices(nv_coords, indices_to_remove):
    """Remove NVs based on manually specified indices"""
    return [
        coord for idx, coord in enumerate(nv_coords) if idx not in indices_to_remove
    ]


def reorder_coords(nv_coords, *data_arrays):
    distances = [
        np.linalg.norm(np.array(coord) - np.array(nv_coords[0])) for coord in nv_coords
    ]
    sorted_indices = np.argsort(distances)

    reordered_coords = [nv_coords[idx] for idx in sorted_indices]

    reordered_data_arrays = tuple(
        [array[idx] for idx in sorted_indices] for array in data_arrays
    )

    return reordered_coords, *reordered_data_arrays


def sigmoid_weights(intensities, threshold, beta=1):
    """
    Compute the weights using a sigmoid function.

    intensities: array of intensities
    threshold: intensity value at which the function starts transitioning
    beta: steepness parameter (higher beta makes the transition steeper)
    """
    weights = np.exp(beta * (intensities - threshold))
    return weights / np.max(weights)  # Normalize the weights


def non_linear_weights(intensities, alpha=1):
    weights = 1 / np.power(intensities, alpha)
    weights = weights / np.max(weights)  # Normalize to avoid extreme values
    return weights


def linear_weights(intensities, alpha=1):
    weights = 1 / np.power(intensities, alpha)
    weights = weights / np.max(weights)  # Normalize to avoid extreme values
    return weights


def non_linear_weights_adjusted(intensities, alpha=1, beta=0.5, threshold=0.7):
    """
    Adjust weights such that bright NVs keep the same weight and low-intensity NVs get scaled.

    Parameters:
    - intensities: Array of intensities for NV centers.
    - alpha: Controls the non-linearity for low intensities.
    - beta: Controls the sharpness of the transition around the threshold.
    - threshold: Intensity value above which weights are not changed.

    Returns:
    - weights: Adjusted weights where bright NVs have weight ~1, and low-intensity NVs are scaled.
    """
    # Normalize the intensities between 0 and 1
    norm_intensities = intensities / np.max(intensities)

    # Apply a non-linear transformation to only the lower intensities
    weights = np.where(
        norm_intensities > threshold,
        1,  # Keep bright NVs the same
        1
        / (1 + np.exp(-beta * (norm_intensities - threshold)))
        ** alpha,  # Non-linear scaling for low intensities
    )

    # Ensure that the weights are normalized
    weights = weights / np.max(weights)

    return weights


# Save the results to a file
def save_results(nv_coordinates, integrated_intensities, spot_weights, filename):
    """
    Save NV data results to an .npz file.

    nv_coordinates: list or array of NV coordinates
    integrated_intensities: array of integrated intensities
    spot_weights: array of weights (inverse of integrated intensities)
    filename: string, the name of the file to save results
    """
    # Ensure the directory exists
    path = os.path.dirname(filename)
    if not os.path.exists(path):
        os.makedirs(path)  # Create the directory if it doesn't exist

    # Save the data to a .npz file
    np.savez(
        filename,
        nv_coordinates=nv_coordinates,
        integrated_intensities=integrated_intensities,
        spot_weights=spot_weights,
    )


def filter_by_snr(snr_list, threshold=0.5):
    """Filter out NVs with SNR below the threshold."""
    return [i for i, snr in enumerate(snr_list) if snr >= threshold]


def load_nv_coords(
    # file_path="slmsuite/nv_blob_detection/nv_blob_filtered_77nvs_new.npz",
    file_path="slmsuite/nv_blob_detection/nv_blob_filtered_240nvs.npz",
):
    data = np.load(file_path)
    print(data.keys())
    nv_coordinates = data["nv_coordinates"]
    # spot_weights = data["spot_weights"]
    spot_weights = data["integrated_counts"]
    return nv_coordinates, spot_weights


def sigmoid_weight_update(
    fidelities, spot_weights, intensities, alpha=1, beta=10, fidelity_threshold=0.90
):
    """
    Update the spot weights using a sigmoid function. Low-fidelity NVs are adjusted more,
    while high-fidelity NVs remain largely unchanged.

    Parameters:
    - fidelities: Array of fidelity values for NV centers.
    - intensities: Array of integrated intensities for NV centers.
    - alpha: Controls the non-linearity of the weight update for low-fidelity NVs.
    - beta: Controls the steepness of the sigmoid function transition.
    - fidelity_threshold: Fidelity value below which weights should be updated.

    Returns:
    - updated_weights: Array of updated spot weights.
    """
    # Normalize intensities between 0 and 1
    norm_intensities = intensities / np.max(intensities)

    # Initialize updated weights as 1 (i.e., no change for high-fidelity NVs)
    updated_weights = np.copy(spot_weights)

    # Loop over each NV and update weights for those with fidelity < fidelity_threshold
    for i, fidelity in enumerate(fidelities):
        if fidelity < fidelity_threshold:
            # Use a sigmoid to adjust the weight based on intensity
            updated_weights[i] = (
                1 / (1 + np.exp(-beta * (norm_intensities[i]))) ** alpha
            )

    # Normalize the updated weights to avoid extreme values
    updated_weights = updated_weights / np.max(updated_weights)

    return updated_weights


def manual_sigmoid_weight_update(
    spot_weights, intensities, alpha, beta, update_indices
):
    """
    Update spot weights only for NVs with specified indices using a sigmoid function.
    Prints the weights before and after updates.

    Parameters:
    - spot_weights: Current spot weights for each NV.
    - intensities: Integrated intensities for each NV.
    - alpha, beta: Parameters for the sigmoid function.
    - update_indices: List of NV indices to update the weights.

    Returns:
    - updated_spot_weights: List of updated spot weights for each NV.
    """
    updated_spot_weights = (
        spot_weights.copy()
    )  # Make a copy to avoid mutating the original list
    norm_intensities = intensities / np.max(intensities)
    for idx in update_indices:
        print(f"NV Index {idx}: Weight before update: {updated_spot_weights[idx]}")

        # Apply the sigmoid weight update for the specific NV
        weight_update = 1 / (1 + np.exp(-beta * (norm_intensities[idx]))) ** alpha
        updated_spot_weights[idx] = weight_update  # Update weight for this NV

        print(f"NV Index {idx}: Weight after update: {updated_spot_weights[idx]}")

    return updated_spot_weights


# Adjust weights based on SNR values
def adjust_weights_sigmoid(spot_weights, snr_values, alpha=1.0, beta=0.001):
    """Apply sigmoid adjustment to spot weights based on SNR values."""
    updated_weights = np.copy(spot_weights)
    for i, value in enumerate(snr_values):
        if value < 0.9:
            # Sigmoid-based weight adjustment
            updated_weights[i] = 1 / (1 + np.exp(-beta * (value - alpha)))
    return updated_weights


def filter_by_peak_intensity(fitted_data, threshold=0.5):
    """
    Filter NVs based on peak intensity.

    Args:
        fitted_data: List of tuples (x, y, peak_intensity) from Gaussian fitting.
        threshold: Minimum peak intensity required to keep the NV.

    Returns:
        Filtered NV coordinates and their intensities.
    """
    filtered_coords = []
    filtered_intensities = []

    for x, y, intensity in fitted_data:
        if intensity >= threshold:
            filtered_coords.append((x, y))
            filtered_intensities.append(intensity)

    return filtered_coords, filtered_intensities


# Main section of the code
if __name__ == "__main__":
    kpl.init_kplotlib()

    # Parameters
    remove_outliers_flag = False  # Set this flag to enable/disable outlier removal
    reorder_coords_flag = True  # Set this flag to enable/disable reordering of NVs

    # data = dm.get_raw_data(file_id=1648773947273, load_npz=True)
    # data = dm.get_raw_data(file_id=1651663986412, load_npz=True)
    # data = dm.get_raw_data(file_id=1680236956179, load_npz=True)
    # data = dm.get_raw_data(file_id=1681853425454, load_npz=True)
    # data = dm.get_raw_data(file_id=1688298946808, load_npz=True)
    data = dm.get_raw_data(file_id=1688328009205, load_npz=True)
    data = dm.get_raw_data(file_id=1688554695897, load_npz=True)

    #
    img_array = np.array(data["ref_img_array"])
    # img_array = -np.array(data["diff_img_array"])
    nv_coordinates, integrated_intensities = load_nv_coords(
        file_path="slmsuite/nv_blob_detection/nv_blob_filtered_144nvs.npz"
    )
    nv_coordinates = nv_coordinates.tolist()
    integrated_intensities = integrated_intensities.tolist()
    # spot_weights = np.array(spot_weights)
    # print(spot_weights)
    reference_nv = [129.985, 121.129]
    # reference_nv = [150.316, 116.627]
    nv_coords = [reference_nv]
    # Iterate through the rest of the NV coordinates
    for coord in nv_coordinates:
        # Check if the new NV coordinate is far enough from all accepted NVs
        keep_coord = True  # Assume the coordinate is valid

        for existing_coord in nv_coords:
            # Calculate the distance between the current NV and each existing NV
            distance = np.linalg.norm(np.array(existing_coord) - np.array(coord))

            if distance < 5:
                keep_coord = False  # If too close, mark it for exclusion
                break  # No need to check further distances
        if keep_coord:
            nv_coords.append(coord)

    # print(filtered_nv_coords)
    integrated_intensities = np.array(integrated_intensities)
    # Integrate intensities for each filtered NV coordinate with the correct order
    sigma = 2.5

    # Reorder NV coordinates and intensities if the flag is set
    if reorder_coords_flag:
        reordered_nv_coords, reordered_intensities = reorder_coords(
            nv_coords, integrated_intensities
        )
    # integrated_intensities = integrate_intensity(img_array, reordered_nv_coords, sigma)
    # integrated_intensities = np.array(integrated_intensities)
    # Initialize lists to store the results
    # fitted_amplitudes = []
    # for coord in reordered_nv_coords:
    #     fitted_x, fitted_y, amplitude = fit_gaussian(img_array, coord, window_size=2)
    #     fitted_amplitudes.append(amplitude)

    # Calculate weights based on the fitted intensities
    spot_weights = linear_weights(reordered_intensities, alpha=0.6)
    updated_spot_weights = spot_weights

    # spot_weights = linear_weights(filtered_intensities, alpha=0.2)
    # spot_weights = non_linear_weights_adjusted(
    #     filtered_intensities, alpha=0.9, beta=0.3, threshold=0.9
    # )
    # spot_weights = sigmoid_weights(filtered_intensities, threshold=0, beta=0.005)
    # Print some diagnostics
    # Update spot weights for NVs with low fidelity

    # Calculate the spot weights based on the integrated intensities
    # spot_weights = non_linear_weights(filtered_intensities, alpha=0.9)
    # Define the NV indices you want to update
    # indices_to_update = [11, 14, 18, 19, 25, 30, 36, 42, 43, 45, 48, 56, 72]
    # indices_to_update = np.arange(0, 77).tolist()
    # Calculate the updated spot weights
    # updated_spot_weights = manual_sigmoid_weight_update(
    #     spot_weights,
    #     integrated_intensities,
    #     alpha=0.9,
    #     beta=6.0,
    #     update_indices=indices_to_update,
    # )
    snr = [
        0.833,
        0.975,
        0.66,
        1.386,
        1.203,
        1.208,
        0.655,
        1.16,
        1.339,
        0.956,
        0.889,
        1.112,
        1.276,
        1.177,
        1.122,
        0.929,
        0.639,
        1.003,
        0.23,
        1.219,
        0.955,
        1.284,
        0.805,
        1.359,
        1.161,
        1.124,
        0.728,
        1.103,
        1.184,
        1.08,
        1.119,
        1.236,
        1.035,
        1.374,
        1.152,
        0.977,
        1.123,
        1.175,
        1.117,
        1.102,
        1.055,
        0.73,
        1.072,
        1.028,
        0.812,
        0.492,
        1.311,
        1.386,
        1.176,
        0.817,
        1.165,
        1.306,
        1.334,
        1.161,
        1.066,
        1.159,
        1.313,
        1.353,
        1.198,
        1.129,
        1.299,
        1.09,
        1.136,
        1.099,
        1.261,
        1.05,
        0.892,
        0.642,
        1.283,
        1.265,
        1.23,
        1.081,
        0.871,
        0.908,
        0.722,
        0.721,
        0.885,
        1.078,
        1.102,
        1.168,
        1.103,
        1.147,
        1.007,
        0.603,
        1.205,
        1.214,
        1.149,
        1.171,
        1.332,
        1.194,
        1.601,
        1.2,
        0.849,
        1.264,
        1.216,
        1.077,
        1.023,
        1.273,
        1.188,
        1.042,
        1.168,
        0.948,
        1.158,
        1.247,
        1.246,
        0.989,
        1.203,
        1.053,
        1.171,
        1.333,
        0.273,
        0.5,
        1.171,
        1.16,
        1.143,
        0.272,
        0.965,
        1.168,
        1.176,
        0.401,
        1.147,
        0.891,
        1.221,
        1.17,
        0.713,
        0.537,
        0.991,
        0.925,
        1.059,
        0.894,
        1.234,
        0.913,
        0.975,
        1.007,
        0.684,
        0.992,
        1.196,
        0.354,
        1.101,
        0.825,
        0.857,
        0.096,
        0.121,
        0.772,
    ]
    # updated_spot_weights = adjust_weights_sigmoid(
    #     spot_weights, snr, alpha=0.0, beta=0.3
    # )

    # Get indices of NVs that meet the SNR threshold
    threshold = 0.7
    filtered_indices = filter_by_snr(snr, threshold)

    # Filter NV coordinates and associated data based on these indices
    filtered_nv_coords = [reordered_nv_coords[i] for i in filtered_indices]
    filtered_spot_weights = [spot_weights[i] for i in filtered_indices]
    filtered_integrated_intensities = [
        integrated_intensities[i] for i in filtered_indices
    ]
    print(f"Filtered NV coordinates: {len(filtered_nv_coords)} NVs")
    # print("NV Index | Spot Weight | Updated Spot Weight | Counts")
    # print("-" * 50)
    # for idx, (weight, updated_weight, counts) in enumerate(
    #     zip(spot_weights, updated_spot_weights, reordered_intensities)
    # ):
    #     print(f"{idx:<8} | {weight:.3f} | {updated_weight:.3f} | {counts:.3f}")
    # print(f"NV Coords: {filtered_nv_coords}")
    # print(f"Filtered integrated intensities: {filtered_intensities}")
    # print(f"Normalized spot weights: {spot_weights}")
    # print(f"Normalized spot weights: {updated_spot_weights}")
    # print(f"Number of NVs detected: {len(filtered_nv_coords)}")

    # Save the filtered results
    # save_results(
    #     filtered_nv_coords,
    #     filtered_counts,
    #     spot_weights,
    #     filename="slmsuite/nv_blob_detection/nv_blob_filtered_297.npz",
    # )
    # save_results(
    #     filtered_nv_coords,
    #     filtered_integrated_intensities,
    #     filtered_spot_weights,
    #     filename="slmsuite/nv_blob_detection/nv_blob_filtered_128nvs_updated.npz",
    # )

    # Plot the original image with circles around each NV
    fig, ax = plt.subplots()
    title = "24ms, Ref"
    kpl.imshow(ax, img_array, title=title, cbar_label="Photons")
    # Draw circles and index numbers
    for idx, coord in enumerate(filtered_nv_coords):
        circ = Circle(coord, sigma, color="lightblue", fill=False, linewidth=0.5)
        ax.add_patch(circ)
        # Place text just above the circle
        ax.text(
            coord[0],
            coord[1] - sigma - 1,
            str(idx),
            color="white",
            fontsize=8,
            ha="center",
        )

    # # Plot histogram of the filtered integrated intensities using Seaborn
    # sns.set(style="whitegrid")

    # plt.figure(figsize=(6, 5))
    # sns.histplot(filtered_counts, bins=45, kde=False, color="blue")

    # plt.xlabel("Integrated Intensity")
    # plt.ylabel("Frequency")
    # plt.title("Histogram of Filtered Integrated Counts")
    plt.show(block=True)