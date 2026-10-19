# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from dask_geopandas import from_geopandas
from geopandas import GeoDataFrame
from geopandas import GeoSeries
from geopandas import overlay
from pandas import concat
from shapely.geometry import LineString

from dave_core.components.substations import create_mv_lv_substations
from dave_core.geography.geo_utils import nearest_road_points
from dave_core.plausibility.structural_check import disconnected_nodes
from dave_core.progressbar import create_tqdm
from dave_core.progressbar import create_tqdm_dask
from dave_core.settings import dave_settings
from dave_core.toolbox import add_dave_name
from dave_core.toolbox import related_sub
from dave_core.toolbox import voronoi
from dave_core.topology.topology_utils import add_nodes_to_lines
from dave_core.topology.topology_utils import run_steiner_tree_net_group
from dave_core.topology.topology_utils import search_end_point_id


def create_lv_lines(nodes, node_pair, line_type):
    """
    This function creates lv lines between two points
    """
    # create connections lines
    node_pair_dask = from_geopandas(node_pair, npartitions=dave_settings["cpu_number"])
    with create_tqdm_dask(desc="Create connection lines", bar_type="sub_bar"):
        line_connection = node_pair_dask.apply(
            lambda x: LineString([x[x.keys()[0]], x[x.keys()[1]]]),
            axis=1,
            meta=node_pair_dask,
        ).compute()
    # calculate line length
    line_gdf = GeoDataFrame(
        {
            "geometry": line_connection,
            "line_type": line_type,
            "length_km": line_connection.length / 1000,
            "voltage_kv": 0.4,
            "voltage_level": 7,
            "source": "dave internal",
        },
        crs=dave_settings["crs_main"],
    )
    # search node ids
    lines_geom = from_geopandas(line_gdf.geometry, npartitions=dave_settings["cpu_number"])
    with create_tqdm_dask(desc="Search lv from node ids", bar_type="sub_bar"):
        line_gdf["from_node"] = lines_geom.apply(
            lambda x: search_end_point_id(x, nodes, considered_end="from"), meta=lines_geom
        ).compute()
    with create_tqdm_dask(desc="Search lv to node ids", bar_type="sub_bar"):
        line_gdf["to_node"] = lines_geom.apply(
            lambda x: search_end_point_id(x, nodes, considered_end="to"), meta=lines_geom
        ).compute()
    return line_gdf


def create_trafo_nodes(grid_data, nodes, node_type=None):
    """
    This function creates nodes for transformers by searching the suitable substation information
    """
    # create nodes
    nodes_df = GeoDataFrame(
        {
            "geometry": nodes,
            "node_type": node_type,
            "voltage_level": 7,
            "voltage_kv": 0.4,
            "source": "dave internal",
        }
    )
    nodes_geom_dask = from_geopandas(nodes_df.geometry, npartitions=dave_settings["cpu_number"])
    # create mv/lv substations
    if grid_data.components_power.substations.mv_lv.empty:
        mvlv_substations = create_mv_lv_substations(grid_data)
    else:
        mvlv_substations = grid_data.components_power.substations.mv_lv
    # search for the substations where the lv nodes are within
    with create_tqdm_dask(desc="Search related substations", bar_type="sub_bar"):
        sub_infos = nodes_geom_dask.apply(
            lambda x: related_sub(x, mvlv_substations), meta=nodes_geom_dask
        ).compute()
    nodes_df["ego_subst_id"] = sub_infos.apply(lambda x: x[0])
    nodes_df["subst_dave_name"] = sub_infos.apply(lambda x: x[1])
    nodes_df["subst_name"] = sub_infos.apply(lambda x: x[2])
    # add dave name
    nodes_df.reset_index(drop=True, inplace=True)
    return nodes_df


