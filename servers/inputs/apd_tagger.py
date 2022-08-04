# -*- coding: utf-8 -*-
"""
Input server for APDs running into the Time Tagger.

Created on Wed Apr 24 22:07:25 2019

@author: mccambria

### BEGIN NODE INFO
[info]
name = apd_tagger
version = 1.0
description =

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 5
### END NODE INFO
"""


from labrad.server import LabradServer
from labrad.server import setting
from twisted.internet.defer import ensureDeferred
import TimeTagger
from numpy import count_nonzero, nonzero, concatenate
import numpy as np
import logging
import re
import time
import socket
# from pathos.multiprocessing import ProcessingPool as Pool


class ApdTagger(LabradServer):
    name = "apd_tagger"
    pc_name = socket.gethostname()

    def initServer(self):
        filename = (
            "E:/Shared drives/Kolkowitz Lab"
            " Group/nvdata/pc_{}/labrad_logging/{}.log"
        )
        filename = filename.format(self.pc_name, self.name)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%y-%m-%d_%H-%M-%S",
            filename=filename,
        )
        self.reset_tag_stream_state()
        config = ensureDeferred(self.get_config())
        config.addCallback(self.on_get_config)

    async def get_config(self):
        p = self.client.registry.packet()
        p.cd(["", "Config", "DeviceIDs"])
        p.get("time_tagger_serial")
        p.cd(["", "Config", "Wiring", "Tagger"])
        p.get("di_clock")
        p.dir()
        result = await p.send()
        return result

    def on_get_config(self, config):
        get_result = config["get"]
        tagger_serial = get_result[0]
        try:
            self.tagger = TimeTagger.createTimeTagger(tagger_serial)
        except Exception as e:
            logging.info(e)
        self.tagger.reset()
        # The APDs share a clock, but everything else is distinct
        self.tagger_di_clock = get_result[1]
        # Determine how many APDs we're supposed to set up
        apd_sub_dirs = []
        apd_indices = []
        sub_dirs = config["dir"][0]
        for sub_dir in sub_dirs:
            if re.fullmatch(r"Apd_[0-9]+", sub_dir):
                apd_sub_dirs.append(sub_dir)
                apd_indices.append(int(sub_dir.split("_")[1]))
        if len(apd_sub_dirs) > 0:
            wiring = ensureDeferred(self.get_wiring(apd_sub_dirs))
            wiring.addCallback(self.on_get_wiring, apd_indices)

    async def get_wiring(self, apd_sub_dirs):
        p = self.client.registry.packet()
        for sub_dir in apd_sub_dirs:
            p.cd(["", "Config", "Wiring", "Tagger", sub_dir])
            p.get("di_apd")
            p.get("di_gate")
        result = await p.send()
        return result["get"]

    def on_get_wiring(self, wiring, apd_indices):
        self.tagger_di_apd = {}
        self.tagger_di_gate = {}
        # Loop through the available APDs
        for loop_index in range(len(apd_indices)):
            apd_index = apd_indices[loop_index]
            wiring_index = 2 * loop_index
            di_apd = wiring[wiring_index]
            self.tagger_di_apd[apd_index] = di_apd
            di_gate = wiring[wiring_index + 1]
            self.tagger_di_gate[apd_index] = di_gate
        self.reset_tag_stream_state()  # Initialize state variables
        self.reset(None)
        logging.info("init complete")

    def read_raw_stream(self):
        if self.stream is None:
            logging.error("read_raw_stream attempted while stream is None.")
            return
        buffer = self.stream.getData()
        # Monitor overflows for both the Time Tagger's onboard buffer
        # and the software buffer that the stream feeds into on our PC
        num_hardware_overflows = self.tagger.getOverflowsAndClear()
        has_software_overflows = buffer.hasOverflows
        if (num_hardware_overflows > 0) or has_software_overflows:
            logging.info(f"Num hardware overflows: {num_hardware_overflows}")
            logging.info(f"Has software overflows: {has_software_overflows}")
        timestamps = buffer.getTimestamps()
        channels = buffer.getChannels()
        return timestamps, channels

    def read_counter_setting_internal(self, num_to_read):
        if self.stream is None:
            logging.error("read_counter attempted while stream is None.")
            return
        if num_to_read is None:
            # Poll once and return the result
            counts = self.read_counter_internal()
        else:
            # Poll until we've read the requested number of samples
            counts = []
            while len(counts) < num_to_read:
                counts.extend(self.read_counter_internal())
            if len(counts) > num_to_read:
                msg = "Read {} samples, only requested {}".format(
                    len(counts), num_to_read
                )
                logging.error(msg)

        return counts

    def get_gate_click_inds(self, sample_channels_arr, apd_index):

        open_channel = self.tagger_di_gate[self.stream_apd_indices[apd_index]]
        close_channel = -open_channel

        # Find gate open clicks
        open_inds = nonzero(sample_channels_arr == open_channel)[0].tolist()

        # Find gate close clicks
        # Gate close channel is negative of gate open channel,
        # signifying the falling edge
        close_inds = nonzero(sample_channels_arr == close_channel)[0].tolist()

        return open_inds, close_inds

    def append_apd_channel_counts(
        self, gate_inds, apd_index, sample_channels, sample_counts_append
    ):
        # The zip must be recreated each time we want to use it
        # since the generator it returns is a single-use object for
        # memory reasons.
        gate_zip = zip(gate_inds[0], gate_inds[1])
        apd_channel = self.tagger_di_apd[apd_index]
        count_lambda = lambda gate: count_nonzero(sample_channels[gate[0]: gate[1]] == apd_channel)
        # with Pool() as p:
        #     channel_counts = p.map(count_lambda, gate_zip)
        # channel_counts = [
        #     count_nonzero(sample_channels[open_ind:close_ind] == apd_channel)
        #     for open_ind, close_ind in gate_zip
        # ]
        channel_counts = [count_lambda(gate) for gate in gate_zip]
        sample_counts_append(channel_counts)

    def read_counter_internal(self):
        """
        This is the core counter function for the Time Tagger. It needs to be
        fast since we often have a high data rate (say, 1 million counts per
        second). If it's not fast enough, we may encounter unexpected behavior,
        like certain samples returning 0 counts when clearly they should return
        something > 0. As such, this function is already highly optimized. The
        main approach is to use lambda functions and built-ins that map from 
        Python to some other language (like how list comprehension runs in C) 
        since Python is so slow. So beware of messing around here. 
        """

        if self.stream is None:
            logging.error(
                "read_counter_internal attempted while stream is None."
            )
            return

        # channels is an array
        _, channels = self.read_raw_stream()

        # Find clock clicks (sample breaks)
        result = nonzero(channels == self.tagger_di_clock)
        clock_click_inds = result[0].tolist()

        previous_sample_end_ind = None
        sample_end_ind = None

        # Counts will be a list of lists - the first dimension will divide
        # samples and the second will divide gatings within samples
        return_counts = []
        return_counts_append = return_counts.append

        for clock_click_ind in clock_click_inds:

            # Clock clicks end samples, so they should be included with the
            # sample itself
            sample_end_ind = clock_click_ind + 1

            # Get leftovers and make sure we've got an array for comparison
            # to find click indices
            if previous_sample_end_ind is None:
                join_tuple = (
                    self.leftover_channels,
                    channels[0:sample_end_ind],
                )
                sample_channels = concatenate(join_tuple)
            else:
                sample_channels = channels[
                    previous_sample_end_ind:sample_end_ind
                ]

            sample_counts = []
            sample_counts_append = sample_counts.append

            # Get all the gates once and then count for each APD individually
            if self.stream_single_gate:
                gate_inds = self.get_gate_click_inds(sample_channels, 0)
                for apd_index in self.stream_apd_indices:
                    self.append_apd_channel_counts(
                        gate_inds,
                        apd_index,
                        sample_channels,
                        sample_counts_append,
                    )

            # Loop through the APDs, getting the gates for each APD
            else:
                for apd_index in self.stream_apd_indices:
                    gate_inds = self.get_gate_click_inds(
                        sample_channels, apd_index
                    )
                    self.append_apd_channel_counts(
                        gate_inds,
                        apd_index,
                        sample_channels,
                        sample_counts_append,
                    )

            return_counts_append(sample_counts)
            previous_sample_end_ind = sample_end_ind

        if sample_end_ind is None:
            # No samples were clocked - add everything to leftovers
            self.leftover_channels.extend(channels)
        else:
            # Reset leftovers from the last sample clock
            self.leftover_channels = channels[sample_end_ind:].tolist()

        return return_counts

    def stop_tag_stream_internal(self):
        if self.stream is not None:
            self.stream.stop()
        self.reset_tag_stream_state()

    def reset_tag_stream_state(self):
        self.stream = None
        self.stream_apd_indices = []
        self.stream_channels = []
        self.leftover_channels = []

    @setting(0, returns="*i")
    def get_channel_mapping(self, c):
        """As a regexp, the order is:
        [+APD, *[gate open, gate close], ?clock]
        Whether certain channels will be present/how many channels of a given
        type will be present is based on the channels passed to
        start_tag_stream.
        """
        return self.stream_channels

    @setting(1, apd_indices="*i", gate_indices="*i", clock="b")
    def start_tag_stream(self, c, apd_indices, gate_indices=None, clock=True):
        """Expose a raw tag stream which can be read with read_tag_stream and
        closed with stop_tag_stream.
        """

        # Make sure the existing stream is stopped and we have fresh state
        if self.stream is not None:
            logging.warning(
                "New stream started before existing stream was "
                "stopped. Stopping existing stream."
            )
            self.stop_tag_stream_internal()
        else:
            self.reset_tag_stream_state()

        channels = []
        for ind in apd_indices:
            channels.append(self.tagger_di_apd[ind])
        # If gate_indices is unspecified, add gates for all the
        # passed APDs by default
        if gate_indices is None:
            gate_indices = apd_indices
        for ind in gate_indices:
            gate_channel = self.tagger_di_gate[ind]
            channels.append(gate_channel)  # rising edge
            channels.append(-gate_channel)  # falling edge
        if clock:
            channels.append(self.tagger_di_clock)
        # Store in state before de-duplication to preserve order
        self.stream_channels = channels
        # De-duplicate the channels list
        channels = list(set(channels))
        self.stream = TimeTagger.TimeTagStream(
            self.tagger, 10 ** 8, channels
        )
        # When you set up a measurement, it will not start recording data
        # immediately. It takes some time for the tagger to configure the fpga,
        # etc. The sync call waits until this process is complete.
        self.tagger.sync()
        self.stream_apd_indices = apd_indices

        # If all APDs are running off the same gate, we can make things faster
        active_gates = [self.tagger_di_gate[ind] for ind in apd_indices]
        self.stream_single_gate = len(set(active_gates)) == 1

    @setting(2)
    def stop_tag_stream(self, c):
        """Closes the stream started with start_tag_stream. Resets
        leftovers.
        """
        self.stop_tag_stream_internal()

    @setting(9)
    def clear_buffer(self, c):
        """Clear the hardware's internal buffer. Should be called before
        starting a pulse sequence."""
        buffer = self.stream.getData()
        # We also don't care about overflows here, so toss (but log) those
        num_hardware_overflows = self.tagger.getOverflowsAndClear()
        has_software_overflows = buffer.hasOverflows
        if (num_hardware_overflows > 0) or has_software_overflows:
            logging.info(f"Num hardware overflows: {num_hardware_overflows}")
            logging.info(f"Has software overflows: {has_software_overflows}")

    # @setting(3, num_to_read="i", returns="*s*i")
    # def read_tag_stream(self, c, num_to_read=None):
    #     """Read the stream started with start_tag_stream. Returns two lists,
    #     each as long as the number of counts that have occurred since the
    #     buffer was refreshed. First list is timestamps in ps, second is
    #     channel names
    #     """
    #     if self.stream is None:
    #         logging.error("read_tag_stream attempted while stream is None.")
    #         return
    #     if num_to_read is None:
    #         timestamps, channels = self.read_raw_stream()
    #     else:
    #         timestamps = []
    #         channels = []
    #         # logging.info("Start")
    #         while True:
    #             num_read = np.count_nonzero(np.array(channels) == self.tagger_di_clock)
    #             # logging.info("num_read: {}".format(num_read))
    #             if num_read >= num_to_read:
    #                 break 
    #             timestamps_chunk, channels_chunk = self.read_raw_stream()
    #             timestamps.extend(timestamps_chunk.tolist())
    #             channels.extend(channels_chunk.tolist())
    #         timestamps = np.array(timestamps)
    #         channels = np.array(channels)
    #     # Convert timestamps to strings since labrad does not support int64s
    #     # It must be converted to int64s back on the client
    #     timestamps = timestamps.astype(str).tolist()
    #     return timestamps, channels

    @setting(3, num_to_read="i", returns="*s*i")
    def read_tag_stream(self, c, num_to_read=None):
        """Read the stream started with start_tag_stream. Returns two lists,
        each as long as the number of counts that have occurred since the
        buffer was refreshed. First list is timestamps in ps, second is
        channel names
        """
        if self.stream is None:
            logging.error("read_tag_stream attempted while stream is None.")
            return
        if num_to_read is None:
            timestamps, channels = self.read_raw_stream()
        else:
            timestamps = np.array([], dtype=np.int64)
            channels = np.array([], dtype=int)
            num_read = 0
            while True:
                timestamps_chunk, channels_chunk = self.read_raw_stream()
                timestamps = np.append(timestamps, timestamps_chunk)
                channels = np.append(channels, channels_chunk)
                # Check if we've read enough samples
                new_num_read = np.count_nonzero(channels_chunk == self.tagger_di_clock)
                num_read += new_num_read
                if num_read >= num_to_read:
                    break 
        # Convert timestamps to strings since labrad does not support int64s
        # It must be converted to int64s back on the client
        timestamps = timestamps.astype(str).tolist()
        return timestamps, channels

    @setting(4, num_to_read="i", returns="*3w")
    def read_counter_complete(self, c, num_to_read=None):
        return self.read_counter_setting_internal(num_to_read)

    @setting(5, num_to_read="i", returns="*w")
    def read_counter_simple(self, c, num_to_read=None):

        complete_counts = self.read_counter_setting_internal(num_to_read)

        # To combine APDs we assume all the APDs have the same gate
        gate_channels = list(self.tagger_di_gate.values())
        first_gate_channel = gate_channels[0]
        if not all(val == first_gate_channel for val in gate_channels):
            logging.critical("Combined counts from APDs with different gates.")

        # Just find the sum of each sample in complete_counts
        return_counts = [
            np.sum(sample, dtype=int) for sample in complete_counts
        ]

        return return_counts

    @setting(6, num_to_read="i", returns="*2w")
    def read_counter_separate_gates(self, c, num_to_read=None):

        complete_counts = self.read_counter_setting_internal(num_to_read)
        # logging.info(complete_counts)

        # To combine APDs we assume all the APDs have the same gate
        gate_channels = list(self.tagger_di_gate.values())
        first_gate_channel = gate_channels[0]
        if not all(val == first_gate_channel for val in gate_channels):
            logging.critical("Combined counts from APDs with different gates.")

        # Add the APD counts as vectors for each sample in complete_counts
        return_counts = [
            np.sum(sample, 0, dtype=int).tolist()
            for sample in complete_counts
        ]

        return return_counts

    @setting(11, modulus="i", num_to_read="i", returns="*2w")
    def read_counter_modulo_gates(self, c, modulus, num_to_read=None):

        complete_counts = self.read_counter_setting_internal(num_to_read)
        # logging.info(complete_counts)

        # To combine APDs we assume all the APDs have the same gate
        gate_channels = list(self.tagger_di_gate.values())
        first_gate_channel = gate_channels[0]
        if not all(val == first_gate_channel for val in gate_channels):
            logging.critical("Combined counts from APDs with different gates.")

        # Add the APD counts as vectors for each sample in complete_counts
        # sum_lambda = lambda arg: np.sum(arg, 0, dtype=int).tolist()
        # with Pool() as p:
        #     separate_gate_counts = p.map(sum_lambda, complete_counts)
        separate_gate_counts = [np.sum(el, 0, dtype=int).tolist() for el in complete_counts]
        
        # Run the modulus
        return_counts = []
        for sample in separate_gate_counts:
            sample_list = []
            for ind in range(modulus):
                sample_list.append(np.sum(sample[ind::modulus]))
            return_counts.append(sample_list)

        return return_counts

    @setting(7, num_to_read="i", returns="*2w")
    def read_counter_separate_apds(self, c, num_to_read=None):

        complete_counts = self.read_counter_setting_internal(num_to_read)

        # Just find the sum of the counts for each APD for each
        # sample in complete_counts
        return_counts = [
            [np.sum(apd_counts, dtype=int) for apd_counts in sample]
            for sample in complete_counts
        ]

        return return_counts

    @setting(8)
    def reset(self, c):
        self.stop_tag_stream_internal()

__server__ = ApdTagger()

if __name__ == "__main__":
    from labrad import util

    util.runServer(__server__)
