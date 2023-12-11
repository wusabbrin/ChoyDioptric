# -*- coding: utf-8 -*-
"""
Widefield ESR

Created on October 13th, 2023

@author: mccambria
"""


from qm import qua
from qm import QuantumMachinesManager
from qm.simulate import SimulationConfig
import servers.timing.sequencelibrary.QM_opx.seq_utils as seq_utils
import utils.common as common
import matplotlib.pyplot as plt


def get_seq(args, num_reps, reference=True):
    (
        pol_duration_ns,
        pol_coords_list,
        ion_duration_ns,
        ion_coords_list,
        readout_duration_ns,
        uwave_ind,
        uwave_duration_ns,
    ) = args

    if num_reps == None:
        num_reps = 1

    sig_gen_el = seq_utils.get_sig_gen_element(uwave_ind)
    uwave_duration = seq_utils.convert_ns_to_cc(uwave_duration_ns, raise_error=True)
    buffer = seq_utils.get_widefield_operation_buffer()

    with qua.program() as seq:
        seq_utils.turn_on_aods()

        def half_rep(no_uwave=False):
            # Polarization
            seq_utils.macro_polarize(pol_duration_ns, pol_coords_list)

            # Microwave sequence
            if not no_uwave:
                if uwave_duration is None:
                    qua.play("pi_pulse", sig_gen_el)
                else:
                    qua.play("on", sig_gen_el, duration=uwave_duration)
            qua.wait(buffer, sig_gen_el)
            qua.align()

            # Ionization
            seq_utils.macro_ionize(ion_duration_ns, ion_coords_list)

            # Readout
            seq_utils.macro_charge_state_readout(readout_duration_ns)

        def one_rep():
            if reference:
                for no_uwave in (False, True):
                    half_rep(no_uwave)
                    qua.align()
                    seq_utils.macro_wait_for_trigger()
            else:
                half_rep(False)
                qua.align()
                seq_utils.macro_wait_for_trigger()

        seq_utils.handle_reps(one_rep, num_reps, wait_for_trigger=False)

    seq_ret_vals = []
    return seq, seq_ret_vals


if __name__ == "__main__":
    config_module = common.get_config_module()
    config = config_module.config
    opx_config = config_module.opx_config

    ip_address = config["DeviceIDs"]["QM_opx_ip"]
    qmm = QuantumMachinesManager(host=ip_address)
    opx = qmm.open_qm(opx_config)

    try:
        args = [
            "laser_INTE_520",
            1000.0,
            [
                [112.8143831410256, 110.75435400118901],
                [112.79838314102561, 110.77035400118902],
            ],
            "laser_COBO_638",
            200,
            [
                [76.56091979499166, 75.8487161634141],
                [76.30891979499165, 75.96071616341409],
            ],
            "laser_OPTO_589",
            3500.0,
            "sig_gen_STAN_sg394",
            96 / 2,
        ]
        seq, seq_ret_vals = get_seq(args, 5)

        sim_config = SimulationConfig(duration=int(500e3 / 4))
        sim = opx.simulate(seq, sim_config)
        samples = sim.get_simulated_samples()
        samples.con1.plot()
        plt.show(block=True)

    except Exception as exc:
        raise exc
    finally:
        qmm.close_all_quantum_machines()
