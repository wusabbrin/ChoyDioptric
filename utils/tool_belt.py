# -*- coding: utf-8 -*-
"""This file contains functions, classes, and other objects that are useful
in a variety of contexts. Since they are expected to be used in many
files, I put them all in one place so that they don't have to be redefined
in each file.

Created on November 23rd, 2018

@author: mccambria
"""

# region Imports and constants

import os
import csv
from datetime import datetime
import numpy as np
from numpy import exp
import json
import time
import labrad
from pathlib import Path, PurePath
from enum import Enum, IntEnum, auto
import socket
import smtplib
from email.mime.text import MIMEText
import traceback
import keyring
import math
import sys
sys.path.insert(0, 'C:\\Users\\choyl\\ChoyDioptric')  # Add parent directory to path
import utils.common as common
import utils.search_index as search_index
import signal
import copy
from decimal import Decimal
# from git import Repo


class States(Enum):
    LOW = auto()
    ZERO = auto()
    HIGH = auto()


# Normalization style for comparing experimental data to reference data
class NormStyle(Enum):
    SINGLE_VALUED = auto()  # Use a single-valued reference
    POINT_TO_POINT = auto()  # Normalize each signal point by its own reference


class ModTypes(Enum):
    DIGITAL = auto()
    ANALOG = auto()


class Digital(IntEnum):
    LOW = 0
    HIGH = 1


Boltzmann = 8.617e-2  # meV / K

# endregion
# region Laser utils


def get_mod_type(laser_name):
    with labrad.connect() as cxn:
        mod_type = common.get_registry_entry(
            cxn, "mod_type", ["", "Config", "Optics", laser_name]
        )
    mod_type = eval(mod_type)
    return mod_type.name


def laser_off(cxn, laser_name):
    laser_switch_sub(cxn, False, laser_name)


def laser_on(cxn, laser_name, laser_power=None):
    laser_switch_sub(cxn, True, laser_name, laser_power)


def get_opx_laser_pulse_info(config, laser_name, laser_power):
    mod_type = config["Optics"][laser_name]["mod_type"]
    laser_delay = config["Optics"][laser_name]["delay"]

    laser_pulse_name = "laser_ON_{}".format(eval(mod_type).name)

    if eval(mod_type).name == "ANALOG":
        laser_pulse_amplitude = laser_power

    elif eval(mod_type).name == "DIGITAL":
        if laser_power == 0:
            laser_pulse_name = "laser_OFF_{}".format(eval(mod_type).name)
            laser_pulse_amplitude = 1
        else:
            laser_pulse_amplitude = 1

    return laser_pulse_name, laser_delay, laser_pulse_amplitude


def laser_switch_sub(cxn, turn_on, laser_name, laser_power=None):
    mod_type = common.get_registry_entry(
        cxn, "mod_type", ["", "Config", "Optics", laser_name]
    )
    mod_type = eval(mod_type)
    pulse_gen = get_server_pulse_gen(cxn)

    if mod_type is ModTypes.DIGITAL:
        if turn_on:
            laser_chan = common.get_registry_entry(
                cxn,
                "do_{}_dm".format(laser_name),
                ["", "Config", "Wiring", "PulseGen"],
            )
            pulse_gen.constant([laser_chan])
    elif mod_type is ModTypes.ANALOG:
        if turn_on:
            laser_chan = common.get_registry_entry(
                cxn,
                "ao_{}_am".format(laser_name),
                ["", "Config", "Wiring", "PulseGen"],
            )
            if laser_chan == 0:
                pulse_gen.constant([], laser_power, 0.0)
            elif laser_chan == 1:
                pulse_gen.constant([], 0.0, laser_power)

    # If we're turning things off, turn everything off. If we wanted to really
    # do this nicely we'd find a way to only turn off the specific channel,
    # but it's not worth the effort.
    if not turn_on:
        pulse_gen.constant([])


def set_laser_power(
    cxn, nv_sig=None, laser_key=None, laser_name=None, laser_power=None
):
    """Set a laser power, or return it for analog modulation.
    Specify either a laser_key/nv_sig or a laser_name/laser_power.
    """

    if (nv_sig is not None) and (laser_key is not None):
        laser_name = nv_sig[laser_key]
        power_key = "{}_power".format(laser_key)
        # If the power isn't specified, then we assume it's set some other way
        if power_key in nv_sig:
            laser_power = nv_sig[power_key]
    elif (laser_name is not None) and (laser_power is not None):
        pass  # All good
    else:
        raise Exception(
            "Specify either a laser_key/nv_sig or a laser_name/laser_power."
        )

    # If the power is controlled by analog modulation, we'll need to pass it
    # to the pulse streamer
    mod_type = common.get_registry_entry(
        cxn, "mod_type", ["", "Config", "Optics", laser_name]
    )
    mod_type = eval(mod_type)
    if mod_type == ModTypes.ANALOG:
        return laser_power
    else:
        laser_server = get_filter_server(cxn, laser_name)
        if (laser_power is not None) and (laser_server is not None):
            laser_server.set_laser_power(laser_power)
        return None


def get_opx_uwave_pulse_info(config, pulse_time):
    pulse_time_cc = int(round(pulse_time / 4))

    if pulse_time_cc < 4:
        uwave_pulse = "uwave_OFF"
        uwave_amp = 1
        uwave_time_cc = 4

    elif pulse_time_cc >= 4:
        uwave_pulse = "uwave_ON"
        uwave_amp = 1
        uwave_time_cc = pulse_time_cc

    return uwave_pulse, uwave_amp, uwave_time_cc


