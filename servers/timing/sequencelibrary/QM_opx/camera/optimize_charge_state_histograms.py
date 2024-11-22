# -*- coding: utf-8 -*-
"""
Charge state readout after polarization/ionization, no spin manipulation

Created on October 13th, 2023

@author: mccambria
"""

import matplotlib.pyplot as plt
import numpy as np
from qm import QuantumMachinesManager, qua
from qm.simulate import SimulationConfig

import utils.common as common
from servers.timing.sequencelibrary.QM_opx import seq_utils
from servers.timing.sequencelibrary.QM_opx.camera import base_charge_state_histograms


def get_seq(
    pol_coords_list,
    pol_duration_list,
    pol_amp_list,
    ion_coords_list,
    step_vals,
    optimize_pol_or_readout,
    optimize_duration_or_amp,
    num_reps,
):
    if optimize_duration_or_amp:
        step_vals = [seq_utils.convert_ns_to_cc(el) for el in step_vals]

    with qua.program() as seq:
        if optimize_duration_or_amp:
            override_var = qua.declare(qua.fixed)
        else:
            override_var = qua.declare(int)

        # Determine which variable to override
        pol_duration_override = None
        pol_amp_override = None
        readout_duration_override = None
        readout_amp_override = None
        if optimize_pol_or_readout:
            if optimize_duration_or_amp:
                pol_duration_override = override_var
            else:
                pol_amp_override = override_var
        else:
            if optimize_duration_or_amp:
                readout_duration_override = override_var
            else:
                readout_amp_override = override_var

        def one_step():
            base_charge_state_histograms.macro(
                pol_coords_list,
                pol_duration_list,
                pol_amp_list,
                ion_coords_list,
                num_reps,
                pol_duration_override=pol_duration_override,
                pol_amp_override=pol_amp_override,
                readout_duration_override=readout_duration_override,
                readout_amp_override=readout_amp_override,
            )

        with qua.for_each_(override_var, step_vals):
            one_step()

    seq_ret_vals = []
    return seq, seq_ret_vals


if __name__ == "__main__":
    config_module = common.get_config_module()
    config = config_module.config
    opx_config = config_module.opx_config

    qm_opx_args = config["DeviceIDs"]["QM_opx_args"]
    qmm = QuantumMachinesManager(**qm_opx_args)
    opx = qmm.open_qm(opx_config)

    try:
        seq, seq_ret_vals = get_seq(
            [
                [110, 109.51847988358579],
                [112, 110.70156405156148],
            ],
            [
                [75.42725784791932, 75.65982013416432],
                [75.98725784791932, 74.74382013416432],
            ],
            False,
            True,
            False,
            5,
        )

        sim_config = SimulationConfig(duration=int(150e3 / 4))
        sim = opx.simulate(seq, sim_config)
        samples = sim.get_simulated_samples()
        samples.con1.plot()

    except Exception as exc:
        raise exc
    finally:
        qmm.close_all_quantum_machines()
        plt.show(block=True)
