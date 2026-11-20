# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from pandapower.powerflow import LoadflowNotConverged
from pandapower.run import runpp
from pandas import DataFrame

from dave_core.converter.create_pandapower import create_pandapower
from dave_core.model_utils import lv_net_by_net_group
from dave_core.progressbar import create_tqdm


# check power flow
def power_flow_lv_net_group(grid_data):
    """
    Checking if the power flow for each low voltage converge per net_group

    Input:
        **grid_data** (attrdict) - dave attrdict with empty tables
    """
    # set progress bar
    pbar = create_tqdm(desc="run power flow per lv net group")
    net_groups = grid_data.lv_data.lv_nodes.net_group.unique()
    # TODO: das muss parallelisiert werden
    powerflow_results = []
    for group in net_groups:
        # filter dave dataset to low voltage network and the conisdered net group
        grid_data_group = lv_net_by_net_group(grid_data, net_group=group, keep_geo=False)
        # convert net group into pandapower model
        net_power_group = create_pandapower(
            grid_data_group,
            save_data=False,
        )
        # run power flow
        try:
            runpp(net_power_group)
            powerflow_results.append(
                {
                    "net_group": group,
                    "powerflow_converges": True,
                    "min_vm_pu": net_power_group.res_bus.vm_pu.min(),
                    "max_vm_pu": net_power_group.res_bus.vm_pu.max(),
                    "max_line_loading": net_power_group.res_line.loading_percent.max(),
                    "max_trafo_loading": net_power_group.res_trafo.loading_percent.max(),
                }
            )
        except LoadflowNotConverged:
            powerflow_results.append(
                {
                    "net_group": group,
                    "powerflow_converges": False,
                }
            )
        # update progress
        pbar.update(100 / len(net_groups))
        pbar.refresh()
    # close progress bar
    pbar.close()
    # create result dataframe
    return DataFrame(powerflow_results)


def electrical_check(
    grid_data, min_vm_pu=0.95, max_vm_pu=1.05, max_line_loading=100, max_trafo_loading=100
):
    """
    This functions checks the dave model for electrical plausibility by:
        1. run power flow and check for convergence
        2. check power flow results for violations of boundary conditions

    Input:
        **grid_data** (attrdict) - dave attrdict with empty tables

    Optional:
        **min_vm_pu** (float, default 0.95) - minimal permissible node voltage in p.u. \n
        **max_vm_pu** (float, default 1.05) - maximum permissible node voltage in p.u. \n
        **max_line_loading** (int, default 100) - maximum permissible line loading in % \n
        **max_trafo_loading** (int, default 100) - maximum permissible transformer loading in % \n
    """
    # set progress bar
    pbar = create_tqdm(desc="electrical plausibility checks")
    if grid_data.target_input.power_levels.iloc[0][0] == "lv":
        # Case: Model represents only low voltage
        # run powerflow per net group
        powerflow_results = power_flow_lv_net_group(grid_data)
        print(powerflow_results)
    elif (
        len(grid_data.target_input.power_levels.iloc[0]) > 1
        and "lv" in grid_data.target_input.power_levels.iloc[0]
    ):
        # Case: Model represents multiple voltage levels including low voltage
        pass
        # hier im gesamten power flow und lv einzeln mit aufteilung per gruppe und zudem jedem Ext grid dran hängen
    else:
        # Case: Model represents one or more voltage levels without low voltage
        pass
        # convert to pandapower und direkt power flow auf ganzes model
    # close progress bar
    pbar.close()


#### Todos ####
# funktion um mv zu checken (unabhängig von lv)
# funktion und mv / lv kombination zu checken
# zusätzliche Funktion für pp diagnostic? Könnte auch mit ijn die check power flow funktion und dann check lv group (bzw. die anderen)
# funktion um zu checken ob trafogrenzen pro netzgruppe eingehalten werden (peak bei aggregierter Zeitreihe)