def set_filter(cxn, nv_sig=None, optics_key=None, optics_name=None, filter_name=None):
    """optics_key should be either 'collection' or a laser key.
    Specify either an optics_key/nv_sig or an optics_name/filter_name.
    """

    if (nv_sig is not None) and (optics_key is not None):
        if optics_key in nv_sig:
            optics_name = nv_sig[optics_key]
        else:
            optics_name = optics_key
        filter_key = "{}_filter".format(optics_key)
        # Just exit if there's no filter specified in the nv_sig
        if filter_key not in nv_sig:
            return
        filter_name = nv_sig[filter_key]
        if filter_name is None:
            return
    elif (optics_name is not None) and (filter_name is not None):
        pass  # All good
    else:
        raise Exception(
            "Specify either an optics_key/nv_sig or an" " optics_name/filter_name."
        )

    filter_server = get_filter_server(cxn, optics_name)
    if filter_server is None:
        return
    pos = common.get_registry_entry(
        cxn,
        filter_name,
        ["", "Config", "Optics", optics_name, "FilterMapping"],
    )
    # print(filter_server)
    # print(pos)
    filter_server.set_filter(pos)


def get_filter_server(cxn, optics_name):
    """Try to get a filter server. If there isn't one listed on the registry,
    just return None.
    """
    try:
        server_name = common.get_registry_entry(
            cxn, "filter_server", ["", "Config", "Optics", optics_name]
        )
        return getattr(cxn, server_name)
    except Exception:
        return None


def get_laser_server(cxn, laser_name):
    """Try to get a laser server. If there isn't one listed on the registry,
    just return None.
    """
    try:
        server_name = common.get_registry_entry(
            cxn, "laser_server", ["", "Config", "Optics", laser_name]
        )
        # print(getattr(cxn, server_name))
        return getattr(cxn, server_name)
    except Exception:
        return None


# def process_laser_seq(pulse_streamer, seq, config, laser_name, laser_power, train):
#     """Some lasers may require special processing of their Pulse Streamer
#     sequence. For example, the Cobolt lasers expect 3.5 V for digital
#     modulation, but the Pulse Streamer only supplies 2.6 V.
#     """

#     pulser_wiring = config["Wiring"]["PulseGen"]
#     # print(config)
#     mod_type = config["Optics"][laser_name]["mod_type"]
#     mod_type = eval(mod_type)

#     processed_train = []

#     if mod_type is ModTypes.DIGITAL:
#         processed_train = train.copy()
#         pulser_laser_mod = pulser_wiring["do_{}_dm".format(laser_name)]
#         seq.setDigital(pulser_laser_mod, processed_train)

#     # Analog, convert LOW / HIGH to 0.0 / analog voltage
#     # currently can't handle multiple powers of the AM within the same sequence
#     # Possibly, we could pass laser_power as a list, and then build the sequences
#     # for each power (element) in the list.
#     elif mod_type is ModTypes.ANALOG:
#         high_count = 0
#         for el in train:
#             dur = el[0]
#             val = el[1]
#             if type(laser_power) == list:
#                 if val == 0:
#                     power_dict = {Digital.LOW: 0.0}
#                 else:
#                     power_dict = {Digital.HIGH: laser_power[high_count]}
#                     if val == Digital.HIGH:
#                         high_count += 1
#             # If a list wasn't passed, just use the single value for laser_power
#             elif type(laser_power) != list:
#                 power_dict = {Digital.LOW: 0.0, Digital.HIGH: laser_power}
#             processed_train.append((dur, power_dict[val]))

#         pulser_laser_mod = pulser_wiring["ao_{}_am".format(laser_name)]
#         # print(processed_train)
#         seq.setAnalog(pulser_laser_mod, processed_train)


# endregion
# region Pulse generator utils


