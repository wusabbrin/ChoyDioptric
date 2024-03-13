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


def get_seq(args, num_reps):
    (
        pol_coords_list,
        ion_coords_list,
        pol_duration_ns,
        ion_duration_ns,
        diff_polarize,
        diff_ionize,
    ) = args

    if num_reps is None:
        num_reps = 1

    if diff_polarize and not diff_ionize:
        do_polarize_sig = True
        do_polarize_ref = False
        do_ionize_sig = False
        do_ionize_ref = False
    elif not diff_polarize and diff_ionize:
        do_polarize_sig = True
        do_polarize_ref = True
        do_ionize_sig = True
        do_ionize_ref = False

    with qua.program() as seq:
        seq_utils.turn_on_aods()
        # qua.wait(25000)
        # qua.align()

        def half_rep(do_polarize_sub, do_ionize_sub):
            if do_polarize_sub:
                seq_utils.macro_polarize(pol_coords_list, pol_duration_ns)

            if do_ionize_sub:
                seq_utils.macro_ionize(ion_coords_list, ion_duration_ns)

            seq_utils.macro_charge_state_readout()

        def one_rep():
            for half_rep_args in [
                [do_polarize_sig, do_ionize_sig],
                [do_polarize_ref, do_ionize_ref],
            ]:
                half_rep(*half_rep_args)

                # qua.align()
                seq_utils.macro_wait_for_trigger()

        seq_utils.handle_reps(one_rep, num_reps, wait_for_trigger=False)

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
        args = [
            [
                [110, 109.51847988358679],
                [112, 110.70156405156148],
            ],
            [
                [75.42725784791932, 75.65982013416432],
                [75.98725784791932, 74.74382013416432],
            ],
            1000.0,
            1000.0,
            False,
            True,
        ]
        seq, seq_ret_vals = get_seq(args, 5)

        sim_config = SimulationConfig(duration=int(1e6 / 4))
        sim = opx.simulate(seq, sim_config)
        samples = sim.get_simulated_samples()
        samples.con1.plot()
        plt.show(block=True)

    except Exception as exc:
        raise exc
    finally:
        qmm.close_all_quantum_machines()
