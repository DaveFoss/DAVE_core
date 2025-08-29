# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from dask_geopandas import from_geopandas
from shapely import union_all
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
