# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


# funktionen um die Netzmodelle aus elektrotechnischer sicht zu plausibilisieren

# funktioniert LAstfluss (iterativ über die einzelnen netzgruppen
# => Wirklich einzeln rechnen
# passen die Werte oder gibt es besondere ausreißer? Könnte man auch checken ob der max wert viel höher ist als der avarage


# convert to pandapower
# read pandapower
# net = from_json(
#     r"C:\Users\tbanze\Eigene Datein\SimBench Sektor\Netzmodell Düsseldorf\duesseldorf_dave_pandapower.json"
# )
# !!! in dem net sind keine Gruppen, das muss im Converter angepasst werden. Es sind auch keine  ext grids drin


# Überlegen, ob ich hier auch das dave netz nehme, nach den netzgruppen filter und dann erst zu pp convertiere

from dave_core.model_utils import lv_net_by_net_group


# check load flow
def check_power_flow_lv_net_group(grid_data):
    """
    Checking if the power flow for each low voltage converge per net_group

    Input:
        **grid_data** (attrdict) - dave attrdict with empty tables
    """
    net_groups = grid_data.lv_data.lv_nodes.net_group.unique()
    for group in net_groups:
        # filter dave dataset to low voltage network and the conisdered net group
        grid_data_group = lv_net_by_net_group(grid_data, net_group=group, keep_geo=False)
        print(grid_data_group)
        # convert net group into pandapower model

        # run power flow
        # !!! hier mit try and except und mitzählen, welche Netzgruppen nicht k,onvergieren und wie viele (ggf. in Prozent)


# funktion um mv zu checken (unabhängig von lv)

# funktion und mv / lv kombination zu checken

# zusätzliche Funktion für pp diagnostic? Könnte auch mit ijn die check power flow funktion und dann check lv group (bzw. die anderen)

# funktion um zu checken ob trafogrenzen pro netzgruppe eingehalten werden (peak bei aggregierter Zeitreihe)
