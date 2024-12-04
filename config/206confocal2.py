# -*- coding: utf-8 -*-
"""
Default config file for laptops, home PCs, etc 

Created August 8th, 2023

@author: mccambria
"""

from utils.constants import ModMode, ControlMode, CountFormat
from utils.constants import CollectionMode, LaserKey, LaserPosMode
from pathlib import Path
import numpy as np

from pathlib import Path

home = Path.home()

green_laser = "laser_LGLO_532"

config = {
    "shared_email": "choylab206@outlook.com",
    "windows_nvdata_path": Path("D:/Choy_Lab/sivdata"),
    "windows_repo_path": Path("C:/Users/choyl/ChoyDioptric"),

    # Units for NV signature
    "apd_indices": [0],
    "nv_sig_units": {
        "coords": "um",
        "expected_count_rate": "kcps",
        "durations": "ns",
        "magnet_angle": "deg",
        "resonance": "GHz",
        "rabi": "ns",
        "uwave_power": "dBm",
    },
    "DeviceIDs": {
        "tagger_SWAB_20_ip": "192.168.1.8",           # Added 
        "tagger_SWAB_20_port": "41101",               # Added 
        "tagger_SWAB_20_serial": "174000JFF",         # Added 
        "pos_xyz_Newport_25XA_ip": "192.168.1.90",    # Added 
        "laser_msquared_ip": "192.168.1.222",        # Added 
        "laser_msquared_port": "39900",              # Added 
        "pulse_gen_SWAB_82_ip": "192.168.1.100",
    },
    "Servers": {
        "counter": "tagger_SWAB_20", 
        "tagger": "tagger_SWAB_20",
        "pos_xy": "pos_xyz_Newport_25XA",             # Added 
        "pos_xyz": "pos_xyz_Newport_25XA",            # Added 
        "pos_z": "pos_xyz_Newport_25XA",              # Updated 
        "pulse_gen": "pulse_gen_SWAB_82", 
    },
    "Wiring": {
        "Daq": {
            "ao_galvo_x": "dev1/AO0",
            "ao_galvo_y": "dev1/AO1",
            "ao_objective_piezo": "dev1/AO2",
            "di_clock": "PFI12",
        },
        "PulseGen": {
            "do_laserglow_532_dm": 4,
            "do_sample_clock": 5,
        },
        "Tagger": {
            "di_apd_0": 5,    
            "di_apd_1": 6,    
            "di_apd_gate": 7, 
            "di_clock": 8     
        },
    }

}

