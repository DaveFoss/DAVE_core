# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

import copy

import matplotlib.pyplot as plt
from networkx import DiGraph
from networkx import connected_components
from networkx import draw
from networkx import node_connected_component
from networkx.drawing.nx_agraph import graphviz_layout
from pandas import DataFrame
from pandas import concat
from pandas import isnull
from tqdm import tqdm

from dave_core.plausibility.structural_check import create_graph
from dave_core.settings import dave_settings


def filter_isolated_edges(edges, nodes):
    """
    This function checks for edges in a graph which are not connected to the most of the others

    INPUT:
        **edges** (GeoDataFrame) - all edges in the grid area
        **nodes** (GeoDataFrame) - all nodes in the grid area

    Output:
        **edges** (GeoDataFrame) - filtered edges

    """
    # create graph
    graph = create_graph(nodes, edges)
    # check for disconnected edges
    connected_elements = list(connected_components(graph))
    main_subgraph = connected_elements[0]
    # filter isolated roads
    edges_filtered = edges[edges.from_bus.isin(main_subgraph)]
    edges_filtered = edges_filtered[edges_filtered.to_bus.isin(main_subgraph)]
    return edges_filtered


def create_directed_graph(nodes, edges):
    """
    Create directed network x graph
    """
    # create empty directed graph
    graph = DiGraph()
    # create nodes
    graph.add_nodes_from(nodes.index.to_list())
    # create edges
    graph.add_edges_from(edges.apply(lambda x: (x["from_bus"], x["to_bus"]), axis=1).to_list())
    return graph


def plot_graph(graph):
    """
    Function for plotting a graph
    """
    pos = graphviz_layout(graph, prog="dot")
    draw(graph, pos, with_labels=True, arrows=True)
    plt.show()


def direction_away_from_node(graph, target_node):
    """
    This function change the direction of all edges in a directed graph to point away from a \
    certain bus.

    Attention: Only usable for beam networks! If you have isolated parts of the network (e.g. \
    net groups) you have to hand over all slack nodes

    INPUT:
        **graph** (networkx graph) - directed graph \n
        **target_node** (list(int)) - Number of the node from which all lines should point away \n
    """
    edges_to_reverse = []
    # take care of do not checking nodes twice to avoid a loop
    checked_nodes = target_node.copy()
    # initialise check node
    check_node = target_node.copy()
    while len(check_node) > 0:
        # check for predecessor and successor nodes to get information of the direction of the connecting line
        predecessor_nodes = list(graph.predecessors(check_node[0]))  # wrong direction
        successors_nodes = list(graph.successors(check_node[0]))  # right direction
        # save edges which have to change
        for node in predecessor_nodes:
            if node not in checked_nodes:
                # save edge with wrong direction to correct later
                edges_to_reverse.append((node, check_node[0]))
                # update check node lists
                check_node += [node]
                checked_nodes += [node]
        for node in successors_nodes:
            if node not in checked_nodes:
                check_node += [node]
                checked_nodes += [node]
        check_node.pop(0)
    # change direction of edges which are point to target node
    for from_bus, to_bus in set(edges_to_reverse):
        graph.remove_edge(from_bus, to_bus)
        graph.add_edge(to_bus, from_bus)
    return graph


def check_terminal_subgraph(graph, terminal_nodes):
    """
    This function checks which terminal nodes are in a diffrent subgraph than the first terminal node

    INPUT:
        **graph** (networkx graph) - Graph which defines the basis for the \n
            network generation
        **terminal_nodes** (list) - List of the terminal nodes in graph \n
    """
    # switch graph to a undirected one
    graph_und = graph.to_undirected()
    if terminal_nodes:
        # check components in the subgraph of the first terminal node
        comp = node_connected_component(graph_und, terminal_nodes[0])
        not_in_comp = [t for t in terminal_nodes if t not in comp]
        if not_in_comp:
            print("terminal nodes in another subgraph:", not_in_comp)


def disconnected_nodes(nodes, edges, min_number_nodes):
    """
    converts nodes and lines to a networkX graph and checks for isolated parts of the graphs / nodes

    INPUT:
        **nodes** (DataFrame) - Dataset of nodes with DaVe name  \n
        **edges** (DataFrame) - Dataset of edges (lines, pipelines) with DaVe name \n
    OUTPUT:
        **nodes_disconnected** (set) - all dave names for nodes which are not connected to a grid with a minumum
                          number of nodes \n
    """
    # create graph
    graph = create_graph(nodes[["dave_name", "geometry"]], edges)
    # check for disconnected nodes
    nodes_disconnected = set()
    for elements in list(connected_components(graph)):
        if len(elements) < min_number_nodes:
            for node in elements:
                nodes_disconnected.add(node)
    return nodes_disconnected


