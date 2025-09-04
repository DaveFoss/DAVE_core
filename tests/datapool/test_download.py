# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from pathlib import Path

import pytest
import requests
from geopandas import GeoDataFrame
from geopandas import read_file

from dave_core.dave_structure import create_empty_dataset
from dave_core.geography.osm_data import get_osm_data
from dave_core.settings import dave_settings


def test_fhg_data_availability():
    response = requests.head(
        dave_settings["fhg_oc_url"],
        timeout=10,
    )  # Verwende HEAD, um nur die Header abzurufen
    assert response.status_code == 200, f"Data Repo is not available: {response.status_code}"


def test_oep_availability():
    response = requests.head(
        dave_settings["oep_url"], verify=False, timeout=10
    )  # Verwende HEAD, um nur die Header abzurufen
    assert response.status_code == 200, f"Data Repo is not available: {response.status_code}"


def test_osm_request():
    grid_data = create_empty_dataset()
    # define example area
    area = read_file(
        Path(__file__).resolve().parents[2] / "examples" / "example_geodata.gpkg", layer="iee"
    )
    border = area.iloc[0].geometry
    # request building data
    buildings = get_osm_data(
        grid_data,
        "building",
        border=border,
        target_geom=border.buffer(dave_settings["osm_area_buffer"]),
    )  # !!! was ist target_area
    # check results
    assert isinstance(buildings, GeoDataFrame)
    assert not buildings.empty
    assert any(buildings["name"].str.contains("Fraunhofer IEE"))


if __name__ == "__main__":
    pytest.main([__file__, "-xs"])
