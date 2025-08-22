# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from pathlib import Path

import geopandas as gpd
import pytest

from dave_core.create import create_grid


def test_lv_topo():
    """
    This test checks the low voltage topology generation based on an own polygon
    for the grid area.
    """
    # test own polygon
    # Hertingshausen is a part from the Town Baunatal. (ca. 500 relevant Buildings)
    own_area_path = Path(__file__).resolve().parents[2] / "examples" / "hertingshausen.geojson"
    own_area_polygon = gpd.read_file(own_area_path).iloc[0].geometry
    # run topology generation
    grid_data = create_grid(
        own_area=own_area_polygon,
        # grid level parameters
        power_levels=["lv"],
        # power grid components
        transformers=False,
        renewable_powerplants=False,
        conventional_powerplants=False,
        loads=False,
        save_data=False,
    )
    # check results
    assert not grid_data.area.empty, "No area was defined."
    assert not grid_data.buildings.commercial.empty, "No commercial building data were collected."
    assert not grid_data.buildings.residential.empty, "No residential building data were collected."
    assert not grid_data.roads.roads.empty, "No road data data were collected."
    assert (
        not grid_data.roads.road_junctions.empty
    ), "No road junctions was calculated and returned."
    assert not grid_data.landuse.empty, "No landuse data data were collected."
    assert not grid_data.lv_data.lv_nodes.empty, "No low voltage nodes were generated."
    assert not grid_data.lv_data.lv_lines.empty, "No low voltage lines were generated."
    assert (
        not grid_data.components_power.substations.mv_lv.empty
    ), "No mv/lv substation data were collected."


if __name__ == "__main__":
    pytest.main([__file__, "-xs"])