def process_laser_seq(pulse_streamer, seq, config, laser_name, laser_power, train):
    """
    Some lasers may require special processing of their Pulse Streamer
    sequence. For example, the Cobolt lasers expect 3.5 V for digital
    modulation, but the Pulse Streamer only supplies 2.6 V.
    """
    pulser_wiring = config["Wiring"]["PulseGen"]
    # print(config)
    if laser_name not in config["Optics"]:
        return 
    mod_type = config["Optics"][laser_name]["mod_type"]
    mod_type = eval(mod_type)
    if "am_feedthrough" in config["Optics"][laser_name]:
        am_feedthrough = config["Optics"][laser_name]["am_feedthrough"]
        am_feedthrough = eval(am_feedthrough)
    else:
        am_feedthrough = False

    # LOW = 0
    # HIGH = 1

    processed_train = []
    # Digital, feedthrough, bookend each pulse with 100 ns clock pulses
    # Assumes we always leave the laser on (or off) for at least 100 ns
    if am_feedthrough:
        # Collapse the sequence so that no two adjacent elements have the
        # same value
        collapsed_train = []
        ind = 0
        len_train = len(train)
        while ind < len_train:
            el = train[ind]
            dur = el[0]
            val = el[1]
            next_ind = ind + 1
            while next_ind < len_train:
                next_el = train[next_ind]
                next_dur = next_el[0]
                next_val = next_el[1]
                # If the next element shares the same value as the current
                # one, combine them
                if next_val == val:
                    dur += next_dur
                    next_ind += 1
                else:
                    break
            # Append the current pulse and start back
            # where we left off
            collapsed_train.append((dur, val))
            ind = next_ind
        # print(pulse_streamer)
        # Check if this is just supposed to be always on
        if (len(collapsed_train) == 1) and (collapsed_train[0][1] == Digital.HIGH):
            if pulse_streamer is not None:
                # pulse_streamer.client[laser_name].laser_on(laser_power)
                pulse_streamer.laser_LGLO_589.laser_on(laser_power)
            return
        # Set up the bookends
        # print(collapsed_train)
        for ind in range(len(collapsed_train)):
            el = collapsed_train[ind]
            dur = el[0]
            val = el[1]
            # print(Digital.LOW)
            # For the first element, just leave things LOW
            # Assumes the laser is off prior to the start of the sequence
            if (ind == 0) and (val == 0):
                processed_train.append((dur, Digital.LOW))
                continue
            if dur < 75:
                raise ValueError(
                    "Feedthrough lasers do not support pulses shorter than" " 100 ns."
                )
            processed_train.append((20, Digital.HIGH))
            processed_train.append((dur - 20, Digital.LOW))
        # print(processed_train)
        pulser_laser_mod = pulser_wiring["do_{}_am".format(laser_name)]
        seq.setDigital(pulser_laser_mod, processed_train)
    else:
        if mod_type is ModTypes.DIGITAL:
            processed_train = train.copy()
            pulser_laser_mod = pulser_wiring["do_{}_dm".format(laser_name)]
            seq.setDigital(pulser_laser_mod, processed_train)

        # Analog, convert LOW / HIGH to 0.0 / analog voltage
        # currently can't handle multiple powers of the AM within the same sequence
        # Possibly, we could pass laser_power as a list, and then build the sequences
        # for each power (element) in the list.
        elif mod_type is ModTypes.ANALOG:
            high_count = 0
            for el in train:
                dur = el[0]
                val = el[1]
                if type(laser_power) == list:
                    if val == 0:
                        power_dict = {Digital.LOW: 0.0}
                    else:
                        power_dict = {Digital.HIGH: laser_power[high_count]}
                        if val == Digital.HIGH:
                            high_count += 1
                # If a list wasn't passed, just use the single value for laser_power
                elif type(laser_power) != list:
                    power_dict = {Digital.LOW: 0.0, Digital.HIGH: laser_power}
                processed_train.append((dur, power_dict[val]))
            pulser_laser_mod = pulser_wiring["ao_{}_am".format(laser_name)]
            # print(processed_train)
            seq.setAnalog(pulser_laser_mod, processed_train)

    # feedthrough = config["Optics"][laser_name]["feedthrough"]
    # feedthrough = eval(feedthrough)
    # #    feedthrough = False

    # # LOW = 0
    # # HIGH = 1

    # processed_train = []

    # if mod_type is ModTypes.DIGITAL:
    #     # Digital, feedthrough, bookend each pulse with 100 ns clock pulses
    #     # Assumes we always leave the laser on (or off) for at least 100 ns
    #     if feedthrough:
    #         # Collapse the sequence so that no two adjacent elements have the
    #         # same value
    #         collapsed_train = []
    #         ind = 0
    #         len_train = len(train)
    #         while ind < len_train:
    #             el = train[ind]
    #             dur = el[0]
    #             val = el[1]
    #             next_ind = ind + 1
    #             while next_ind < len_train:
    #                 next_el = train[next_ind]
    #                 next_dur = next_el[0]
    #                 next_val = next_el[1]
    #                 # If the next element shares the same value as the current
    #                 # one, combine them
    #                 if next_val == val:
    #                     dur += next_dur
    #                     next_ind += 1
    #                 else:
    #                     break
    #             # Append the current pulse and start back
    #             # where we left off
    #             collapsed_train.append((dur, val))
    #             ind = next_ind
    #         # Check if this is just supposed to be always on
    #         if (len(collapsed_train) == 1) and (collapsed_train[0][1] == Digital.HIGH):
    #             if pulse_streamer is not None:
    #                 pulse_streamer.client[laser_name].laser_on()
    #             return
    #         # Set up the bookends
    #         for ind in range(len(collapsed_train)):
    #             el = collapsed_train[ind]
    #             dur = el[0]
    #             val = el[1]
    #             # For the first element, just leave things LOW
    #             # Assumes the laser is off prior to the start of the sequence
    #             if (ind == 0) and (val is Digital.LOW):
    #                 processed_train.append((dur, Digital.LOW))
    #                 continue
    #             if dur < 75:
    #                 raise ValueError(
    #                     "Feedthrough lasers do not support pulses shorter than"
    #                     " 100 ns."
    #                 )
    #             processed_train.append((20, Digital.HIGH))
    #             processed_train.append((dur - 20, Digital.LOW))
    #     # Digital, no feedthrough, do nothing
    #     else:
    #         processed_train = train.copy()
    #     pulser_laser_mod = pulser_wiring["do_{}_dm".format(laser_name)]
    #     seq.setDigital(pulser_laser_mod, processed_train)

    # # Analog, convert LOW / HIGH to 0.0 / analog voltage
    # # currently can't handle multiple powers of the AM within the same sequence
    # # Possibly, we could pass laser_power as a list, and then build the sequences
    # # for each power (element) in the list.
    # elif mod_type is ModTypes.ANALOG:
    #     high_count = 0
    #     for el in train:
    #         dur = el[0]
    #         val = el[1]
    #         if type(laser_power) == list:
    #             if val == 0:
    #                 power_dict = {Digital.LOW: 0.0}
    #             else:
    #                 power_dict = {Digital.HIGH: laser_power[high_count]}
    #                 if val == Digital.HIGH:
    #                     high_count += 1
    #         # If a list wasn't passed, just use the single value for laser_power
    #         elif type(laser_power) != list:
    #             power_dict = {Digital.LOW: 0.0, Digital.HIGH: laser_power}
    #         processed_train.append((dur, power_dict[val]))

    #     pulser_laser_mod = pulser_wiring["ao_{}_am".format(laser_name)]
    #     # print(processed_train)
    #     seq.setAnalog(pulser_laser_mod, processed_train)


def set_delays_to_zero(config):
    """Pass this a config dictionary and it'll set all the delays to zero.
    Useful for testing sequences without having to worry about delays.
    """
    for key in config:
        # Check if any entries are delays and set them to 0
        if key.endswith("delay"):
            config[key] = 0
            return
        # Check if we're at a sublevel - if so, recursively set its delay to 0
        val = config[key]
        if type(val) is dict:
            set_delays_to_zero(val)


def set_delays_to_sixteen(config):
    """Pass this a config dictionary and it'll set all the delays to 16ns,
    which is the minimum wait() time for the OPX. Useful for testing
    sequences without having to worry about delays.
    """
    for key in config:
        # Check if any entries are delays and set them to 0
        if key.endswith("delay"):
            config[key] = 16
            return
        # Check if we're at a sublevel - if so, recursively set its delay to 0
        val = config[key]
        if type(val) is dict:
            set_delays_to_sixteen(val)


def seq_train_length_check(train):
    """Print out the length of a the sequence train for a specific channel.
    Useful for debugging sequences
    """
    total = 0
    for el in train:
        total += el[0]
    print(total)


def encode_seq_args(seq_args):
    # Recast np ints to Python ints so json knows what to do
    for ind in range(len(seq_args)):
        el = seq_args[ind]
        if type(el) is np.int32:
            seq_args[ind] = int(el)
    return json.dumps(seq_args)


