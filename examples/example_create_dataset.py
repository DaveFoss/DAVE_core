# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from pathlib import Path

import geopandas as gpd

from dave_core import dave_settings
from dave_core.create import create_grid

"""
This is a example file for testing dave
"""
########## Examples for grid area definition #########################
# test target by plz
_postalcode_1 = ["34225"]  # Baunatal
_postalcode_2 = [
    "37085",
    "37075",
    "37083",
    "37079",
    "37081",
    "37073",
    "37077",
]  # Göttingen
_postalcode_3 = ["ALL"]  # all postal code areas in germany

# test target by town_name
_town_name_1 = ["Göttingen"]
_town_name_2 = ["KAsSel", "Baunatal"]
_town_name_3 = ["ALL"]  # all town names in germany

# test target by federal state
_federal_state_1 = ["Hessen"]
_federal_state_2 = ["HeSsEn", "SchleSWIg-HOLstein"]
_federal_state_3 = ["ALL"]  # all federal states in germany

# test target by nuts-region
_nuts_1 = ["DE"]  # nuts level 0
_nuts_2 = ["DE11A", "DE11B"]  # nuts level 3
_nuts_3 = ["DEF", "DE60"]  # example for diffrent nuts level combined(1 and 2)
_nuts_4 = (["DE1"], "2021")  # nuts level 1 and other year

# test own shape
# Hertingshausen is a part from the Town Baunatal. (ca. 500 relevant Buildings)
own_area_polygon = (
    gpd.read_file(f"{Path(__file__).parent}\\example_geodata.gpkg", layer="hertingshausen")
    .iloc[0]
    .geometry
)


##################### test main function ##########################
"""
This is the main function for DAVE with all possible parameters.
For testing you can use the pre defined variables on the top or own ones.
"""


grid_data = create_grid(
    # grid area parameters (select on of the following five options)
    postalcode=None,
    town_name=None,
    federal_state=None,
    nuts_region=None,
    own_area=own_area_polygon,
    # geographical parameters
    geodata=["roads", "railways"],
    # grid level parameters
    power_levels=["lv"],
    gas_levels=[],
    # --- optional parameters
    opt_model=False,
    combine_areas=[],
    # converting parameters
    convert_power=[],  # if True a second return variable must be defined
    convert_gas=[],  # if True a second return variable must be defined
    # power grid components
    transformers=True,
    renewable_powerplants=False,
    conventional_powerplants=False,
    loads=False,
    # gas grid components
    compressors=False,
    sinks=False,
    sources=False,
    # output settings
    output_folder=dave_settings["dave_output_dir"],
    output_format="GPKG",
    save_data=True,
)
