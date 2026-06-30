# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2026 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from dask_geopandas import from_geopandas
from geopandas import GeoDataFrame
from geopandas import GeoSeries
from pandas import concat
from shapely import union_all
from shapely.geometry import LineString
from shapely.geometry import Polygon

from dave_core.datapool.osm_request import osm_request
from dave_core.geography.geo_utils import generate_road_endings
from dave_core.model_utils import filter_isolated_edges
from dave_core.settings import dave_settings
from dave_core.toolbox import intersection_with_area
from dave_core.topology.topology_utils import add_nodes_to_lines


def get_osm_data(grid_data, key, border, target_geom):
    """
    This function requests data from osm and filter it

    INPUT:

        **grid_data** (string) - DAVE data dictionary
        **key** (string) - name of the object type which should be considered
        **border** (geometrie) - border for the data consideration
        **target_geom** (geometrie) - geometry of the considerd target
    """
    data, meta_data = osm_request(data_type=key, area=border)
    # add meta data
    if f"{meta_data['Main'].Titel.loc[0]}" not in grid_data.meta_data.keys():
        grid_data.meta_data[f"{meta_data['Main'].Titel.loc[0]}"] = meta_data
    # check if there are data
    if not data.empty:
        # filter data parameters which are relevant for the grid modeling
        data = data.filter(dave_settings["osm_tags"][key][3])
        data.rename(columns={"id": "osm_id"}, inplace=True)
        # consider only data which are linestring elements and within considered area
        data_dask = from_geopandas(data.geometry, npartitions=dave_settings["cpu_number"])
        data = data[
            (data_dask.apply(lambda x: isinstance(x, LineString), meta=data_dask).compute())
            & (data_dask.intersects(target_geom).compute())
        ]
        data.set_crs(dave_settings["crs_degree"], inplace=True)
        data.to_crs(dave_settings["crs_main"], inplace=True)
    return data


def calculate_road_junctions(roads):
    """
    This function searches junctions for the relevant roads in the target area
    """
    if not roads.empty:
        junction_points = []
        while len(roads) > 1:
            # considered line
            line_geometry = roads.iloc[0].geometry
            # check considered line surrounding for possible intersectionpoints with other lines
            lines_cross = roads[roads.geometry.crosses(line_geometry.buffer(1))]
            if not lines_cross.empty:
                # find line intersections between considered line and other lines
                line_junctions = line_geometry.intersection(lines_cross.geometry.unary_union)
                if line_junctions.geom_type == "Point":
                    junction_points.append(line_junctions)
                elif line_junctions.geom_type == "MultiPoint":
                    for point in line_junctions.geoms:
                        junction_points.append(point)
            # set new roads quantity for the next iterationstep
            roads = roads.iloc[1:, :]
            roads.reset_index(drop=True, inplace=True)
        # delet duplicates
        junctions = GeoSeries(junction_points).drop_duplicates()
        # write road junctions into grid_data
        road_junctions = GeoDataFrame(
            {
                "node_type": "road_junction",
                "source": "dave internal",
                "geometry": junctions,
            },
            crs=dave_settings["crs_main"],
        )
        return road_junctions


def road_processing(grid_data, roads):
    # filter relevant roads
    roads_highway_dask = from_geopandas(
        roads.highway,
        npartitions=dave_settings["cpu_number"],
    )
    roads_relevant = roads[roads_highway_dask.isin(dave_settings["roads_relevant"]).compute()]

    # calculate road junctions for relevant roads
    road_junctions = calculate_road_junctions(roads_relevant)
    grid_data.road_data.road_junctions = concat(
        [grid_data.road_data.road_junctions, road_junctions], ignore_index=True
    )
    grid_data.road_data.road_junctions.set_geometry("geometry", inplace=True)

    # calculate road endings wich are not coresspond to a rodad junction
    road_endings = generate_road_endings(roads_relevant, road_junctions)
    grid_data.road_data.road_endings = concat(
        [grid_data.road_data.road_endings, road_endings], ignore_index=True
    )
    grid_data.road_data.road_endings.set_geometry("geometry", inplace=True)
    # add road junctions and road endings to road network
    nodes = concat([road_junctions, road_endings])
    nodes.reset_index(drop=True, inplace=True)
    roads_splited = add_nodes_to_lines(nodes, lines_existing=roads_relevant)
    # search and filter isolated roads
    roads_relevant = filter_isolated_edges(roads_splited, nodes)
    grid_data.road_data.roads = concat(
        [grid_data.road_data.roads, roads_relevant], ignore_index=True
    )


def landuse_processing(grid_data, landuse):
    # filter landuses with geometry given as point or LineString with less than 3 coords
    landuse = landuse[
        landuse.geometry.apply(lambda x: isinstance(x, LineString) and len(x.coords[:]) >= 3)
    ]
    # convert geometry to polygon
    landuse["geometry"] = landuse.geometry.apply(lambda x: Polygon(x))

    # intersect landuses with the target area
    area = grid_data.area.rename(columns={"name": "bundesland"})
    # filter landuses which are within the grid area
    landuse = intersection_with_area(landuse, area)  # !!! duplicated with intersection before?
    # calculate polygon area in km²
    landuse["area_km2"] = landuse.area / 1e06
    # write landuse into grid_data
    grid_data.landuse = concat([grid_data.landuse, landuse], ignore_index=True)