def decode_seq_args(seq_args_string):
    if seq_args_string == "":
        return []
    else:
        return json.loads(seq_args_string)


def get_pulse_streamer_wiring(cxn):
    config = get_config_dict(cxn)
    pulse_streamer_wiring = config["Wiring"]["PulseGen"]
    return pulse_streamer_wiring


def get_tagger_wiring(cxn):
    cxn.registry.cd(["", "Config", "Wiring", "Tagger"])
    _, keys = cxn.registry.dir()
    if keys == []:
        return {}
    p = cxn.registry.packet()
    for key in keys:
        p.get(key, key=key)  # Return as a dictionary
    wiring = p.send()
    tagger_wiring = {}
    for key in keys:
        tagger_wiring[key] = wiring[key]
    return tagger_wiring


# endregion
# region Math functions


def get_pi_pulse_dur(rabi_period):
    return round(rabi_period / 2)


def get_pi_on_2_pulse_dur(rabi_period):
    return round(rabi_period / 4)


def iq_comps(phase, amp):
    """Given the phase and amplitude of the IQ vector, calculate the I (real) and
    Q (imaginary) components
    """
    if type(phase) is list:
        ret_vals = []
        for val in phase:
            ret_vals.append(np.round(amp * np.exp((0 + 1j) * val), 5))
        return (np.real(ret_vals).tolist(), np.imag(ret_vals).tolist())
    else:
        ret_val = np.round(amp * np.exp((0 + 1j) * phase), 5)
        return (np.real(ret_val), np.imag(ret_val))


def lorentzian(x, x0, A, L, offset):
    """Calculates the value of a lorentzian for the given input and parameters

    Params:
        x: float
            Input value
        params: tuple
            The parameters that define the lorentzian
            0: x0, mean postiion in x
            1: A, amplitude of curve
            2: L, related to width of curve
            3: offset, constant y value offset
    """

    x_center = x - x0
    return offset + A * 0.5 * L / (x_center**2 + (0.5 * L) ** 2)


def exp_decay(x, amp, decay, offset):
    return offset + amp * np.exp(-x / decay)


def linear(x, slope, y_offset):
    return slope * x + y_offset


def quadratic(x, a, b, c, x_offset):
    x_ = x - x_offset
    return a * (x_) ** 2 + b * x_ + c


def exp_stretch_decay(x, amp, decay, offset, B):
    return offset + amp * np.exp(-((x / decay) ** B))


def exp_t2(x, amp, decay, offset):
    return exp_stretch_decay(x, amp, decay, offset, 3)


def gaussian(x, *params):
    """Calculates the value of a gaussian for the given input and parameters

    Params:
        x: float
            Input value
        params: tuple
            The parameters that define the Gaussian
            0: coefficient that defines the peak height
            1: mean, defines the center of the Gaussian
            2: standard deviation, defines the width of the Gaussian
            3: constant y value to account for background
    """

    coeff, mean, stdev, offset = params
    var = stdev**2  # variance
    centDist = x - mean  # distance from the center
    return offset + coeff**2 * np.exp(-(centDist**2) / (2 * var))


def sinexp(t, offset, amp, freq, decay):
    two_pi = 2 * np.pi
    half_pi = np.pi / 2
    return offset + (amp * np.sin((two_pi * freq * t) + half_pi)) * exp(
        -(decay**2) * t
    )


def cosexp(t, offset, amp, freq, decay):
    two_pi = 2 * np.pi
    return offset + (np.exp(-t / abs(decay)) * abs(amp) * np.cos((two_pi * freq * t)))


def inverted_cosexp(t, offset, freq, decay):
    two_pi = 2 * np.pi
    amp = offset - 1
    return offset - (np.exp(-t / abs(decay)) * abs(amp) * np.cos((two_pi * freq * t)))


def cosexp_1_at_0(t, offset, freq, decay):
    two_pi = 2 * np.pi
    amp = 1 - offset
    return offset + (np.exp(-t / abs(decay)) * abs(amp) * np.cos((two_pi * freq * t)))


def sin_1_at_0_phase(t, amp, offset, freq, phase):
    two_pi = 2 * np.pi
    # amp = 1 - offset
    return offset + (abs(amp) * np.sin((freq * t - np.pi / 2 + phase)))


def sin_phase(t, amp, offset, freq, phase):
    return offset + (abs(amp) * np.sin((freq * t + phase)))


def cosine_sum(t, offset, decay, amp_1, freq_1, amp_2, freq_2, amp_3, freq_3):
    two_pi = 2 * np.pi

    return offset + np.exp(-t / abs(decay)) * (
        amp_1 * np.cos(two_pi * freq_1 * t)
        + amp_2 * np.cos(two_pi * freq_2 * t)
        + amp_3 * np.cos(two_pi * freq_3 * t)
    )


def cosine_double_sum(t, offset, decay, amp_1, freq_1, amp_2, freq_2):
    two_pi = 2 * np.pi

    return offset + np.exp(-t / abs(decay)) * (
        amp_1 * np.cos(two_pi * freq_1 * t)
        + amp_2 * np.cos(two_pi * freq_2 * t)
        # + amp_3 * np.cos(two_pi * freq_3 * t)
    )


def cosine_one(t, offset, decay, amp_1, freq_1):
    two_pi = 2 * np.pi

    return offset + np.exp(-t / abs(decay)) * (amp_1 * np.cos(two_pi * freq_1 * t))


def t2_func(t, amplitude, offset, t2):
    n = 3
    return amplitude * np.exp(-((t / t2) ** n)) + offset


