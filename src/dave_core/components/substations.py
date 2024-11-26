# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details). All rights reserved.
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from dave_core.settings import dave_settings
from dave_core.toolbox import intersection_with_area
from pandas import Series, concat

from dave_pro.datapool.oep_request import oep_request


def create_hv_mv_substations(grid_data):
    """
    This function requests data for the hv/mv substations if there not already
    included in grid data
    """
    if grid_data.components_power.substations.hv_mv.empty:
        hvmv_substations, meta_data = oep_request(
            table="ego_dp_hvmv_substation"
        )  # take polygon for full area
        # add meta data
        if (
            bool(meta_data)
            and f"{meta_data['Main'].Titel.loc[0]}" not in grid_data.meta_data.keys()
        ):
            grid_data.meta_data[f"{meta_data['Main'].Titel.loc[0]}"] = meta_data
        hvmv_substations.rename(
            columns={
                "version": "ego_version",
                "subst_id": "ego_subst_id",
                "voltage": "voltage_kv",
                "ags_0": "Gemeindeschluessel",
            },
            inplace=True,
        )
        # filter substations which are within the grid area
        hvmv_substations = intersection_with_area(hvmv_substations, grid_data.area)
        if not hvmv_substations.empty:
            hvmv_substations["voltage_level"] = 4
            # add dave name
            hvmv_substations.reset_index(drop=True, inplace=True)
            hvmv_substations.insert(
                0,
                "dave_name",
                Series(list(map(lambda x: f"substation_4_{x}", hvmv_substations.index))),
            )
            # set crs
            hvmv_substations.set_crs(dave_settings["crs_main"], inplace=True)
            # add ehv substations to grid data
            grid_data.components_power.substations.hv_mv = concat(
                [grid_data.components_power.substations.hv_mv, hvmv_substations]
            )
    else:
        hvmv_substations = grid_data.components_power.substations.hv_mv.copy()
    return hvmv_substations


def create_mv_lv_substations(grid_data):
    """
    This function requests data for the mv/lv substations if there not already
    included in grid data
    """
    if grid_data.components_power.substations.mv_lv.empty:
        mvlv_substations, meta_data = oep_request(table="ego_dp_mvlv_substation")
        # add meta data
        if (
            bool(meta_data)
            and f"{meta_data['Main'].Titel.loc[0]}" not in grid_data.meta_data.keys()
        ):
            grid_data.meta_data[f"{meta_data['Main'].Titel.loc[0]}"] = meta_data
        mvlv_substations.rename(
            columns={"version": "ego_version", "mvlv_subst_id": "ego_subst_id"}, inplace=True
        )
        # change wrong crs from oep
        mvlv_substations.crs = dave_settings["crs_main"]
        # filter trafos which are within the grid area
        mvlv_substations = intersection_with_area(mvlv_substations, grid_data.area)
        if not mvlv_substations.empty:
            mvlv_substations["voltage_level"] = 6
            # add dave name
            mvlv_substations.reset_index(drop=True, inplace=True)
            mvlv_substations.insert(
                0,
                "dave_name",
                Series(list(map(lambda x: f"substation_6_{x}", mvlv_substations.index))),
            )
            # add ehv substations to grid data
            grid_data.components_power.substations.mv_lv = concat(
                [grid_data.components_power.substations.mv_lv, mvlv_substations], ignore_index=True
            )
    else:
        mvlv_substations = grid_data.components_power.substations.mv_lv.copy()
    return mvlv_substations
