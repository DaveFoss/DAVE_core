# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from copy import deepcopy

from dask_geopandas import from_geopandas
from geopandas import GeoDataFrame
from geopandas import GeoSeries
from pandas import concat
from shapely.geometry import LineString
from shapely.geometry import Point
from shapely.wkb import loads

from dave_core.components.substations import create_hv_mv_substations
from dave_core.components.substations import create_mv_lv_substations
from dave_core.geography.geo_utils import nearest_road_points
from dave_core.model_utils import disconnected_nodes
from dave_core.progressbar import create_tqdm
from dave_core.settings import dave_settings
from dave_core.toolbox import add_dave_name
from dave_core.toolbox import intersection_with_area
from dave_core.topology.topology_utils import add_nodes_to_lines
from dave_core.topology.topology_utils import run_steiner_tree


def create_mv_lines_trafos(mv_buses, roads_geometry):
    # --- create mv lines
    # find nearest points at roads and create connection lines
    nearest_points = nearest_road_points(
        mv_buses.geometry,
        roads_geometry,
    )
    nearest_points_gdf = GeoDataFrame(
        {
            "geometry": nearest_points,
            "node_type": "transformer_connection",
            "voltage_kv": dave_settings["mv_voltage"],
            "voltage_level": 5,
            "source": "dave internal",
        }
    )
    # calculate trafi lines
    bus_road_lines = GeoSeries(
        list(
            map(
                lambda x, y: LineString([x, y]),
                mv_buses.geometry,
                nearest_points,
            )
        ),
        crs=dave_settings["crs_main"],
    )
    # calculate line parameters
    bus_road_lines = bus_road_lines.set_crs(dave_settings["crs_main"])
    bus_road_lines_gdf = GeoDataFrame(
        {
            "geometry": bus_road_lines,
            "line_type": "transformer_connection",
            "length_km": bus_road_lines.length / 1000,
            "voltage_kv": dave_settings["mv_voltage"],
            "voltage_level": 5,
            "source": "dave internal",
        }
    )
    return bus_road_lines_gdf, nearest_points_gdf


def create_nodes_hvmv_subs(grid_data, hvmv_substations):
    if (
        grid_data.mv_data.mv_nodes.empty
        or "hvmv_substation" not in grid_data.mv_data.mv_nodes.node_type.unique()
    ):
        # nodes for hv/mv trafos us side
        hvmv_buses = hvmv_substations.copy(deep=True)
        hvmv_buses.crs = hvmv_substations.crs
        if not hvmv_buses.empty:
            hvmv_buses.drop(
                columns=(
                    [
                        "dave_name",
                        "lon",
                        "lat",
                        "polygon",
                        "voltage_kv",
                        "power_type",
                        "substation",
                        "osm_id",
                        "osm_www",
                        "frequency",
                        "subst_name",
                        "ref",
                        "operator",
                        "dbahn",
                        "status",
                        "otg_id",
                        "Gemeindeschluessel",
                        "geom",
                        "voltage_level",
                    ]
                ),
                inplace=True,
            )
            hvmv_buses["node_type"] = "hvmv_substation"
            # change geometry to point
            hvmv_buses["geometry"] = hvmv_buses.point.apply(lambda x: loads(x, hex=True))
            # set crs suitable to points and project to right one
            hvmv_buses.set_crs(dave_settings["crs_degree"], allow_override=True, inplace=True)
            hvmv_buses.to_crs(dave_settings["crs_main"], inplace=True)
            # filter trafos which are within the grid area
            hvmv_buses = intersection_with_area(hvmv_buses, grid_data.area)
            hvmv_buses.drop(
                columns=(
                    [
                        "point",
                    ]
                ),
                inplace=True,
            )
            hvmv_buses["voltage_level"] = 5
            hvmv_buses["voltage_kv"] = dave_settings["mv_voltage"]
            # add oep as source
            hvmv_buses["source"] = "OEP"
    else:
        hvmv_buses = grid_data.mv_data.mv_nodes[
            grid_data.mv_data.mv_nodes.node_type == "hvmv_substation"
        ]
    return hvmv_buses