def poiss_snr(sig, ref):
    """Take a list of signal and reference counts, and take their average,
    then calculate a snr.
    inputs:
        sig_count = list
        ref_counts = list
    outputs:
        snr = list
    """

    # Assume Poisson statistics on each count value
    # sig_noise = np.sqrt(sig)
    # ref_noise = np.sqrt(ref)
    # snr = (ref - sig) / np.sqrt(sig_noise**2 + ref_noise**2)
    # snr_per_readout = (snr / np.sqrt(num_reps))

    ref_count = np.array(ref)
    sig_count = np.array(sig)
    num_reps, num_points = ref_count.shape

    sig_count_avg = np.average(sig_count)
    ref_count_avg = np.average(ref_count)
    dif = sig_count_avg - ref_count_avg
    sig_noise = np.sqrt(sig_count_avg)
    ref_noise = np.sqrt(ref_count_avg)
    noise = np.sqrt(sig_noise**2 + ref_noise**2)
    snr = dif / noise

    N = sig_count_avg - ref_count_avg
    d = np.sqrt(sig_noise**2 + ref_noise**2)
    D = np.sqrt(sig_count_avg + ref_count_avg)
    d_d = 0.5 * d / D

    snr_unc = snr * np.sqrt((N / d) ** 2 + (d_d / D) ** 2)

    return snr, snr_unc


def get_scan_vals(center, scan_range, num_steps, dtype=float):
    """
    Returns a linspace for a scan centered about specified point
    """

    half_scan_range = scan_range / 2
    low = center - half_scan_range
    high = center + half_scan_range
    scan_vals = np.linspace(low, high, num_steps, dtype=dtype)
    # Deduplicate - may be necessary for ints and low scan ranges
    scan_vals = np.unique(scan_vals)
    return scan_vals


def bose(energy, temp):
    """Calculate Bose Einstein occupation number

    Parameters
    ----------
    energy : numeric
        Mode energy in meV
    temp : numeric
        Temperature in K

    Returns
    -------
    numeric
        Occupation number
    """
    # For very low temps we can get divide by zero and overflow warnings.
    # Fortunately, numpy is smart enough to know what we mean when this
    # happens, so let's let numpy figure it out and suppress the warnings.
    old_settings = np.seterr(divide="ignore", over="ignore")
    # print(energy / (Boltzmann * temp))
    val = 1 / (np.exp(energy / (Boltzmann * temp)) - 1)
    # Return error handling to default state for other functions
    np.seterr(**old_settings)
    return val


def process_counts(
    sig_counts, ref_counts, num_reps, readout, norm_style=NormStyle.SINGLE_VALUED
):
    """Extract the normalized average signal at each data point.
    Since we sometimes don't do many runs (<10), we often will have an
    insufficient sample size to run stats on for norm_avg_sig calculation.
    We assume Poisson statistics instead.

    Parameters
    ----------
    sig_counts : 2D array
        Signal counts from the experiment
    ref_counts : 2D array
        Reference counts from the experiment
    num_reps : int
        Number of experiment repetitions summed over for each point in sig or ref counts
    readout : numeric
        Readout duration in ns
    norm_style : NormStyle(enum), optional
        By default NormStyle.SINGLE_VALUED

    Returns
    -------
    1D array
        Signal count rate averaged across runs
    1D array
        Reference count rate averaged across runs
    1D array
        Normalized average signal
    1D array
        Standard error of the normalized average signal
    """

    ref_counts = np.array(ref_counts)
    sig_counts = np.array(sig_counts)
    num_runs, num_points = ref_counts.shape
    readout_sec = readout * 1e-9

    # Find the averages across runs
    sig_counts_avg = np.average(sig_counts, axis=0)
    single_ref_avg = np.average(ref_counts)
    ref_counts_avg = np.average(ref_counts, axis=0)

    sig_counts_ste = np.sqrt(sig_counts_avg) / np.sqrt(num_runs)
    single_ref_ste = np.sqrt(single_ref_avg) / np.sqrt(num_runs * num_points)
    ref_counts_ste = np.sqrt(ref_counts_avg) / np.sqrt(num_runs)

    if norm_style == NormStyle.SINGLE_VALUED:
        norm_avg_sig = sig_counts_avg / single_ref_avg
        norm_avg_sig_ste = norm_avg_sig * np.sqrt(
            (sig_counts_ste / sig_counts_avg) ** 2
            + (single_ref_ste / single_ref_avg) ** 2
        )
    elif norm_style == NormStyle.POINT_TO_POINT:
        norm_avg_sig = sig_counts_avg / ref_counts_avg
        norm_avg_sig_ste = norm_avg_sig * np.sqrt(
            (sig_counts_ste / sig_counts_avg) ** 2
            + (ref_counts_ste / ref_counts_avg) ** 2
        )

    sig_counts_avg_kcps = (sig_counts_avg / (num_reps * 1000)) / readout_sec
    ref_counts_avg_kcps = (ref_counts_avg / (num_reps * 1000)) / readout_sec

    return (
        sig_counts_avg_kcps,
        ref_counts_avg_kcps,
        norm_avg_sig,
        norm_avg_sig_ste,
    )


# endregion
# region LabRAD registry utils
# Core registry functions in Common


def get_config_dict(cxn=None):
    """Get the whole config from the registry as a dictionary"""
    if cxn is None:
        with labrad.connect() as cxn:
            return get_config_dict_sub(cxn)
    else:
        return get_config_dict_sub(cxn)


def get_config_dict_sub(cxn):
    config_dict = {}
    populate_config_dict(cxn, ["", "Config"], config_dict)
    return config_dict


def populate_config_dict(cxn, reg_path, dict_to_populate):
    """Populate the config dictionary recursively"""

    # Sub-folders
    cxn.registry.cd(reg_path)
    sub_folders, keys = cxn.registry.dir()
    for el in sub_folders:
        sub_dict = {}
        sub_path = reg_path + [el]
        populate_config_dict(cxn, sub_path, sub_dict)
        dict_to_populate[el] = sub_dict

    # Keys
    if len(keys) == 1:
        cxn.registry.cd(reg_path)
        p = cxn.registry.packet()
        key = keys[0]
        p.get(key)
        val = p.send()["get"]
        if type(val) == np.ndarray:
            val = val.tolist()
        dict_to_populate[key] = val

    elif len(keys) > 1:
        cxn.registry.cd(reg_path)
        p = cxn.registry.packet()
        for key in keys:
            p.get(key)
        vals = p.send()["get"]

        for ind in range(len(keys)):
            key = keys[ind]
            val = vals[ind]
            if type(val) == np.ndarray:
                val = val.tolist()
            dict_to_populate[key] = val


