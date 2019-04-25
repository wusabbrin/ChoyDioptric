# -*- coding: utf-8 -*-
"""
g(2) routine. For each event on one channel, calculates the deltas relative to
the events on the opposite channel and plots a histogram of the deltas. Here
the events are photon detections from the same source, but split over two
APDs. The splitting is necessary to compensate for the APD dead time, which
is typically significantly longer than the lifetime of the excited state we
are interested in.

Created on Wed Apr 24 17:33:26 2019

@author: mccambria
"""

# %% Imports


import utils.tool_belt as tool_belt
import numpy
import matplotlib.pyplot as plt
import time


# %% Functions


def process_raw_buffer(buffer, diff_window, afterpulse_window,
                       differences_append, apd_a_index, apd_b_index):

    # Couple shorthands to speed up the calculation
    buffer_tagTimestamps = buffer.tagTimestamps
    buffer_tagChannels = buffer.tagChannels
    buffer_size = buffer.size

    indices_to_delete = []
    indices_to_delete_append = indices_to_delete.append

    # Throw out probable afterpulses
    for click_index in range(buffer.size):

        click_time = buffer_tagTimestamps[click_index]

        # Determine the afterpulse channel
        click_channel = buffer_tagChannels[click_index]

        # Calculate relevant differences
        next_index = click_index + 1
        while next_index < buffer_size:
            diff = buffer_tagTimestamps[next_index] - click_time
            if diff > afterpulse_window:
                break
            if buffer_tagChannels[next_index] == click_channel:
                indices_to_delete_append(next_index)
            next_index += 1

    buffer_tagTimestamps = numpy.delete(buffer_tagTimestamps, indices_to_delete)
    buffer_tagChannels = numpy.delete(buffer_tagChannels, indices_to_delete)

    # Calculate differences
    num_vals = buffer_tagTimestamps.size
    for click_index in range(num_vals):

        click_time = buffer_tagTimestamps[click_index]

        # Determine the channel to take the difference with
        click_channel = buffer_tagChannels[click_index]
        if click_channel == apd_a_index:
            diff_channel = apd_b_index
        else:
            diff_channel = apd_a_index

        # Calculate relevant differences
        next_index = click_index + 1
        while next_index < num_vals:  # Don't go past the buffer end
            # Stop taking differences past the diff window
            diff = buffer_tagTimestamps[next_index] - click_time
            if diff > diff_window:
                break
            # Only record the diff between opposite chanels
            if buffer_tagChannels[next_index] == diff_channel:
                # Flip the sign for diffs relative to channel 2
                if click_channel == apd_b_index:
                    diff = -diff
                differences_append(diff)
            next_index += 1


# %% Main


def main(cxn, name, coords, apd_a_index, apd_b_index):

    # %% Initial calculations and setup


    run_time = 60 * 7
#    run_time = 30
    sleep_time = 2
    afterpulse_window = 50 * 10**3
    diff_window = 100 * 10**3  # 100 ns in ps

    # Set xyz and open the AOM
    tool_belt.set_xyz(cxn, coords)
    cxn.pulse_streamer.constant()

    total_size = 0
    collect_time = 0
    collection_index = 0

    apd_indices = [apd_a_index, apd_b_index]

    differences = []  # Create a list to hold the differences
    differences_append = differences.append  # Skip unnecessary lookup
    buffer = None
    num_bins = int((2 * diff_window) / 1000)  # 1 ns bins in ps

    # %% Collect the data

    start_time = time.time()
    start_calc_time = start_time
    tool_belt.init_safe_stop()

    # Python does not have do-while loops so we will use something like
    # a while True
    cxn.apd_tagger.start_tag_stream(apd_indices)  # Expose an initial stream
    stop = False
    while not stop:

        # Wait until some data has filled
        now = time.time()
        time_elapsed = now - start_calc_time
        time.sleep(max(sleep_time - time_elapsed, 0))

        # Read the stream and
        buffer = cxn.apd_tagger.read_tag_stream()

        # Check if we should stop
        if (time.time() - start_time > run_time) or tool_belt.safe_stop():
            stop = True
        else:
            # Expose a new stream so that we collect data while calculating
            cxn.apd_tagger.start_tag_stream(apd_indices)

        # Process data
        start_calc_time = time.time()
        process_raw_buffer(buffer, diff_window, afterpulse_window,
                           differences_append, apd_a_index, apd_b_index)

        # Create/update the histogram
        if collection_index == 1:
            fig, ax = plt.subplots()
            hist, bin_edges = numpy.histogram(differences, num_bins)
            bin_edges = bin_edges / 1000  # ps to ns
            bin_center_offset = (bin_edges[1] - bin_edges[0]) / 2
            bin_centers = bin_edges[0: num_bins] + bin_center_offset
            ax.plot(bin_centers, hist)
            ax.set_xlabel('Time (ns)')
            ax.set_ylabel('Differences')
            ax.set_title(r'$g^{(2)}(\tau)$')
            fig.tight_layout()
            fig.canvas.draw()
            fig.canvas.flush_events()
        elif collection_index > 1:
            hist, bin_edges = numpy.histogram(differences, num_bins)
            tool_belt.update_line_plot_figure(fig, hist)

        collection_index += 1
        total_size += buffer.size

    # %% Save the data

    int_differences = list(map(int, differences))

    raw_data = {'name': name,
                'coords': coords,
                'differences': int_differences,
                'total_size': total_size,
                'collect_time': collect_time}

    timeStamp = tool_belt.get_time_stamp()
    filePath = tool_belt.get_file_path('g2_measurement', timeStamp, name)
    tool_belt.save_figure(fig, filePath)
    tool_belt.save_raw_data(raw_data, filePath)
