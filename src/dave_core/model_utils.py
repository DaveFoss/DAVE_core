# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from networkx import connected_components

from dave_core.plausibility.structural_check import create_graph


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
