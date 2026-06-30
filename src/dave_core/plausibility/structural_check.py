# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from geopandas import GeoDataFrame
from networkx import Graph
from networkx import connected_components
from pandas import concat

from dave_core.progressbar import create_tqdm
from dave_core.settings import dave_settings


def correct_wrong_wording(edges):
    """
    In DAVE the naming of the nodes is incosistant. This function is for correcting the name if it is wrong

    INPUT:
        **edges** (GeoDataFrame) - List of lines which should be connected via steiner tree

    OUTPUT:
        **edges** (GeoDataFrame) - List of lines with corrected names
    """
    if "from_node" in edges.keys():
        edges["from_bus"] = edges.apply(
            lambda x: x.from_bus if isinstance(x.from_bus, str) else x.from_node, axis=1
        )
        edges["to_bus"] = edges.apply(
            lambda x: x.to_bus if isinstance(x.to_bus, str) else x.to_node, axis=1
        )
    return edges


def create_graph(nodes, edges, weight_parameter=None):
    """
    Create network x graph

    INPUT:
        **nodes** (GeoDataFrame) - all nodes which can be considered (including auxillary nodes like road junctions)
        **edges** (GeoDataFrame) - List of lines which should be connected via steiner tree
        **weight_parameter** (String) - Name of the parameter in edges which defines the weight factor

    OUTPUT:
        **graph** (networkx graph element) - resulting networkx graph
    """
    # create empty graph
    graph = Graph()

    # create nodes
    graph.add_nodes_from(nodes.index.to_list())

    # correct bus/node wording
    edges = correct_wrong_wording(edges)
    # create edges
    if weight_parameter:
        graph.add_weighted_edges_from(
            edges.apply(
                lambda x: (x["from_bus"], x["to_bus"], x[weight_parameter]), axis=1
            ).to_list()
        )
    else:
        graph.add_edges_from(edges.apply(lambda x: (x["from_bus"], x["to_bus"]), axis=1).to_list())
    return graph


def disconnected_nodes(nodes, edges, min_number_nodes):
    """
    Identify disconnected nodes in a network by converting data to a networkX \
        graph and checks connectivity

    INPUT:
             **nodes** (DataFrame) - Dataset of nodes with DaVe name  \n
             **edges** (DataFrame) - Dataset of edges (lines, pipelines) with DaVe name \n
    OUTPUT:
             **nodes** (set) - all dave names for nodes which are not connected to a grid with a minumum
             number of nodes \n

    """

    # create graph
    graph = create_graph(nodes, edges)

    # Find disconnected nodes
    disconnected = set()
    for component in connected_components(graph):
        if len(component) < min_number_nodes:
            disconnected.update(component)

    print(f"Disconnected nodes ({len(disconnected)}):", list(disconnected)[:10])
    return disconnected


def find_open_ends(nodes, edges):
    """
    This functions searches for open ends in a network topology e.g. for localization of external \
        grids and network equivalents
    """
    # create graph
    graph = create_graph(nodes, edges)
    # find open ends in graph
    return [node for node in graph.nodes() if graph.degree(node) == 1]