def disconnected_nodes_subgraph(nodes, edges, terminal_nodes):
    """
    converts nodes and lines to a networkX graph and checks all subgraphs if anyone contains all terminal nodes

    INPUT:
        **nodes** (DataFrame) - Dataset of nodes with DaVe name  \n
        **edges** (DataFrame) - Dataset of edges (lines, pipelines) with DaVe name \n
    OUTPUT:
        **nodes** (set) - all dave names for nodes which are not connected to a grid with a minumum
                          number of nodes \n
    """
    # create graph
    graph = create_graph(nodes, edges)
    # check for terminal nodes in diffrent subgraphs
    check_terminal_subgraph(graph, terminal_nodes)
    # check for disconnected nodes
    nodes_disconnected = set()
    connected_elements = list(connected_components(graph))
    for subgraph in connected_elements:
        if not all(x in subgraph for x in terminal_nodes):
            nodes_disconnected.update(subgraph)
    return nodes_disconnected


def clean_disconnected_elements_power(grid_data, min_number_nodes):
    """
    This function clean up disconnected elements for the diffrent power grid levels
    """
    # get disconnected nodes
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
    trafos_all = concat(
        [
            grid_data.components_power.transformers.ehv_ehv,
            grid_data.components_power.transformers.ehv_hv,
            grid_data.components_power.transformers.hv_mv,
            grid_data.components_power.transformers.mv_lv,
        ],
        ignore_index=True,
    )
    trafos_all.rename(columns={"bus_hv": "from_bus", "bus_lv": "to_bus"}, inplace=True)
    if not nodes_all.empty:
        nodes_dis = list(
            disconnected_nodes(
                nodes=nodes_all,
                edges=concat(
                    [lines_all, trafos_all],
                    ignore_index=True,
                ),
                min_number_nodes=min_number_nodes,
            )
        )
        # drop elements for each level which are disconnected
        for level in grid_data.target_input.power_levels.iloc[0]:
            nodes = grid_data[f"{level}_data"][f"{level}_nodes"]
            lines = grid_data[f"{level}_data"][f"{level}_lines"]
            # filter disconnected lines based on disconnected nodes
            lines_dis = lines[lines.from_bus.isin(nodes_dis)]
            # filter power components which connected to disconnected junctions
            power_components = list(grid_data.components_power.keys())
            for component_typ in power_components:
                if (
                    component_typ not in ["transformers", "substations"]
                    and not grid_data.components_power[f"{component_typ}"].empty
                ):
                    components = grid_data.components_power[f"{component_typ}"]
                    # delet needless power components
                    grid_data.components_power[f"{component_typ}"].drop(
                        components[components.bus.isin(nodes_dis)].index.to_list(), inplace=True
                    )
                    grid_data.components_power[f"{component_typ}"].reset_index(
                        drop=True, inplace=True
                    )
                elif component_typ == "transformers":
                    # this components have a sub type
                    power_components_sub = list(
                        grid_data.components_power[f"{component_typ}"].keys()
                    )
                    for component_subtyp in power_components_sub:
                        if not grid_data.components_power[f"{component_typ}"][
                            f"{component_subtyp}"
                        ].empty:
                            components = grid_data.components_power[f"{component_typ}"][
                                f"{component_subtyp}"
                            ]
                            # delet needless power components
                            grid_data.components_power[f"{component_typ}"][
                                f"{component_subtyp}"
                            ].drop(
                                components[
                                    components.bus_hv.isin(nodes_dis)
                                    & components.bus_lv.isin(nodes_dis)
                                ].index.to_list(),
                                inplace=True,
                            )
                            grid_data.components_power[f"{component_typ}"][
                                f"{component_subtyp}"
                            ].reset_index(drop=True, inplace=True)
                elif component_typ == "substation":
                    # this components have a sub type
                    power_components_sub = list(
                        grid_data.components_power[f"{component_typ}"].keys()
                    )
                    for component_subtyp in power_components_sub:
                        if not grid_data.components_power[f"{component_typ}"][
                            f"{component_subtyp}"
                        ].empty:
                            components = grid_data.components_power[f"{component_typ}"][
                                f"{component_subtyp}"
                            ]
                            # delet needless power components
                            substation_dis = nodes[nodes.dave_name.isin(nodes_dis)].subst_dave_name
                            if ~isnull(substation_dis).all():
                                grid_data.components_power[f"{component_typ}"][
                                    f"{component_subtyp}"
                                ].drop(
                                    components[
                                        components.dave_name.isin(nodes_dis)
                                    ].index.to_list(),
                                    inplace=True,
                                )
                                grid_data.components_power[f"{component_typ}"][
                                    f"{component_subtyp}"
                                ].reset_index(drop=True, inplace=True)

            # delet needless nodes and lines
            grid_data[f"{level}_data"][f"{level}_nodes"].drop(
                nodes[nodes.dave_name.isin(nodes_dis)].index.to_list(), inplace=True
            )
            grid_data[f"{level}_data"][f"{level}_nodes"].reset_index(drop=True, inplace=True)
            grid_data[f"{level}_data"][f"{level}_lines"].drop(
                lines_dis.index.to_list(), inplace=True
            )
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
        [grid_data.hp_data.hp_pipes, grid_data.mp_data.mp_pipes, grid_data.lp_data.lp_pipes],
        ignore_index=True,
    )  # !!! Todo: Verbindung der Netzebenen mit einbeziehen z.B. Trafos
    pipelines_all.rename(
        columns={"from_junction": "from_node", "to_junction": "to_node"}, inplace=True
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
                junctions[junctions.dave_name.isin(junctions_dis)].index.to_list(), inplace=True
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
    This function clean up the DaVe Dataset for diffrent kinds of failures
    """
    # set progress bar
    pbar = tqdm(
        total=100,
        desc="clean up dave dataset:             ",
        position=0,
        bar_format=dave_settings["bar_format"],
    )
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


# !!! Todo's clean up:
# Leitungen mit Länge 0
# pandapower diagnostic nochmal genauer anschauen


def lv_net_by_net_group(grid_data, net_group, keep_geo=True):
    """
    This function reduces the dave dataset to a specific low voltage net_group. Only the net \
    elements which are connected to this group will keeped

    First only works for lv level

    INPUT:
        **grid_data** (attrdict) - all Informations about the grid
        **net_group** (int) - Number of the net group to which the network model should be reduced

    OPTIONAL:
        **keep_geo** (bool, default True) - defines whether the geodata should be retained

    OUTPUT:
        **grid_data_red** (attrdict) - grid data reduced to considered net group

    """
    grid_data_red = copy.deepcopy(grid_data)
    # delet geographical data
    if keep_geo:
        pass
        # TODO: Hier noch Geodata reduzieren mittels konvexer Hülle und intersection
    else:
        # delete all geodata
        grid_data_red.buildings.commercial = DataFrame([])
        grid_data_red.buildings.residential = DataFrame([])
        grid_data_red.buildings.other = DataFrame([])
        grid_data_red.roads.roads = DataFrame([])
        grid_data_red.roads.road_junctions = DataFrame([])
        grid_data_red.landuse = DataFrame([])
        grid_data_red.waterways = DataFrame([])
        grid_data_red.railways = DataFrame([])

    # reduce lv topology
    if not grid_data_red.lv_data.lv_nodes.empty:
        grid_data_red.lv_data.lv_nodes = grid_data_red.lv_data.lv_nodes[
            grid_data_red.lv_data.lv_nodes.net_group == net_group
        ]
    if not grid_data_red.lv_data.lv_lines.empty:
        grid_data_red.lv_data.lv_lines = grid_data_red.lv_data.lv_lines[
            grid_data_red.lv_data.lv_lines.net_group == net_group
        ]

    # reduce network components
    nodes_rel = grid_data_red.lv_data.lv_nodes.dave_name.to_list()
    if not grid_data_red.components_power.loads.empty:
        grid_data_red.components_power.loads = grid_data_red.components_power.loads[
            grid_data_red.components_power.loads.bus.isin(nodes_rel)
        ]
    if not grid_data_red.components_power.renewable_powerplants.empty:
        grid_data_red.components_power.renewable_powerplants = (
            grid_data_red.components_power.renewable_powerplants[
                grid_data_red.components_power.renewable_powerplants.bus.isin(nodes_rel)
            ]
        )
    if not grid_data_red.components_power.conventional_powerplants.empty:
        grid_data_red.components_power.conventional_powerplants = (
            grid_data_red.components_power.conventional_powerplants[
                grid_data_red.components_power.conventional_powerplants.bus.isin(nodes_rel)
            ]
        )
    if not grid_data_red.components_power.transformers.mv_lv.empty:
        grid_data_red.components_power.transformers.mv_lv = (
            grid_data_red.components_power.transformers.mv_lv[
                grid_data_red.components_power.transformers.mv_lv.bus_lv.isin(nodes_rel)
            ]
        )
    # TODO: Substations müssen auch ncoh gefiltert werden

    # delet other topologys
    grid_data_red.ehv_data.ehv_nodes = DataFrame([])
    grid_data_red.hv_data.hv_nodes = DataFrame([])
    grid_data_red.mv_data.mv_nodes = grid_data_red.mv_data.mv_nodes[
        grid_data_red.mv_data.mv_nodes.dave_name.isin(
            grid_data_red.components_power.transformers.mv_lv.bus_hv.to_list()
        )
    ]
    grid_data_red.ehv_data.ehv_lines = DataFrame([])
    grid_data_red.hv_data.hv_lines = DataFrame([])
    grid_data_red.mv_data.mv_lines = DataFrame([])

    # delet other components
    grid_data_red.components_power.transformers.hv_mv = DataFrame([])
    grid_data_red.components_power.transformers.ehv_hv = DataFrame([])

    # reduce target_input
    grid_data_red.target_input.power_levels.iloc[0] = ["lv"]
    return grid_data_red
