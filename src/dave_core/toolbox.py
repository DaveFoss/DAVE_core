# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details). All rights reserved.
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from os import path

from dask_geopandas import from_geopandas
from geopandas import GeoDataFrame
from geopandas import overlay
from geopy.geocoders import ArcGIS
from numpy import append
from numpy import array
from pandas import concat
from scipy.spatial import Voronoi
from shapely.geometry import LineString
from shapely.geometry import MultiLineString
from shapely.geometry import MultiPoint
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.ops import linemerge
from shapely.ops import polygonize

from dave_core.settings import dave_settings


def multiline_coords(line_geometry):
    """
    This function extracts the coordinates from a MultiLineString

    INPUT:
    **line_geometry** (Shapely MultiLinesString) - geometry in MultiLineString format

    OUTPUT:
        **line_coords** (list) - coordinates of the given MultiLineString
    """
    merged_line = linemerge(line_geometry)
    # sometimes line merge can not merge the lines correctly
    line_coords = []
    if isinstance(merged_line, MultiLineString):
        for line in list(merged_line.geoms):
            line_coords += line.coords[:]
    else:
        line_coords += merged_line.coords[:]
    return line_coords


def create_interim_area(areas):
    """
    This function creats a interim area to combine not connected areas.

    INPUT:
        **areas** (GeoDataFrame) - all considered grid areas

    OUTPUT:
        **areas** (GeoDataFrame) - all considered grid areas extended with interim areas
    """
    # check if there are diffrent grid areas
    if len(areas) > 1:
        # check for isolated areas
        areas_iso = []
        for i, area in areas.iterrows():
            # check if the considered area adjoining an other one
            areas_other = areas.drop([i])
            distance = areas_other.geometry.apply(lambda x, area=area: area.geometry.distance(x))
            if distance.min() > 0:
                areas_iso.append((i, distance.idxmin()))
        # if their are isolated areas, check for a connection on the highest grid level
        if len(areas_iso) > 0:
            for area_iso in areas_iso:
                # filter areas
                geom1 = areas.loc[area_iso[0]].geometry
                geom2 = areas.loc[area_iso[1]].geometry
                # define diffrence area
                combined = unary_union([geom1, geom2])
                convex_hull = combined.convex_hull
                difference = convex_hull.difference(geom1)
                difference = difference.difference(geom2)
                # add difference area to areas
                areas = concat(
                    [
                        areas,
                        GeoDataFrame({"name": "interim area", "geometry": [difference]}),
                    ],
                    ignore_index=True,
                )
    return areas


def voronoi(points, polygon_param=True):
    """
    This function calculates the voronoi diagram for given points

    INPUT:
        **points** (GeoDataFrame) - all nodes for voronoi analysis (centroids)
        **polygon_param** (bool, default True) - if True the centroid and dave name for each \
            voronoi polygon will be searched

    OUTPUT:
        **voronoi polygons** (GeoDataFrame) - all voronoi areas for the given points
    """
    # define points for voronoi centroids
    points = points.reset_index(drop=True)  # don't use inplace

    voronoi_centroids = [[point.x, point.y] for i, point in points.geometry.items()]
    voronoi_points = array(voronoi_centroids)
    # maximum points of the considered area define, which limit the voronoi polygons
    bound_points = MultiPoint(points.geometry).convex_hull.buffer(1).bounds
    points_boundary = [
        [bound_points[0], bound_points[1]],
        [bound_points[0], bound_points[3]],
        [bound_points[2], bound_points[1]],
        [bound_points[2], bound_points[3]],
    ]
    # append boundary points to avoid infinit polygons with relevant nodes
    voronoi_points = append(voronoi_points, points_boundary, axis=0)
    # carry out voronoi analysis
    vor = Voronoi(voronoi_points)
    # select finit lines and create LineStrings (regions with -1 are infinit)
    lines = [LineString(vor.vertices[line]) for line in vor.ridge_vertices if -1 not in line]
    # create polygons from the lines
    polygons = array(list(polygonize(lines)))
    # create GeoDataFrame with polygons
    voronoi_polygons = GeoDataFrame(geometry=polygons, crs=dave_settings["crs_main"])
    # search voronoi centroids and dave name
    if polygon_param:
        voronoi_polygons_geom_dask = from_geopandas(
            voronoi_polygons.geometry, npartitions=dave_settings["cpu_number"]
        )
        voronoi_polygons["centroid"] = voronoi_polygons_geom_dask.apply(
            lambda x: (
                points[points.within(x)].iloc[0].geometry
                if not points[points.within(x)].empty
                else "fail"
            ),
            meta=voronoi_polygons_geom_dask,
        ).compute()
        voronoi_polygons["dave_name"] = voronoi_polygons_geom_dask.apply(
            lambda x: (
                points[points.within(x)].iloc[0].dave_name
                if not points[points.within(x)].empty
                else "fail"
            ),
            meta=voronoi_polygons_geom_dask,
        ).compute()
    return voronoi_polygons


def adress_to_coords(adress, geolocator=None):
    """
    This function request geocoordinates to a given adress.

    INPUT:
        **Adress** (string) - format: street_name housenummber postal_code city
                              example: 'Königstor 59 34119 Kassel'

    OUTPUT:
        **geocoordinates** (tuple) - geocoordinates for the adress in format (longitude, latitude)
    """
    if not geolocator:
        geolocator = ArcGIS(timeout=None)
    if adress:
        location = geolocator.geocode(adress)
        return (location.longitude, location.latitude)


def get_data_path(filename=None, dirname=None):
    """
    This function returns the full os path for a given directory (and filename)
    """
    data_path = (
        path.join(dave_settings["dave_dir"], "datapool", dirname, filename)
        if filename
        else path.join(dave_settings["dave_dir"], "datapool", dirname)
    )
    return data_path


