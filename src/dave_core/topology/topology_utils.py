# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from dask_geopandas import from_geopandas
from geopandas import GeoDataFrame
from shapely.geometry import MultiPoint
from shapely.geometry import Point
from shapely.ops import snap
from shapely.ops import split

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
    points_split = nodes[nodes.geometry.within(line.buffer(1e-8))]
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
    nodes = nodes[nodes.geometry.within(line_endpoint.buffer(1e-8))]
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