def create_building_nodes(grid_data, roads):
    """
    This function creates node pairs including the building centroid and a \
        point on the road which is the closest to them

    INPUT:
        **grid_data** (attrdict) - all Informations about the grid
        **roads** (GeoDataFrame) - relevant roads to use for building connection
    """
    # shortest way between building centroid and road for relevant buildings (building connections)
    buildings_rel = concat(
        [grid_data.buildings.residential, grid_data.buildings.commercial], ignore_index=True
    )
    centroids = buildings_rel.reset_index(drop=True).centroid
    nearest_building_points = nearest_road_points(
        points=centroids,
        roads=roads.geometry,
    )
    building_connections = concat([centroids, nearest_building_points], axis=1)
    building_connections.columns = ["building_centroid", "nearest_point"]

    # add lv nodes to grid data
    building_nodes_df = concat(
        [
            GeoDataFrame(
                {
                    "geometry": building_connections.building_centroid,
                    "node_type": "building_connection",
                    "voltage_level": 7,
                    "voltage_kv": 0.4,
                    "source": "dave internal",
                }
            ),
            GeoDataFrame(
                {
                    "geometry": GeoSeries(building_connections.nearest_point).drop_duplicates(),
                    "node_type": "grid_connection",
                    "voltage_level": 7,
                    "voltage_kv": 0.4,
                    "source": "dave internal",
                }
            ),
        ],
        ignore_index=True,
    )
    # create mv/lv substations
    mvlv_substations = (
        create_mv_lv_substations(grid_data)
        if grid_data.components_power.substations.mv_lv.empty
        else grid_data.components_power.substations.mv_lv
    )

    # search for the substations where the lv nodes are within
    sub_infos = building_nodes_df.geometry.apply(lambda x: related_sub(x, mvlv_substations))
    building_nodes_df["ego_subst_id"] = sub_infos.apply(lambda x: x[0])
    building_nodes_df["subst_dave_name"] = sub_infos.apply(lambda x: x[1])
    building_nodes_df["subst_name"] = sub_infos.apply(lambda x: x[2])
    # add dave name
    building_nodes_df.reset_index(drop=True, inplace=True)
    return building_connections, building_nodes_df


def reconnect_lines(line_connections, nodes, nodes_disconnected):
    """
    This function checks if a building or trafo connection line ist connected to an node in an
    isolated area. These nodes will be deleted from the grid which makes it necessary to reconnect
    the building and trafo lines to nodes which will be part of the resulting grid.

    """
    for i, line in line_connections.iterrows():
        if line.to_node in nodes_disconnected:
            # calculate new node
            new_node_idx = (
                nodes.drop([*list(nodes_disconnected), line.from_node])
                .distance(nodes.loc[line.from_node].geometry)
                .idxmin()
            )
            line_connections.at[i, "to_node"] = new_node_idx
            # calculate new geometry
            line_connections.at[i, "geometry"] = LineString(
                [nodes.loc[line.from_node].geometry, nodes.loc[new_node_idx].geometry]
            )
    return line_connections