def get_apd_indices(cxn):
    "Get a list of the APD indices in use from the registry"
    return common.get_registry_entry(cxn, "apd_indices", ["Config"])


def get_apd_gate_channel(cxn):
    return common.get_registry_entry(cxn, "di_apd_gate", ["Config", "Wiring", "Tagger"])


# endregion
# region Server getters
"""Each getter looks up the requested server from the registry and
returns a usable reference to the requested server (i.e. cxn.<server>)
"""


def get_server_pulse_gen(cxn):
    """Get the pulse gen server for this setup, e.g. opx or swabian"""
    return common.get_server(cxn, "pulse_gen")


def get_server_charge_readout_laser(cxn):
    """Get the laser for charge readout"""
    return common.get_server(cxn, "charge_readout_laser")


def get_server_arb_wave_gen(cxn):
    """Get the arbitrary waveform generator server for this setup, e.g. opx or keysight"""
    return common.get_server(cxn, "arb_wave_gen")


def get_server_counter(cxn):
    """Get the photon counter server for this setup, e.g. opx or swabian"""
    return common.get_server(cxn, "counter")


def get_server_tagger(cxn):
    """Get the photon time tagger server for this setup, e.g. opx or swabian"""
    return common.get_server(cxn, "tagger")


def get_server_temp_controller(cxn):
    return common.get_server(cxn, "temp_controller")


def get_server_temp_monitor(cxn):
    return common.get_server(cxn, "temp_monitor")


def get_server_power_supply(cxn):
    return common.get_server(cxn, "power_supply")


def get_server_sig_gen(cxn, state):
    """Get the signal generator that controls transitions to the specified NV state"""
    return common.get_server(cxn, f"sig_gen_{state.name}")


def get_server_magnet_rotation(cxn):
    """Get the signal generator that controls magnet rotation angle"""
    return common.get_server(cxn, "magnet_rotation")

def get_server_laser_msquared(cxn):
    """Get the pulse gen server for this setup, e.g. opx or swabian"""
    return common.get_server(cxn, "Msquare")

# endregion
# region File and data handling utils


def get_raw_data(
    file_name,
    path_from_nvdata=None,
    nvdata_dir=None,
):
    """Returns a dictionary containing the json object from the specified
    raw data file. If path_from_nvdata is not specified, we assume we're
    looking for an autogenerated experiment data file. In this case we'll
    use glob (a pattern matching module for pathnames) to efficiently find
    the file based on the known structure of the directories rooted from
    nvdata_dir (ie nvdata_dir / pc_folder / routine / year_month / file.txt)
    """
    file_path = get_raw_data_path(file_name, path_from_nvdata, nvdata_dir)
    with file_path.open() as f:
        res = json.load(f)
        return res


def get_raw_data_path(
    file_name,
    path_from_nvdata=None,
    nvdata_dir=None,
):
    """Same as get_raw_data, but just returns the path to the file"""
    if nvdata_dir is None:
        nvdata_dir = common.get_nvdata_path()
    if path_from_nvdata is None:
        path_from_nvdata = search_index.get_data_path_from_nvdata(file_name)
    data_dir = nvdata_dir / path_from_nvdata
    file_name_ext = "{}.txt".format(file_name)
    file_path = data_dir / file_name_ext
    return file_path


def get_branch_name():
    """Return the name of the active branch of dioptric (fka kolkowitz-nv-experiment-v1.0)"""
    # home_to_repo = PurePath("Documents/GitHub/kolkowitz-nv-experiment-v1.0")
    home_to_repo = PurePath("C:/Users/choyl/ChoyDioptric")
    repo_path = PurePath(Path.home()) / home_to_repo
    repo = Repo(repo_path)
    return repo.active_branch.name


def get_time_stamp():
    """Get a formatted timestamp for file names and metadata.

    Returns:
        string: <year>_<month>_<day>-<hour>_<minute>_<second>
    """

    timestamp = str(datetime.now())
    timestamp = timestamp.split(".")[0]  # Keep up to seconds
    timestamp = timestamp.replace(":", "_")  # Replace colon with dash
    timestamp = timestamp.replace("-", "_")  # Replace dash with underscore
    timestamp = timestamp.replace(" ", "-")  # Replace space with dash
    return timestamp


def get_time_stamp_from_file_name(file_name):
    """Get the formatted timestamp from a file name

    Returns:
        string: <year>_<month>_<day>-<hour>_<minute>_<second>
    """

    file_name_split = file_name.split("-")
    time_stamp_parts = file_name_split[0:2]
    timestamp = "-".join(time_stamp_parts)
    return timestamp


def get_files_in_folder(folderDir, filetype=None):
    """
    folderDir: str
        full file path, use previous function get_folder_dir
    filetype: str
        must be a 3-letter file extension, do NOT include the period. ex: 'txt'
    """
    # print(folderDir)
    file_list_temp = os.listdir(folderDir)
    if filetype:
        file_list = []
        for file in file_list_temp:
            if file[-3:] == filetype:
                file_list.append(file)
    else:
        file_list = file_list_temp

    return file_list


def get_file_path(source_file, time_stamp, name, subfolder=None):
    """Get the file path to save to. This will be in a subdirectory of nvdata.

    Params:
        source_file: string
            Source __file__ of the caller which will be parsed to get the
            name of the subdirectory we will write to
        time_stamp: string
            Formatted timestamp to include in the file name
        name: string
            The full file name consists of <timestamp>_<name>.<ext>
            Ext is supplied by the save functions
        subfolder: string
            Subfolder to save to under file name
    """

    nvdata_dir = common.get_nvdata_path()
    pc_name = socket.gethostname()
    branch_name = get_branch_name()
    source_name = Path(source_file).stem
    date_folder = "_".join(time_stamp.split("_")[0:2])  # yyyy_mm

    folder_dir = (
        nvdata_dir
        / f"pc_{pc_name}"
        / f"branch_{branch_name}"
        / source_name
        / date_folder
    )

    if subfolder is not None:
        folder_dir = folder_dir / subfolder

    # Make the required directories if it doesn't exist already
    folder_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"{time_stamp}-{name}"

    return folder_dir / file_name


