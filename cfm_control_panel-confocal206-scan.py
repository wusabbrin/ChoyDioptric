# -*- coding: utf-8 -*-
"""
Control panel with a few of the basics as a template

Created on December 17th, 2022

@author: mccambria
"""


### Imports

import time
import numpy as np
import labrad
import utils.tool_belt as tool_belt
import utils.positioning as positioning
import majorroutines.image_sample as image_sample
import majorroutines.optimize as optimize
import majorroutines.stationary_count as stationary_count
import majorroutines.pulsed_resonance as pulsed_resonance
import majorroutines.rabi as rabi
import majorroutines.siv_frequency_sweep as siv_frequency_sweep
import majorroutines.siv_broad_frequency_sweep as siv_broad_frequency_sweep


### Major Routines


def do_image_sample(nv_sig):

    scan_range = 100.0
    num_steps = 10

    # scan_range = 1.0
    # num_steps = 90

    # scan_range = 0.5
    # num_steps = 90

    # scan_range = 0.2
    # num_steps = 60

    # scan_range = 1.0
    # num_steps = 180

    image_sample.main(
        nv_sig,
        scan_range,
        scan_range,
        num_steps,
    )


def do_image_sample_zoom(nv_sig):
    # scan_range = 0.15
    # num_steps = 150
    scan_range = 1.0
    num_steps = 70
    image_sample.main(nv_sig, scan_range, scan_range, num_steps)


def do_optimize(nv_sig):

    optimize.main(nv_sig, set_to_opti_coords=False, save_data=True, plot_data=True)


def do_stationary_count(nv_sig, disable_opt=False):
    nv_sig["imaging_readout_dur"] *= 10
    run_time = 1 * 60 * 10**9  # ns
    stationary_count.main(nv_sig, run_time, disable_opt=disable_opt)
    
def do_siv_freq_sweep(cxn, nv_sig, freq_center=50, freq_range=30):

    num_steps = 200

    # num_reps = 2e4
    # num_runs = 16

    num_reps = 1
    num_runs = 2
    
    
    siv_frequency_sweep.main_with_cxn(
        cxn,
        nv_sig,
        freq_center,
        freq_range,
        num_steps,
        num_reps,
        num_runs,
    )
    
def do_siv_broad_freq_sweep(cxn, nv_sig, freq_center=737.0, freq_range=1.2):

    num_steps = 180

    # num_reps = 2e4
    # num_runs = 16

    num_reps = 1
    num_runs = 6
    
    
    siv_broad_frequency_sweep.main_with_cxn(
        cxn,
        nv_sig,
        freq_center,
        freq_range,
        num_steps,
        num_reps,
        num_runs,
    )

def do_pulsed_resonance(nv_sig, freq_center=2.87, freq_range=0.2):

    num_steps = 51

    # num_reps = 2e4
    # num_runs = 16

    num_reps = 1e2
    num_runs = 32

    uwave_power = 4
    uwave_pulse_dur = 100

    pulsed_resonance.main(
        nv_sig,
        freq_center,
        freq_range,
        num_steps,
        num_reps,
        num_runs,
        uwave_power,
        uwave_pulse_dur,
    )


def do_rabi(nv_sig, state, uwave_time_range=[0, 300]):

    num_steps = 51

    # num_reps = 2e4
    # num_runs = 16

    num_reps = 1e2
    num_runs = 16

    period = rabi.main(nv_sig, uwave_time_range, state, num_steps, num_reps, num_runs)
    nv_sig["rabi_{}".format(state.name)] = period




### Run the file


if __name__ == "__main__":

    ### Shared parameters

    green_laser = "laserglow_532"
    siv_resonant_laser = "Msquared"

    sample_name = "sandia1"
    z_coord = 5
    
  # 
    ref_coords = [0, 0, z_coord] 
    # ref_coords = [0.359, 0.924, z_coord]
    ref_coords = np.array(ref_coords)

    nv_sig = {
        "coords": ref_coords,
        "name": "{}-nvref".format(sample_name),
        "disable_opt": False,
        "disable_z_opt": True,
        "expected_count_rate": None,
        
        "imaging_laser": green_laser,
        # "imaging_laser": red_laser,
        # "imaging_laser": siv_resonant_laser,
        "imaging_laser_filter": "nd_0",
        "imaging_readout_dur":2e7,
        # 
        "collection_filter": None,
        "magnet_angle": None,
        "piezo_coords": [None, None],
    }
    # nv_sig = {
    #     "coords": [-0.01, 0.39, z_coord],
    #     "name": "{}-nv1_2023_08_01".format(sample_name),
    #     "disable_opt": False,
    #     "disable_z_opt": True,
    #     "expected_count_rate": None,
    #     #
    #     "imaging_laser": green_laser,
    #     "imaging_laser_filter": "nd_0",
    #     "imaging_readout_dur": 1e7,
    #     #
    #     "collection_filter": None,
    #     "magnet_angle": None,
    #     "piezo_coords": [None, None],
    # }

    ### Functions to run

    email_to = "wwu239@wisc.edu"
    try:

        # pass
    
        tool_belt.init_safe_stop()
    
        # Increasing x moves the image down, increasing y moves the image left
        # for x_coord in np.arange(1000,-1000,-75):
        #     # if tool_belt.safe_stop():
        #     #     break
        #     for y_coord in np.arange(500,-1000,-75):
        #         if tool_belt.safe_stop():
        #             break
        #         with labrad.connect() as cxn:
        #             cxn.pos_xyz_ATTO_piezos.write_xy(x_coord, y_coord)
        #             nv_sig["piezo_coords"] = [int(x_coord), int(y_coord)]
        #             print(x_coord, y_coord, time.time())
        #         do_image_sample(nv_sig)
            
        # y_coord=-700
        # for x_coord in np.arange(0,-2100,-60):
        #     if tool_belt.safe_stop():
        #         break
            
        #     with labrad.connect() as cxn:
        #         cxn.pos_xyz_ATTO_piezos.write_xy(x_coord, y_coord)
        #         nv_sig["piezo_coords"] = [int(x_coord), int(y_coord)]
        #         do_image_sample(nv_sig)
            
        
        with labrad.connect() as cxn:
            x_coord= 50
            y_coord= 50
            cxn.pos_xyz_Newport_25XA.write_xy(x_coord, y_coord)
            nv_sig["piezo_coords"] = [int(x_coord), int(y_coord)]
            
            # nv_sig["collection_filter"]="nd_1"
            do_image_sample(nv_sig)
            # do_image_sample_zoom(nv_sig)
            # do_optimize(nv_sig)
            # positioning.reset_drift()
            # do_stationary_count(nv_sig, disable_opt=True)
        
        
            # for z_coord in np.arange(1, 9, 2, dtype=int):
            #     nv_sig["coords"][2] = z_coord
            #     # x_coord=0
            #     # y_coord=0
            #     with labrad.connect() as cxn:
            #         cxn.pos_xyz_ATTO_piezos.write_xy(x_coord, y_coord)
            #         do_image_sample(nv_sig)
            # do_siv_freq_sweep(cxn, nv_sig)
            # do_siv_broad_freq_sweep(cxn, nv_sig)
# 
    # except Exception as exc:
    #     tool_belt.send_exception_email(email_to=email_to)
    #     raise exc 

    finally:

        # msg = "Experiment complete!"
        # tool_belt.send_email(msg, email_to=email_to)

        # Make sure everything is reset
        tool_belt.reset_cfm()
        tool_belt.reset_safe_stop()
