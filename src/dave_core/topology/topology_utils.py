# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from dask_geopandas import from_geopandas
from geopandas import GeoDataFrame
from networkx import Graph
from networkx import connected_components
from networkx.algorithms.approximation.steinertree import steiner_tree
from pandas import concat
from shapely.geometry import MultiPoint
from shapely.geometry import Point
from shapely.ops import snap
from shapely.ops import split

from dave_core.model_utils import create_graph
from dave_core.plausibility.structural_check import disconnected_nodes_subgraph
from dave_core.progressbar import create_tqdm_dask
from dave_core.settings import dave_settings


def split_line(line, nodes):
    """
    This function splits a single line by nodes

    INPUT:
        **line** (Shapely LineString) - geometry of a single line
        **nodes** (GeoDataFrame) - possible nodes where to split lines

    OUTPUT:
        **line_splited** (GeoDataFrame) - line splitted at given nodes
    """
    # check if road crosses network node => road need to split
    points_split = nodes[nodes.geometry.within(line.buffer(1e-3))]
    if not points_split.empty:
        # filter points which are endings of the line itself
        points_split = points_split[points_split.distance(Point(line.coords[:][0])) > 1e-3]
        points_split = points_split[points_split.distance(Point(line.coords[:][-1])) > 1e-3]
        # use snap function to snap points_split on line to avoid float point failure at split function
        result = split(
            snap(line, MultiPoint(points_split.geometry.values), tolerance=1e-3),
            MultiPoint(points_split.geometry.values),
        )
        line_splited = list(result.geoms)
    else:
        line_splited = [line]
    return line_splited


def split_lines(lines, nodes):
    """
    This function splits a set of lines by nodes

    INPUT:
        **lines** (GeoDataFrame) - all lines which should be considered
        **nodes** (GeoDataFrame) - possible nodes where to split lines

    OUTPUT:
        **lines_splited** (GeoDataFrame) - lines splitted at given nodes
    """
    # split each line at given nodes
    lines_splited = []
    lines_geom_dask = from_geopandas(lines.geometry, npartitions=dave_settings["cpu_number"])
    with create_tqdm_dask(desc="split lines", bar_type="sub_bar"):
        lines_geom_dask.apply(
            lambda x: lines_splited.extend(split_line(x, nodes)), meta=lines_geom_dask
        ).compute()
    lines_splited = GeoDataFrame(geometry=lines_splited, crs=dave_settings["crs_main"])
    # calculate length
    lines_splited["length_km"] = lines_splited.geometry.apply(lambda x: x.length / 1000)
    return lines_splited


def search_end_point_id(line, nodes, considered_end):
    """
    This function searches the id for the line ending points from a dataset of
    nodes by checking the minimum distance. The distance has to be under 1e-8
    to make sure the point is close to the line ending

    INPUT:
        **line** (shapely LineString) - Geometry of a line
        **nodes** (GeoDataFrame) - existing nodes in network
        **considered_end** (str) - defines which end of the line should be \
            considered. Options: "from" and "to"

    OUTPUT:
        **node_id** (int) - id of the node
    """
    # define line endpoint
    con_end = {"from": 0, "to": -1}
    line_endpoint = Point(line.coords[con_end[considered_end]])
    # search suitable node and extract id
    nodes = nodes[nodes.geometry.within(line_endpoint.buffer(1e-3))]
    if len(nodes.index) > 0:
        line_endpoint_id = nodes.index[0]
    else:
        line_endpoint_id = None
    return line_endpoint_id


def add_nodes_to_lines(nodes, lines_existing):
    """
    This function adds nodes into an existing line network. Existing lines will
    be splited and the nodes will be integrated and connected

    INPUT:
        **nodes** (GeoDataFrame) - nodes which should be implemented in the \
            existing line network
        **lines_existing** (GeoDataFrame) - existing line network

    OUTPUT:
        **lines_splited** (GeoDataFrame) - splitted line network
    """
    # split existing lines at nodes
    lines_splited = split_lines(lines_existing, nodes)
    # search road ending point ids
    lines_splited.reset_index(drop=True, inplace=True)
    # search node ids for line endpoints
    lines_splited_dask = from_geopandas(
        lines_splited.geometry, npartitions=dave_settings["cpu_number"]
    )
    with create_tqdm_dask(desc="search node ids from", bar_type="sub_bar"):
        lines_splited["from_bus"] = lines_splited_dask.apply(
            lambda x: search_end_point_id(x, nodes, considered_end="from"),
            meta=lines_splited_dask,
        ).compute()
    with create_tqdm_dask(desc="search node ids to", bar_type="sub_bar"):
        lines_splited["to_bus"] = lines_splited_dask.apply(
            lambda x: search_end_point_id(x, nodes, considered_end="to"),
            meta=lines_splited_dask,
        ).compute()
    # add internal parameters
    lines_splited["line_type"] = "line_connection"
    lines_splited["source"] = "dave_internal"
    return lines_splited