def intersection_with_area(gdf, area, remove_columns=True, only_limit=True):
    """
    This function intersects a given geodataframe with an area in consideration \
        of mixed geometry types at both input variables
    INPUT:
        **gdf** (GeoDataFrame) - Data to be intersect with an area
        **area** (GeoDataFrame) - Considered Area
        **remove_columns** (bool, default True) - If True the area parameters \
            will deleted in the result
        **only_limit** (bool, default True) - If True it will only considered \
            if the data intersects the area instead of which part of the area \
            they intersect if the area is split in multiple polygons

    OUTPUT:
        **gdf_over** (GeoDataFrame) - Data which intersetcs with considered area
    """
    # reduce grid area geometries to one polygon
    if only_limit:
        area = GeoDataFrame(geometry=[area.geometry.unary_union], crs=dave_settings["crs_main"])
    # check if geodataframe has mixed geometries
    geom_types_gdf = set(map(type, gdf.geometry))
    geom_types_area = set(map(type, area.geometry))
    if len(geom_types_gdf) > 1:
        # in this case the geodataframe has mixed geometrie information. A seperated consideration
        # of overlay is necessary because the function can not handle mixed geometries
        gdf_over = GeoDataFrame([])
        for geom_type in geom_types_gdf:
            # get indeces for geom type
            gdf_geom_idx = [
                row.name for i, row in gdf.iterrows() if isinstance(row.geometry, (geom_type))
            ]
            # check for values in the target area
            gdf_over_geom = overlay(gdf.loc[gdf_geom_idx], area, how="intersection")
            gdf_over = concat([gdf_over, gdf_over_geom], ignore_index=True)
    elif len(geom_types_area) > 1:
        # in this case the geodataframe has mixed geometrie information. A seperated consideration
        # of overlay is necessary because the function can not handle mixed geometries
        gdf_over = GeoDataFrame([])
        for geom_type in geom_types_area:
            area_geom_idx = [
                row.name for i, row in area.iterrows() if isinstance(row.geometry, (geom_type))
            ]
            # check for values in the target area
            gdf_over_geom = overlay(gdf, area.loc[area_geom_idx], how="intersection")
            gdf_over = concat(
                [gdf_over, gdf_over_geom], ignore_index=True
            )  # TODO: Problem ist das es hier Population_1 und _2 gibt, daher wirft er einen Fehler
    else:
        gdf_over = overlay(gdf, area, how="intersection")
    # remove parameters from area
    if (not gdf_over.empty) and (remove_columns):
        remove_columns = area.keys().tolist()
        remove_columns.remove("geometry")
        gdf_over.drop(columns=remove_columns, inplace=True)
    return gdf_over


def intersect_with_composition(gdf1, gdf2, gdf1_name=None, area=None):
    """
    This function intersects two GeoDataFrames with each other and calculates the composition how gdf1 will splitted to gdf2

    Hint: gdf1 and gdf2 must have "name" and "geometry" parameters
    INPUT:
        **gdf1** (GeoDataFrame) - Area with polygons to divide
        **gdf2** (GeoDataFrame) - Area with polygons or nodes to which gdf1 should be divide

    OPTIONAL:
        **gdf1_name** (GeoDataFrame, default None) - Gdf1 parameter which includes the area name. \
            Per default the first column will taken
        **grid_area** (GeoDataFrame, default None) - definition of the consider area
    """
    # reduce data to considered area
    if area:
        gdf1 = intersection_with_area(gdf1, area)
        gdf2 = intersection_with_area(gdf2, area)
    # voronoi tesselation in case gdf2 is a dataset of points
    if isinstance(gdf2.geometry.iloc[0], Point):
        gdf2["geometry"] = voronoi(gdf2, polygon_param=False).geometry

    # define gdf1 name per default
    if not gdf1_name:
        gdf1_name = gdf1.keys()[0]
    if gdf1_name == "name":
        gdf1_name = "gdf1_name"
        gdf1.rename(columns={"name": gdf1_name}, inplace=True)
    # intersect data with voronoi regions
    gdf_intersect = overlay(gdf1, gdf2)  # !!! ggf. drop von centorid und dave_name an der stelle
    # replace "nan" because "nan" is not equals to nan
    gdf_intersect.fillna("None", inplace=True)
    # calculate area percentage
    gdf_intersect["area_percentage"] = gdf_intersect.geometry.area / gdf_intersect.apply(
        lambda x: gdf1[(gdf1[gdf1_name] == x[gdf1_name])].iloc[0].geometry.area,
        axis=1,
    )
    return gdf_intersect


def related_sub(bus, substations):
    """
    This function searches the related substation for a bus and returns some
    substation information

    INPUT:
        **bus** (Shapely Point) - bus geometry
        **substations** (DataFrame) - Table of the possible substations

    OUTPUT:
        (Tuple) - Substation information for a given bus (ego_subst_id, subst_dave_name, subst_name)
    """
    substation_geom_dask = from_geopandas(
        substations.geometry, npartitions=dave_settings["cpu_number"]
    )
    sub_filtered = substations[
        substation_geom_dask.apply(
            lambda x: (bus.within(x)) or (bus.distance(x) < 1e-05), meta=substation_geom_dask
        ).compute()
    ]
    ego_subst_id = sub_filtered.ego_subst_id.to_list() if not sub_filtered.empty else []
    subst_dave_name = sub_filtered.dave_name.to_list() if not sub_filtered.empty else []
    if "subst_name" in sub_filtered.keys():
        subst_name = sub_filtered.subst_name.to_list() if not sub_filtered.empty else []
    else:
        subst_name = "nan"
    return ego_subst_id, subst_dave_name, subst_name