def clean_disconnected_elements_power(grid_data, min_number_nodes):
    """
    This function cleans up disconnected elements for the different power grid levels.
    Handles missing columns like 'dave_name', 'from_bus', 'to_bus' gracefully.
    """
    # --- collect all nodes and lines
    nodes_all = concat(
        [
            grid_data.ehv_data.ehv_nodes,
            grid_data.hv_data.hv_nodes,
            grid_data.mv_data.mv_nodes,
            grid_data.lv_data.lv_nodes,
        ],
        ignore_index=True,
    )

    lines_all = concat(
        [
            grid_data.ehv_data.ehv_lines,
            grid_data.hv_data.hv_lines,
            grid_data.mv_data.mv_lines,
            grid_data.lv_data.lv_lines,
        ],
        ignore_index=True,
    )

    # ensure standard column names exist
    if "from_bus" not in lines_all.columns:
        lines_all.rename(columns={"from_node": "from_bus"}, inplace=True)
    if "to_bus" not in lines_all.columns:
        lines_all.rename(columns={"to_node": "to_bus"}, inplace=True)

    trafos_all = concat(
        [
            grid_data.components_power.transformers.ehv_ehv,
            grid_data.components_power.transformers.ehv_hv,
            grid_data.components_power.transformers.hv_mv,
            grid_data.components_power.transformers.mv_lv,
        ],
        ignore_index=True,
    )

    if "bus_hv" in trafos_all.columns:
        trafos_all.rename(columns={"bus_hv": "from_bus", "bus_lv": "to_bus"}, inplace=True)

    # ensure 'dave_name' exists for all nodes
    for level in grid_data.target_input.power_levels.iloc[0]:
        nodes = grid_data[f"{level}_data"][f"{level}_nodes"]
        if "dave_name" not in nodes.columns:
            nodes = nodes.copy()
            nodes["dave_name"] = nodes.index.to_series().apply(
                lambda x, level=level: f"{level}_node_{x}"
            )
            grid_data[f"{level}_data"][f"{level}_nodes"] = nodes

    # get disconnected nodes
    if not nodes_all.empty:
        nodes_dis = list(
            disconnected_nodes(
                nodes=nodes_all,
                edges=concat([lines_all, trafos_all], ignore_index=True),
                min_number_nodes=min_number_nodes,
            )
        )

        for level in grid_data.target_input.power_levels.iloc[0]:
            nodes = grid_data[f"{level}_data"][f"{level}_nodes"]
            lines = grid_data[f"{level}_data"][f"{level}_lines"]

            # safe filtering of disconnected lines
            if "from_bus" in lines.columns:
                lines_dis = lines[lines.from_bus.isin(nodes_dis)]
            else:
                lines_dis = GeoDataFrame(columns=lines.columns)

            # --- clean other power components
            for component_typ in grid_data.components_power.keys():
                if component_typ not in ["transformers", "substations"]:
                    if not grid_data.components_power[component_typ].empty:
                        comp = grid_data.components_power[component_typ]
                        if "bus" in comp.columns:
                            to_drop = comp[comp.bus.isin(nodes_dis)].index
                            grid_data.components_power[component_typ].drop(to_drop, inplace=True)
                            grid_data.components_power[component_typ].reset_index(
                                drop=True, inplace=True
                            )

                elif component_typ == "transformers":
                    for subtyp, comp in grid_data.components_power[component_typ].items():
                        if not comp.empty and "bus_hv" in comp.columns and "bus_lv" in comp.columns:
                            to_drop = comp[
                                comp.bus_hv.isin(nodes_dis) & comp.bus_lv.isin(nodes_dis)
                            ].index
                            grid_data.components_power[component_typ][subtyp].drop(
                                to_drop, inplace=True
                            )
                            grid_data.components_power[component_typ][subtyp].reset_index(
                                drop=True, inplace=True
                            )

                elif component_typ == "substations":
                    for subtyp, comp in grid_data.components_power[component_typ].items():
                        if not comp.empty and "dave_name" in nodes.columns:
                            subst_to_drop = nodes[nodes.dave_name.isin(nodes_dis)].subst_dave_name
                            if not subst_to_drop.isnull().all():
                                to_drop = comp[comp.dave_name.isin(nodes_dis)].index
                                grid_data.components_power[component_typ][subtyp].drop(
                                    to_drop, inplace=True
                                )
                                grid_data.components_power[component_typ][subtyp].reset_index(
                                    drop=True, inplace=True
                                )

            # --- drop disconnected nodes and lines
            grid_data[f"{level}_data"][f"{level}_nodes"].drop(
                nodes[nodes.dave_name.isin(nodes_dis)].index, inplace=True
            )
            grid_data[f"{level}_data"][f"{level}_nodes"].reset_index(drop=True, inplace=True)

            grid_data[f"{level}_data"][f"{level}_lines"].drop(lines_dis.index, inplace=True)
            grid_data[f"{level}_data"][f"{level}_lines"].reset_index(drop=True, inplace=True)


