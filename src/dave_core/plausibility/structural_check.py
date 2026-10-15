# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from networkx import connected_components
from networkx import node_connected_component

from dave_core.model_utils import create_graph


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


def find_open_ends(nodes, edges):
    """
    This functions searches for open ends in a network topology e.g. for localization of external \
        grids and network equivalents
    """
    # create graph
    graph = create_graph(nodes, edges)
    # find open ends in graph
    return [node for node in graph.nodes() if graph.degree(node) == 1]