def create_lv_topology(grid_data):
    """
    This function creates a dictonary with all relevant geographical
    informations for the target area

    INPUT:
        **grid_data** (attrdict) - all Informations about the grid

    OUTPUT:
        Writes data in the DaVe dataset
    """
    # set main progress bar for lv topology
    pbar = create_tqdm(desc="create low voltage topology", bar_type="main_bar")
    # --- prepare lv nodes for steiner tree
    # prepare road junctions
    road_junctions = GeoDataFrame(grid_data.road_data.road_junctions)
    # get road endings as additional nodes to build lv topology
    road_endings = grid_data.road_data.road_endings
    # prepare nodes
    nodes = concat([grid_data.lv_data.lv_nodes, road_junctions, road_endings])
    nodes.reset_index(drop=True, inplace=True)
    nodes["voltage_level"] = 7
    nodes["voltage_kv"] = 0.4
    # define relevant roads
    relevant_roads = grid_data.road_data.roads.copy()
    # update progress
    pbar.update(5)
    pbar.refresh()

    # create lv nodes for building connection
    building_connections, building_nodes_df = create_building_nodes(grid_data, relevant_roads)
    nodes = concat([nodes, building_nodes_df])
    nodes.reset_index(drop=True, inplace=True)
    # create lines for building connections
    line_buildings = create_lv_lines(nodes, building_connections, line_type="line_building")
    # update progress
    pbar.update(20)
    pbar.refresh()

    # Search mvlv trafo low voltage nodes and add create lv_lines
    transformers = grid_data.components_power.transformers.mv_lv
    transformer_connections = transformers.filter(items=["geometry"])
    transformer_connections["nearest_points"] = nearest_road_points(
        points=transformers.geometry,
        roads=relevant_roads.geometry,
    )
    nodes_trafos = create_trafo_nodes(
        grid_data, transformer_connections["nearest_points"], "trafo_grid_connection"
    )

    nodes = concat([nodes, nodes_trafos])
    nodes = add_dave_name(nodes, "node_7")

    # create lines for transformer connections
    line_trafos = create_lv_lines(nodes, transformer_connections, line_type="line_mvlv_transformer")

    # TODO. Alternative wäre das man die trafosstandorte aus dem steiner tree abgleiten kann (graphen partitionoierung)
    # update progress
    pbar.update(15)
    pbar.refresh()

    # --- prepare lv lines for steiner tree
    # add new nodes to line network
    roads_splited = add_nodes_to_lines(
        nodes,
        lines_existing=relevant_roads,
    )
    roads_splited["voltage_kv"] = 0.4
    roads_splited["voltage_level"] = 7
    # update progress
    pbar.update(10)
    pbar.refresh()

    # filter isolated road areas
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
    # reconnect terminal nodes which are connected to isolated roads
    line_connections = concat([line_buildings, line_trafos])
    line_connections = reconnect_lines(line_connections, nodes, nodes_disconnected)
    # update progress
    pbar.update(10)
    pbar.refresh()

    # --- run steiner tree to calculate lv topology
    # define terminal nodes for steiner tree (nodes which should be connected)
    # terminal_nodes = nodes[nodes.dave_name.str.startswith("node")].index.to_list()

    # run voronoi analyses as steiner tree preprocessing to categorize nodes
    net_group_poly = voronoi(nodes[nodes.node_type == "mvlv_substation"])
    net_group_poly["net_group"] = net_group_poly.apply(lambda x: x.name, axis=1)

    # filter building nodes
    terminal_nodes = nodes[nodes.node_type.isin(["mvlv_substation", "building_connection"])]
    if "net_group" in terminal_nodes.keys():
        terminal_nodes.drop(columns=["net_group"], inplace=True)
    terminal_nodes = overlay(
        terminal_nodes,
        net_group_poly.drop(columns=["centroid", "dave_name"]),
        how="intersection",
    )

    # add origin node idx to terminal nodes
    dave_to_index = dict(zip(nodes["dave_name"], nodes.index, strict=False))
    terminal_nodes["node_idx"] = terminal_nodes.dave_name.apply(lambda x: dave_to_index[x])

    # define possible edges
    edges = concat(
        [
            roads_relevant.rename(columns={"from_bus": "from_node", "to_bus": "to_node"}),
            line_connections,
        ]
    )  # , edges_aux_substations
    edges.reset_index(drop=True, inplace=True)

    # update progress
    pbar.update(10)

    # run steiner tree
    grid_data.lv_data.lv_nodes = GeoDataFrame([])
    grid_data.lv_data.lv_lines = GeoDataFrame([])
    net_group_fail = net_group_poly.apply(
        lambda x: run_steiner_tree_net_group(grid_data, x, terminal_nodes, nodes, edges),
        axis=1,
    )

    # TODO: Dask ist etwas schneller, gibt aber weniger Knoten und Leitungen zurück, als es sein müssten
    # start runtime
    # _start_time = timeit.default_timer()
    # net_group_poly_dask = from_geopandas(net_group_poly, npartitions=dave_settings["cpu_number"])
    # net_group_poly_dask.apply(lambda x: run_steiner_tree_net_group(grid_data, x, nodes_buildings, nodes, edges, net_group_fail), axis=1, meta=net_group_poly_dask).compute()
    # stop and show runtime
    # _stop_time = timeit.default_timer()
    # runtime_pd = round((_stop_time - _start_time), 5)
    # print(f"runtime pd = {runtime_pd} sek")

    # check for failed net groups
    if not net_group_fail[net_group_fail.apply(lambda x: x != [])].empty:
        print(
            f"No LV structure could be found for the network groups {net_group_fail[net_group_fail.notna()].to_list()}"
        )

    # update progress
    pbar.update(25)

    # --- change duplicated nodes inidices
    # (duplicates can apear because duplicated use of nodes in diffrent net groups)
    nodes = grid_data.lv_data.lv_nodes

    # check duplicate name
    duplicate_names = nodes["dave_name"].value_counts()
    duplicate_names = duplicate_names[duplicate_names > 1].index
    duplicate_nodes = nodes[nodes.dave_name.isin(duplicate_names)]

    # delete wrong duplicated nodes (same indice and net group)
    nodes = nodes[~nodes.index.duplicated(keep="first")]

    # change node indices and adjust node references at lines  # !!! braucht sehr lange
    lines = grid_data.lv_data.lv_lines
    for node_name in duplicate_names:
        duplicated_node = duplicate_nodes[duplicate_nodes.dave_name == node_name]
        # check if there are duplicated nodes in the same net_group
        if not duplicated_node["net_group"].duplicated().any():
            # keep the first node as it is
            change_nodes = duplicated_node[1:]
            for _, change_node in change_nodes.iterrows():
                old_idx = change_node.name
                new_idx = len(nodes)
                # change node dave name
                change_node.dave_name = f"node_7_{new_idx}"
                # change index of the node
                change_node.rename(index=new_idx, inplace=True)
                # add duplicates node to nodes with new idx
                nodes = concat([nodes, change_node.to_frame().T])
                # change old node idx at lines
                mask = lines["net_group"] == change_node.net_group
                lines.loc[mask & (lines["from_node"] == old_idx), "from_node"] = new_idx
                lines.loc[mask & (lines["to_node"] == old_idx), "to_node"] = new_idx

    # fix data types
    nodes["subst_dave_name"] = nodes["subst_dave_name"].apply(
        lambda x: x if isinstance(x, str) else None
    )
    nodes["ego_version"] = nodes["ego_version"].apply(lambda x: x if isinstance(x, str) else None)
    nodes["ego_subst_id"] = nodes["ego_subst_id"].apply(lambda x: x if isinstance(x, str) else None)
    nodes["subst_name"] = nodes["subst_name"].apply(lambda x: x if isinstance(x, str) else None)
    # change nodes in dave_dataset
    grid_data.lv_data.lv_nodes = GeoDataFrame([])
    grid_data.lv_data.lv_nodes = nodes
    grid_data.lv_data.lv_nodes.set_crs(dave_settings["crs_main"], inplace=True)

    # add dave name for lv_lines
    grid_data.lv_data.lv_lines = add_dave_name(grid_data.lv_data.lv_lines, "line_7")

    # search for new node indices
    grid_data.lv_data.lv_lines["from_node"] = grid_data.lv_data.lv_lines["from_node"].apply(
        lambda x: grid_data.lv_data.lv_nodes.loc[x].dave_name
    )
    grid_data.lv_data.lv_lines["to_node"] = grid_data.lv_data.lv_lines["to_node"].apply(
        lambda x: grid_data.lv_data.lv_nodes.loc[x].dave_name
    )
    # reset node index
    grid_data.lv_data.lv_nodes.reset_index(drop=True, inplace=True)

    # TODO: quick fix of Series object in from_node / to_node
    grid_data.lv_data.lv_lines.drop(columns=["from_node", "to_node"], inplace=True)
    grid_data.lv_data.lv_lines["from_bus"] = grid_data.lv_data.lv_lines.from_bus.apply(
        lambda x: x if isinstance(x, str) else f"node_7_{x}"
    )
    grid_data.lv_data.lv_lines["to_bus"] = grid_data.lv_data.lv_lines.to_bus.apply(
        lambda x: x if isinstance(x, str) else f"node_7_{x}"
    )

    # update progress
    pbar.update(5)

    # close progress bar
    pbar.close()