def improve_building_tag(
    building_origin, building_geo, landuse_retail, landuse_industrial, landuse_commercial
):
    if landuse_retail is not None and building_geo.intersects(landuse_retail):
        building_type = "retail"
    elif landuse_industrial is not None and building_geo.intersects(landuse_industrial):
        building_type = "industrial"
    elif landuse_commercial is not None and building_geo.intersects(landuse_commercial):
        building_type = "commercial"
    else:
        building_type = building_origin
    return building_type


def building_processing(grid_data, buildings, landuse):
    # create building categories
    residential = dave_settings["buildings_residential"]
    commercial = dave_settings["buildings_commercial"]
    # improve building tag with landuse parameter
    if landuse if isinstance(landuse, bool) else not landuse.empty:
        landuse_retail = union_all(landuse[landuse.landuse == "retail"].geometry)
        landuse_industrial = union_all(landuse[landuse.landuse == "industrial"].geometry)
        landuse_commercial = union_all(landuse[landuse.landuse == "commercial"].geometry)
        buildings_dask = from_geopandas(buildings, npartitions=dave_settings["cpu_number"])
        buildings["building"] = buildings_dask.apply(
            lambda x: (
                improve_building_tag(
                    x.building, x.geometry, landuse_retail, landuse_industrial, landuse_commercial
                )
                if x.building not in commercial
                else x.building
            ),
            axis=1,
            meta=buildings_dask,
        ).compute()

    # write buildings into grid_data
    grid_data.buildings.residential = concat(
        [
            grid_data.buildings.residential,
            buildings[buildings.building.isin(residential)],
        ],
        ignore_index=True,
    )
    grid_data.buildings.commercial = concat(
        [
            grid_data.buildings.commercial,
            buildings[buildings.building.isin(commercial)],
        ],
        ignore_index=True,
    )
    grid_data.buildings.other = concat(
        [
            grid_data.buildings.other,
            buildings[~buildings.building.isin(residential + commercial)],
        ],
        ignore_index=True,
    )


def from_osm(
    grid_data,
    pbar,
    roads,
    buildings,
    landuse,
    railways,
    waterways,
    target_geom,
    progress_step=None,
):
    """
    This function searches for data on OpenStreetMap (OSM) and filters the relevant paramerters
    for grid modeling

    target = geometry of the considerd target
    """
    # count object types to consider for progress bar
    objects_list = [roads, buildings, landuse, railways, waterways]
    objects_con = len([x for x in objects_list if x is True])
    if objects_con == 0:
        # update progress
        pbar.update(progress_step)
    # add a buffer to target to get a bigger view for some geographical informations
    target_geom_buff = target_geom.buffer(dave_settings["osm_area_buffer"])
    # create border for osm query
    border = target_geom.convex_hull
    border_buffer = target_geom_buff.convex_hull
    # search relevant road informations in the target area
    if roads:
        # collect road data from osm
        roads = get_osm_data(grid_data, "road", border_buffer, target_geom_buff)
        if not roads.empty:
            road_processing(grid_data, roads)
        # update progress
        pbar.update(progress_step / objects_con)
    # search landuse informations in the target area
    if landuse:
        # request landuse information
        landuse = get_osm_data(grid_data, "landuse", border_buffer, target_geom_buff)
        # request some leisure place information which are relevant as landuse area
        leisure = get_osm_data(grid_data, "leisure", border_buffer, target_geom_buff)
        # request some natural place information which are relevant as landuse area
        natural = get_osm_data(
            grid_data, "natural", border.buffer(dave_settings["osm_area_buffer"]), target_geom
        )  # !!! Fehler landuse attribute
        # natural parameter in landuse umbenennen und zu landuse hinzufügen?
        landuse = concat([landuse, leisure, natural], ignore_index=True)
        # check if there are data for landuse
        if not landuse.empty:
            landuse_processing(grid_data, landuse)
        # update progress
        pbar.update(progress_step / objects_con)
    # search building informations in the target area
    if buildings:
        buildings = get_osm_data(grid_data, "building", border, target_geom)
        # check if there are data for buildings
        if not buildings.empty:
            building_processing(grid_data, buildings, landuse)
        # update progress
        pbar.update(progress_step / objects_con)
    # search railway informations in the target area
    if railways:
        railways = get_osm_data(grid_data, "railway", border_buffer, target_geom_buff)
        grid_data.railways = concat([grid_data.railways, railways], ignore_index=True)
        # update progress
        pbar.update(progress_step / objects_con)
    # search waterway informations in the target area
    if waterways:
        waterways = get_osm_data(grid_data, "waterway", border_buffer, target_geom_buff)
        grid_data.waterways = concat([grid_data.waterways, waterways], ignore_index=True)
        # update progress
        pbar.update(progress_step / objects_con)