def clean_disconnected_elements_gas(grid_data, min_number_nodes):
    """
    This function clean up disconnected elements for the diffrent gas grid levels
    """
    # get disconnected junctions
    junctions_all = concat(
        [
            grid_data.hp_data.hp_junctions,
            grid_data.mp_data.mp_junctions,
            grid_data.lp_data.lp_junctions,
        ],
        ignore_index=True,
    )
    pipelines_all = concat(
        [
            grid_data.hp_data.hp_pipes,
            grid_data.mp_data.mp_pipes,
            grid_data.lp_data.lp_pipes,
        ],
        ignore_index=True,
    )  # TODO Verbindung der Netzebenen mit einbeziehen z.B. Trafos
    pipelines_all.rename(
        columns={"from_junction": "from_node", "to_junction": "to_node"},
        inplace=True,
    )
    if not junctions_all.empty:
        junctions_dis = list(
            disconnected_nodes(
                nodes=junctions_all,
                edges=pipelines_all,
                min_number_nodes=min_number_nodes,
            )
        )
        # drop elements for each level which are disconnected
        for level in grid_data.target_input.gas_levels.iloc[0]:
            junctions = grid_data[f"{level}_data"][f"{level}_junctions"]
            pipelines = grid_data[f"{level}_data"][f"{level}_pipes"]
            # filter disconnected pipelines based on disconnected junctions
            pipelines_dis = pipelines[pipelines.from_junction.isin(junctions_dis)]
            # filter gas components which connected to disconnected junctions
            gas_components = list(grid_data.components_gas.keys())
            for component_typ in gas_components:
                if not grid_data.components_gas[f"{component_typ}"].empty:
                    components = grid_data.components_gas[f"{component_typ}"]
                    # delet needless gas components
                    grid_data.components_gas[f"{component_typ}"].drop(
                        components[components.junction.isin(junctions_dis)].index.to_list(),
                        inplace=True,
                    )
                    grid_data.components_gas[f"{component_typ}"].reset_index(
                        drop=True, inplace=True
                    )
            # delet needless junctions and pipelines
            grid_data[f"{level}_data"][f"{level}_junctions"].drop(
                junctions[junctions.dave_name.isin(junctions_dis)].index.to_list(),
                inplace=True,
            )
            grid_data[f"{level}_data"][f"{level}_junctions"].reset_index(drop=True, inplace=True)
            grid_data[f"{level}_data"][f"{level}_pipes"].drop(
                pipelines_dis.index.to_list(), inplace=True
            )
            grid_data[f"{level}_data"][f"{level}_pipes"].reset_index(drop=True, inplace=True)


def clean_wrong_piplines(grid_data):
    """
    This function drops gas pipelines which have wrong charakteristics
    """
    for level in grid_data.target_input.gas_levels.iloc[0]:
        pipelines = grid_data[f"{level}_data"][f"{level}_pipes"]
        if not pipelines.empty:
            # check if piplines have the same start and end point
            pipelines_equal = pipelines[pipelines.from_junction == pipelines.to_junction]
            # delet needless pipelines
            grid_data[f"{level}_data"][f"{level}_pipes"].drop(
                pipelines_equal.index.to_list(), inplace=True
            )
            grid_data[f"{level}_data"][f"{level}_pipes"].reset_index(drop=True, inplace=True)


def clean_wrong_lines(grid_data):
    """
    This function drops power lines which have wrong charakteristics
    """
    for level in grid_data.target_input.power_levels.iloc[0]:
        lines = grid_data[f"{level}_data"][f"{level}_lines"]
        if not lines.empty:
            # check if piplines have the same start and end point
            lines_equal = lines[lines.from_bus == lines.to_bus]
            # delet needless pipelines
            grid_data[f"{level}_data"][f"{level}_lines"].drop(
                lines_equal.index.to_list(), inplace=True
            )
            grid_data[f"{level}_data"][f"{level}_lines"].reset_index(drop=True, inplace=True)


def clean_up_data(grid_data, min_number_nodes=dave_settings["min_number_nodes"]):
    """
    This function clean up the DAVE Dataset for diffrent kinds of failures
    """
    # set progress bar
    pbar = create_tqdm(desc="clean up dave dataset")

    # --- clean up power grid data
    if grid_data.target_input.iloc[0].power_levels:
        # clean up disconnected elements
        clean_disconnected_elements_power(grid_data, min_number_nodes)
        # update progress
        pbar.update(40)
        # clean up lines with wrong characteristics
        clean_wrong_lines(grid_data)
        # update progress
        pbar.update(10)
    else:
        # update progress
        pbar.update(50)
    # --- clean up gas grid data
    if grid_data.target_input.iloc[0].gas_levels:
        # clean up disconnected elements
        clean_disconnected_elements_gas(grid_data, min_number_nodes)
        # update progress
        pbar.update(40)
        # clean up pipelines with wrong characteristics
        clean_wrong_piplines(grid_data)
        # update progress
        pbar.update(10)
    else:
        # update progress
        pbar.update(50)
    # close progress bar
    pbar.close()