def create_mv_topology(grid_data):
    """
    This function creates a dictonary with all relevant parameters for the
    medium voltage level

    INPUT:
        **grid_data** (dict) - all Informations about the target area

    OUTPUT:
        Writes data in the DaVe dataset
    """
    # set progress bar
    pbar = create_tqdm(desc="create medium voltage topology", bar_type="main_bar")
    # --- prepare mv nodes for steiner tree
    # prepare nodes including road junctions and road endings
    nodes = concat(
        [
            grid_data.mv_data.mv_nodes,
            GeoDataFrame(grid_data.road_data.road_junctions),
            grid_data.road_data.road_endings,
        ]
    )
    nodes.reset_index(drop=True, inplace=True)
    nodes["voltage_level"] = 5
    nodes["voltage_kv"] = dave_settings["mv_voltage"]
    # update progress
    pbar.update(10)
    pbar.refresh()

    # --- create mv nodes for hvmv substations
    # create hv/mv substations
    if grid_data.components_power.substations.hv_mv.empty:
        hvmv_substations = create_hv_mv_substations(grid_data)
    else:
        hvmv_substations = deepcopy(grid_data.components_power.substations.hv_mv)
    hvmv_buses = create_nodes_hvmv_subs(grid_data, hvmv_substations)
    # update progress
    pbar.update(5)
    pbar.refresh()

    # --- create mv nodes for mvlv substations
    # create mv/lv substations
    if grid_data.components_power.substations.mv_lv.empty:
        mvlv_substations = create_mv_lv_substations(grid_data)
    else:
        mvlv_substations = deepcopy(grid_data.components_power.substations.mv_lv)
    # update progress
    pbar.update(5)
    pbar.refresh()
    if (
        grid_data.mv_data.mv_nodes.empty
        or "mvlv_substation" not in grid_data.mv_data.mv_nodes.node_type.unique()
    ):
        # copy data for mv node creation
        mvlv_buses = mvlv_substations.copy()
        # nodes for mv/lv trafos hv side
        mvlv_buses.drop(
            columns=(
                ["dave_name", "la_id", "subst_id", "geom", "is_dummy", "subst_cnt", "voltage_level"]
            ),
            inplace=True,
        )
        mvlv_buses["node_type"] = "mvlv_substation"
        mvlv_buses["voltage_level"] = 5
        mvlv_buses["voltage_kv"] = dave_settings["mv_voltage"]
        # add oep as source
        mvlv_buses["source"] = "OEP"
    else:
        mvlv_buses = grid_data.mv_data.mv_nodes[
            grid_data.mv_data.mv_nodes.node_type == "mvlv_substation"
        ]
    # update progress
    pbar.update(10)
    pbar.refresh()

    # consider data only if there are more than one node in the target area
    mv_buses = concat([mvlv_buses, hvmv_buses])
    mv_buses.reset_index(drop=True, inplace=True)
    if len(mv_buses) > 1:
        # search for the substations dave name
        substations_rel = concat([hvmv_substations, mvlv_substations])
        id_to_dave = dict(
            zip(substations_rel.ego_subst_id, substations_rel.dave_name, strict=False)
        )
        mv_buses["subs_dave_name"] = mv_buses.ego_subst_id.apply(lambda x: id_to_dave[x])

        mv_buses.reset_index(drop=True, inplace=True)
        # set crs
        mv_buses.set_crs(dave_settings["crs_main"], inplace=True)

        # concat only in case the substations are not existing in nodes allready to avoid duplicates
        if "hvmv_substation" not in nodes.node_type.unique():
            nodes = concat([nodes, mv_buses[mv_buses.node_type == "hvmv_substation"]])
        if "mvlv_substation" not in nodes.node_type.unique():
            nodes = concat([nodes, mv_buses[mv_buses.node_type == "mvlv_substation"]])
        nodes.reset_index(drop=True, inplace=True)

        # create lines for transformer connections
        line_trafos, nearest_points = create_mv_lines_trafos(
            mv_buses, grid_data.road_data.roads.geometry
        )
        nodes = concat([nodes, nearest_points])

        # add dave name to nodes
        nodes = add_dave_name(nodes, "node_5")

        # add from_bus and to_bus to trafo lines
        line_trafos["from_bus"] = line_trafos.geometry.apply(
            lambda x: nodes[nodes.geometry.within(Point(x.coords[0]).buffer(1e-8))].index[0]
        )
        line_trafos["to_bus"] = line_trafos.geometry.apply(
            lambda x: nodes[nodes.geometry.within(Point(x.coords[-1]).buffer(1e-8))].index[0]
        )
        # update progress
        pbar.update(30)
        pbar.refresh()

        # --- prepare mv lines for steiner tree
        # Todo: Splitten und filtern gleich bei LV, lkann das zu roads zusammengefasst werden?
        # add substation nodes to line network
        roads_splited = add_nodes_to_lines(
            nodes,
            lines_existing=grid_data.road_data.roads,
        )
        roads_splited["voltage_kv"] = dave_settings["mv_voltage"]
        roads_splited["voltage_level"] = 5
        # update progress
        pbar.update(10)
        pbar.refresh()

        # filter isolated road areas
        if "from_node" in roads_splited.keys():
            roads_splited.rename(
                columns={"from_node": "from_bus", "to_node": "to_bus"}, inplace=True
            )
        if "geom" in nodes.keys():
            nodes.drop(columns=["geom"], inplace=True)
        nodes_disconnected = disconnected_nodes(nodes, roads_splited, 20)
        roads_splited_dask = from_geopandas(roads_splited, npartitions=dave_settings["cpu_number"])
        roads_relevant = roads_splited[
            roads_splited_dask.apply(
                lambda x: (
                    False
                    if x.from_bus in nodes_disconnected or x.to_bus in nodes_disconnected
                    else True
                ),
                axis=1,
                meta=roads_splited_dask,
            ).compute()
        ]
        # --- run steiner tree to calculate mv basic topology
        # define possible edges
        edges = concat([roads_relevant, line_trafos])
        # update progress
        pbar.update(10)
        pbar.refresh()

        # run steiner tree
        nodes_res, edges_res = run_steiner_tree(
            nodes,
            terminal_nodes=nodes[
                nodes.node_type.isin(["mvlv_substation", "hvmv_substation"])
            ].index.to_list(),
            edges=edges,
        )

        grid_data.mv_data.mv_nodes = nodes_res
        grid_data.mv_data.mv_lines = edges_res
        # update progress
        pbar.update(15)
        pbar.refresh()
        # delet duplicates in grid nodes
        grid_data.mv_data.mv_nodes = grid_data.mv_data.mv_nodes[
            ~grid_data.mv_data.mv_nodes.duplicated(subset=["dave_name"])
        ]
        # add dave name for mv_lines
        grid_data.mv_data.mv_lines = add_dave_name(grid_data.mv_data.mv_lines, "line_5")

        # search for new node indices
        grid_data.mv_data.mv_lines["from_bus"] = grid_data.mv_data.mv_lines["from_bus"].apply(
            lambda x: grid_data.mv_data.mv_nodes.loc[x].dave_name
        )
        grid_data.mv_data.mv_lines["to_bus"] = grid_data.mv_data.mv_lines["to_bus"].apply(
            lambda x: grid_data.mv_data.mv_nodes.loc[x].dave_name
        )
        # reset node index
        grid_data.mv_data.mv_nodes.reset_index(drop=True, inplace=True)
        # update progress
        pbar.update(5)
        pbar.refresh()
        # close progress bar
        pbar.close()

    else:
        # update progress
        pbar.update(80)
        pbar.refresh()
    # close progress bar
    pbar.close()
