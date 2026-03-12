# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from dask_geopandas import from_geopandas
from geopandas import GeoDataFrame
from geopandas import GeoSeries
from pandas import concat
from shapely import union_all
from shapely.geometry import Point
from shapely.ops import nearest_points

from dave_core.progressbar import create_tqdm_dask
from dave_core.settings import dave_settings


def nearest_road_points(points, roads):
    """
    This function finds the shortest way between points (e.g. building centroids and a road

    INPUT:
        **points** (GeoDataSeries) - series of point geometrys
        **roads** (GeoSeries) - relevant road geometries

    OUTPUT:
        **near_points** (GeoSeries) - nearest points on road to given points

    """
    # create multistring of relevant roads and intersect radial lines with it
    multiline_roads = union_all(roads)
    # finding nearest connection between the building centroids and the roads
    points_dask = from_geopandas(points, npartitions=dave_settings["cpu_number"])
    with create_tqdm_dask(desc="Nearest building nodes", bar_type="sub_bar"):
        return points_dask.apply(
            lambda x: nearest_points(x, multiline_roads)[1], meta=points_dask
        ).compute()


def generate_road_endings(relevant_roads, nodes):
    """
    This function filters all road endings which do not correspond to given \
        nodes

    INPUT:
        **relevant_roads** (dict) - roads that should be considered
        **nodes** (dict) - existing nodes to avoid duplication

    OUTPUT:
        **road_endings_rel** (GeoDataFrame) - all relevant road endings
    """
    # extract roads ending points
    relevant_roads_dask = from_geopandas(
        relevant_roads.geometry, npartitions=dave_settings["cpu_number"]
    )
    roads_from_points = relevant_roads_dask.apply(
        lambda x: Point(x.coords[0]),
        meta=relevant_roads_dask,
    ).compute()
    roads_to_points = relevant_roads_dask.apply(
        lambda x: Point(x.coords[-1]),
        meta=relevant_roads_dask,
    ).compute()
    road_endings = GeoDataFrame(
        geometry=GeoSeries(concat([roads_from_points, roads_to_points], ignore_index=True))
    )
    # filter all road endings which are not close to existing nodes to avoid duplicates
    road_endings_dask = from_geopandas(
        road_endings.geometry, npartitions=dave_settings["cpu_number"]
    )
    nodes_buffer = nodes.buffer(1e-8).union_all()
    road_endings_near_nodes = road_endings_dask.apply(
        lambda x, nodes_buffer=nodes_buffer: x.within(nodes_buffer),
        meta=road_endings_dask,
    ).compute()
    road_endings_rel = road_endings[~road_endings_near_nodes]
    # adjust relevant data
    road_endings_rel.reset_index(drop=True, inplace=True)
    road_endings_rel["node_type"] = "road_ending"
    road_endings_rel["source"] = "dave internal"
    return road_endings_rel