def utc_from_file_name(file_name, time_zone="CST"):
    # First 19 characters are human-readable timestamp
    date_time_str = file_name[0:19]
    # Assume timezone is CST
    date_time_str += f"-{time_zone}"
    date_time = datetime.strptime(date_time_str, r"%Y_%m_%d-%H_%M_%S-%Z")
    timestamp = date_time.timestamp()
    return timestamp


def get_nv_sig_units_no_cxn():
    with labrad.connect() as cxn:
        nv_sig_units = get_nv_sig_units(cxn)
    return nv_sig_units


def get_nv_sig_units(cxn):
    try:
        nv_sig_units = common.get_registry_entry(cxn, "nv_sig_units", "Config")
    except Exception:
        nv_sig_units = ""
    return nv_sig_units


def save_figure(fig, file_path):
    """Save a matplotlib figure as a svg.

    Params:
        fig: matplotlib.figure.Figure
            The figure to save
        file_path: string
            The file path to save to including the file name, excluding the
            extension
    """

    fig.savefig(str(file_path.with_suffix(".svg")), dpi=300)


def save_raw_data(rawData, filePath):
    """Save raw data in the form of a dictionary to a text file. New lines
    will be printed between entries in the dictionary.

    Params:
        rawData: dict
            The raw data as a dictionary - will be saved via JSON
        filePath: string
            The file path to save to including the file name, excluding the
            extension
    """

    # Just to be safe, work with a copy of the raw data rather than the
    # raw data itself
    rawData = copy.deepcopy(rawData)

    file_path_ext = filePath.with_suffix(".txt")

    # Add in a few things that should always be saved here. In particular,
    # sharedparameters so we have as snapshot of the configuration and
    # nv_sig_units. If these have already been defined in the routine,
    # then they'll just be overwritten.
    try:
        rawData["config"] = get_config_dict()  # Include a snapshot of the config
    except Exception as e:
        print(e)

    # Casting for JSON compatibility
    nv_sig = rawData["nv_sig"]
    try:
        for key in nv_sig:
            if type(nv_sig[key]) == np.ndarray:
                nv_sig[key] = nv_sig[key].tolist()
            elif isinstance(nv_sig[key], Enum):
                nv_sig[key] = nv_sig[key].name
    except Exception:
        print(" ")

    with open(file_path_ext, "w") as file:
        json.dump(rawData, file, indent=2)

    if file_path_ext.match(search_index.search_index_glob):
        search_index.add_to_search_index(file_path_ext)


# endregion
# region Email utils


def send_exception_email(
    email_from=None,
    email_to=None,
):
    default_email = common.get_default_email()
    if email_from is None:
        email_from = default_email
    if email_to is None:
        email_to = default_email
    # format_exc extracts the stack and error message from
    # the exception currently being handled.
    now = time.localtime()
    date = time.strftime("%A, %B %d, %Y", now)
    timex = time.strftime("%I:%M:%S %p", now)
    exc_info = traceback.format_exc()
    content = f"An unhandled exception occurred on {date} at {timex}.\n{exc_info}"
    send_email(content, email_from=email_from, email_to=email_to)


def send_email(
    content,
    email_from=None, 
    email_to=None
):
    default_email = common.get_default_email()
    if email_from is None:
        email_from = default_email
    if email_to is None:
        email_to = default_email
    pc_name = socket.gethostname()
    msg = MIMEText(content)
    msg["Subject"] = f"Alert from {pc_name}"
    msg["From"] = email_from
    msg["To"] = email_to

    pw = keyring.get_password("system", email_from)

    server = smtplib.SMTP("smtp.gmail.com", 587)  # port 465 or 587
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(email_from, pw)
    server.sendmail(email_from, email_to, msg.as_string())
    server.close()


# endregion
# region Miscellaneous (probably consider deprecated)


def get_dd_model_coeff_dict():
    # fmt: off
    dd_model_coeff_dict = {
        "1": [6, -8, 2],
        "2": [10, -8, -8, 8, -2],
        "4": [18, -8, -24, 8, 16, -8, -8, 8, -2],
        "8": [34, -8, -56, 8, 48, -8, -40, 8, 32, -8, -24, 8, 16, -8, -8, 8, -2],
    }
    # fmt: on

    return dd_model_coeff_dict


def single_conversion(single_func, freq, *args):
    if type(freq) in [list, np.ndarray]:
        single_func_lambda = lambda freq: single_func(freq, *args)
        # with ProcessingPool() as p:
        #     line = p.map(single_func_lambda, freq)
        line = np.array([single_func_lambda(f) for f in freq])
        return line
    else:
        return single_func(freq, *args)


# endregion
# region Rounding
"""
Various rounding tools, including several for presenting data with errors (round_for_print).
Relies on the decimals package for accurate arithmetic w/o binary rounding errors.
"""


def round_sig_figs(val, num_sig_figs):
    """Round a value to the passed number of sig figs

    Parameters
    ----------
    val : numeric
        Value to round
    num_sig_figs : int
        Number of sig figs to round to

    Returns
    -------
    numeric
        Rounded value
    """

    # All the work is done here
    func = lambda val, num_sig_figs: round(
        val, -int(math.floor(math.log10(abs(val))) - num_sig_figs + 1)
    )

    # Check for list/array/single value
    if type(val) is list:
        return [func(el, num_sig_figs) for el in val]
    elif type(val) is np.ndarray:
        rounded_val_list = [func(el, num_sig_figs) for el in val.tolist()]
        return np.array(rounded_val_list)
    else:
        return func(val, num_sig_figs)