def build_steiner_tree(nodes, terminal_nodes, edges):
    """
    This function builds a steiner tree to connect nodes via edges.

    INPUT:
        **nodes** (GeoDataFrame) - all nodes which can be considered (including auxillary nodes like road junctions)
        **terminal_nodes** (list) - List of nodes which should be connected via steiner tree
        **edges** (GeoDataFrame) - List of lines which should be connected via steiner tree

    OUTPUT:
        **subgraph_nodes** (list) - resulting nodes from steiner tree
        **subgraph_edges** (list) - resulting edges from steiner tree

    """
    # filter disconnected nodes and edges  # TODO: Ist bisher noch ein Test, schauen ob man das wirklich so machen kann
    # nodes_disconnected = disconnected_nodes(nodes, edges, min_number_nodes=20)
    nodes_disconnected = disconnected_nodes_subgraph(nodes, edges, terminal_nodes)
    nodes = nodes[
        ~nodes.index.isin(nodes_disconnected)
    ]  # TODO: Hier ist das Problem bei steiner tree
    edges = edges[~edges.from_bus.isin(list(nodes_disconnected))]
    edges = edges[~edges.to_bus.isin(list(nodes_disconnected))]

    # create graph
    graph = create_graph(nodes, edges, "length_km")

    # calculate steiner tree
    subgraph = steiner_tree(
        G=graph,
        terminal_nodes=terminal_nodes,
        weight="weight",
        method="mehlhorn",
    )

    return list(subgraph.nodes), list(subgraph.edges)


def run_steiner_tree(nodes, terminal_nodes, edges, net_group=None):
    """
    This function runs the steiner tree heuristic for given nodes and edges

    INPUT:
        **nodes** (GeoDataFrame) - all possible nodes
        **terminal_nodes** (list) - list of nodes which should be connected
        **edges** (GeoDataFrame) - all possible edges

    OPTIONAL:
        **net_group** (int, default None) - number of the suitable net group

    OUTPUT:
        **nodes_res** (GeoDataFrame) - resulting nodes for steiner tree
        **edges_res** (GeoDataFrame) - resulting edges for steiner tree
    """
    # run steiner tree heuristic
    nodes_stein, edges_stein = build_steiner_tree(nodes, terminal_nodes, edges)
    nodes_res = nodes.filter(nodes_stein, axis=0)
    if net_group is not None:
        nodes_res["net_group"] = net_group
    edges_res = edges[
        edges.apply(
            lambda x: (
                True
                if (x.from_bus, x.to_bus) in (edges_stein)
                or (x.to_bus, x.from_bus) in (edges_stein)
                else False
            ),
            axis=1,
        )
    ]
    if net_group:
        edges_res["net_group"] = net_group
    return nodes_res, edges_res


def run_steiner_tree_net_group(grid_data, net_group, terminal_nodes, nodes, edges):
    """
    This function runs steiner tree heuristik for one net group.

    INPUT:
        **grid_data** (attrdict) - all Informations about the grid
        **net_group** (Series) - information about one net group
        **terminal_nodes** (GeoDataFrame) - nodes which should be connected
        **nodes** (GeoDataFrame) - all possible nodes for steiner tree
        **edges** (GeoDataFrame) - all possible edges for steiner tree

    OUTPUT:
        Writes node and line results from steiner tree run into DAVE dataset
    """
    net_group_fail = None
    # define relevant area to reduce nodes and edges
    area_rel = net_group.geometry.buffer(1e03)
    # define terminal nodes including building nodes and substation
    terminal_nodes = terminal_nodes[
        terminal_nodes.net_group == net_group.net_group
    ].node_idx.to_list()
    terminal_nodes.extend(nodes[nodes.dave_name == net_group.dave_name].index.to_list())
    # filter duplicates
    terminal_nodes = list(set(terminal_nodes))
    # run steiner tree
    if len(terminal_nodes) > 1:  # check if not only the substation is a relevant node
        try:
            nodes_res, edges_res = run_steiner_tree(
                nodes[nodes.geometry.within(area_rel)],
                terminal_nodes,
                edges[edges.within(area_rel)],
                net_group.net_group,
            )
            grid_data.lv_data.lv_nodes = concat([grid_data.lv_data.lv_nodes, nodes_res])
            grid_data.lv_data.lv_lines = concat([grid_data.lv_data.lv_lines, edges_res])
        except:  # noqa: E722
            net_group_fail = net_group.net_group
    elif len(terminal_nodes) == 1 and nodes.loc[terminal_nodes[0]].node_type == "mvlv_substation":
        # chek if only the substation is a terminal node. In this case the substation will be deleted
        trafo_idx = grid_data.components_power.transformers.mv_lv[
            grid_data.components_power.transformers.mv_lv.bus_lv
            == nodes.loc[terminal_nodes[0]].dave_name
        ].index[0]
        print(
            f"The transformer {trafo_idx} will be deleted because of none terminal nodes that will feed from it"
        )
        grid_data.components_power.transformers.mv_lv.drop([trafo_idx], inplace=True)

        # TODO: passende substations auch löschen
    return net_group_fail


def create_subgraphs(nodes, edges):
    """
    This function creates subgraphs by checking connected elements
    """
    # create empty graph
    graph = Graph()
    # create nodes
    graph.add_nodes_from(nodes.index.to_list())
    # create edges
    for _, edge in edges.iterrows():
        graph.add_edge(edge["from_node"], edge["to_node"], weight=edge["length_km"])
    # generate subgraphs
    subgraphs = list(connected_components(graph))
    return subgraphs
