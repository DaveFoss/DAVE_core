# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

import copy

import matplotlib.pyplot as plt
from networkx import DiGraph
from networkx import Graph
from networkx import connected_components
from networkx import draw
from networkx.drawing.nx_agraph import graphviz_layout
from pandas import DataFrame


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


def correct_wrong_wording(edges):
    """
    In DAVE the naming of the nodes is incosistant. This function is for correcting the name if it is wrong

    INPUT:
        **edges** (GeoDataFrame) - List of lines which should be connected via steiner tree

    OUTPUT:
        **edges** (GeoDataFrame) - List of lines with corrected names
    """
    if "from_node" in edges.keys() and "from_bus" not in edges.keys():
        edges["from_bus"] = edges.apply(
            lambda x: int(x.from_node) if isinstance(x.from_node, str) else x.from_node, axis=1
        )
        edges["to_bus"] = edges.apply(
            lambda x: int(x.to_node) if isinstance(x.to_node, str) else x.to_node, axis=1
        )
    elif "from_node" in edges.keys() and "from_bus" in edges.keys():
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