def round_for_print_sci(val, err):
    """Round a value and associated error to the appropriate level given the
    magnitude of the error. The error will be rounded to 1 or 2 sig figs depending
    on whether the first sig fig is >1 or =1 respectively. Returned in a form
    suitable for scientific notation

    Parameters
    ----------
    val : numeric
        Value to round
    err : numeric
        Associated error

    Returns
    -------
    Decimal
        Rounded value as a string
    Decimal
        Rounded error as a string
    int
        Order of magnitude
    """

    val = Decimal(val)
    err = Decimal(err)

    err_mag = math.floor(math.log10(err))
    sci_err = err / (Decimal(10) ** err_mag)
    first_err_digit = int(str(sci_err)[0])
    if first_err_digit == 1:
        err_sig_figs = 2
    else:
        err_sig_figs = 1

    power_of_10 = math.floor(math.log10(abs(val)))
    mag = Decimal(10) ** power_of_10
    rounded_err = round_sig_figs(err / mag, err_sig_figs)
    rounded_val = round(val / mag, (power_of_10 - err_mag) + err_sig_figs - 1)

    # Check for corner case where the value is e.g. 0.999 and rounds up to another decimal place
    if rounded_val >= 10:
        power_of_10 += 1
        # Just shift the decimal over and recast to Decimal to ensure proper rounding
        rounded_err = Decimal(_shift_decimal_left(str(rounded_err)))
        rounded_val = Decimal(_shift_decimal_left(str(rounded_val)))

    return [rounded_val, rounded_err, power_of_10]


def round_for_print_sci_latex(val, err):
    """Round a value and associated error to the appropriate level given the
    magnitude of the error. The error will be rounded to 1 or 2 sig figs depending
    on whether the first sig fig is >1 or =1 respectively. Returned as a string
    to be put directly into LaTeX - the printed result will be in scientific notation

    Parameters
    ----------
    val : numeric
        Value to round
    err : numeric
        Associated error

    Returns
    -------
    str
        Rounded value including error and order of magnitude to be put directly into LaTeX
    """

    rounded_val, rounded_err, power_of_10 = round_for_print_sci(val, err)
    err_str = _strip_err(rounded_err)
    return r"\num{{{}({})e{}}}".format(rounded_val, err_str, power_of_10)


def round_for_print(val, err):
    """Round a value and associated error to the appropriate level given the
    magnitude of the error. The error will be rounded to 1 or 2 sig figs depending
    on whether the first sig fig is >1 or =1 respectively. Returned as a string
    to be printed directly in standard (not scientific) notation. As such, it is
    assumed that err < 1, otherwise the number of sig figs will be unclear

    Parameters
    ----------
    val : numeric
        Value to round
    err : numeric
        Associated error

    Returns
    -------
    str
        Rounded value including error to be printed directly
    """

    # If err > 10, this presentation style becomes unclear
    if err > 10:
        return None

    # Start from the scientific presentation
    rounded_val, rounded_err, power_of_10 = round_for_print_sci(val, err)

    # Get the representation of the actual value, where min_digits
    # ensures the last digit lines up with the error
    mag = Decimal(10) ** power_of_10
    str_rounded_err = str(rounded_err)
    val_str = np.format_float_positional(
        rounded_val * mag, min_digits=len(str_rounded_err) - 2 - power_of_10
    )

    # Trim possible trailing decimal point
    if val_str[-1] == ".":
        val_str = val_str[:-1]

    # Get the representation of the error, which is alway just the trailing non-zero digits
    err_str = _strip_err(rounded_err)

    return f"{val_str}({err_str})"


def _shift_decimal_left(val_str):
    """Finds the . character in a string and moves it one place to the left"""

    decimal_pos = val_str.find(".")
    left_char = val_str[decimal_pos - 1]
    val_str = val_str.replace(f"{left_char}.", f".{left_char}")
    return val_str


def _strip_err(err):
    """Get the representation of the error, which is alway just the trailing non-zero digits

    Parameters
    ----------
    err : str
        Error to process

    Returns
    -------
    str
        Trailing non-zero digits of err
    """

    stripped_err = ""
    trailing = False
    for char in str(err):
        if char == ".":
            continue
        elif char != "0":
            trailing = True
        if trailing:
            stripped_err += char
    return stripped_err


# endregion
# region Safe Stop
"""Use this to safely stop experiments without risking data loss or weird state.
Works by reassigning CTRL + C to set a global variable rather than raise a
KeyboardInterrupt exception. That way we can check on the global variable
whenever we like and stop the experiment appropriately. It's up to you (the
routine author) to place this in your routine appropriately.
"""


def init_safe_stop():
    """Call this at the beginning of a loop or other section which you may
    want to interrupt
    """
    global SAFESTOPFLAG
    # Tell the user safe stop has started if it was stopped or just not started
    try:
        if SAFESTOPFLAG:
            print("\nPress CTRL + C to stop...\n")
    except Exception as exc:
        print("\nPress CTRL + C to stop...\n")
    SAFESTOPFLAG = False
    signal.signal(signal.SIGINT, safe_stop_handler)
    return


def safe_stop_handler(sig, frame):
    """This should never need to be called directly"""
    global SAFESTOPFLAG
    SAFESTOPFLAG = True


def safe_stop():
    """Call this to check whether the user asked us to stop"""
    global SAFESTOPFLAG
    time.sleep(0.1)  # Pause execution to allow safe_stop_handler to run
    return SAFESTOPFLAG


def reset_safe_stop():
    """Reset the Safe Stop flag, but don't remove the handler in case we
    want to reuse it.
    """
    global SAFESTOPFLAG
    SAFESTOPFLAG = False


def poll_safe_stop():
    """Blocking version of safe stop"""
    init_safe_stop()
    while not safe_stop():
        time.sleep(0.1)


# endregion
# region Reset hardware


def reset_cfm(cxn=None):
    """Reset our cfm so that it's ready to go for a new experiment. Avoids
    unnecessarily resetting components that may suffer hysteresis (ie the
    components that control xyz since these need to be reset in any
    routine where they matter anyway).
    """
    if cxn is None:
        with labrad.connect() as cxn:
            reset_cfm_with_cxn(cxn)
    else:
        reset_cfm_with_cxn(cxn)


def reset_cfm_with_cxn(cxn):
    cxn_server_names = cxn.servers
    for name in cxn_server_names:
        server = cxn[name]
        # Check for servers that ask not to be reset automatically
        if hasattr(server, "reset_cfm_opt_out"):
            continue
        if hasattr(server, "reset"):
            server.reset()


# endregion


# Testing
if __name__ == "__main__":
    print(round_for_print_sci(0.997, 0.0940))
