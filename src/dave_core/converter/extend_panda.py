from json import dumps

from geopandas import GeoDataFrame, GeoSeries
from pandapipes import pandapipesNet
from pandapipes import toolbox as ppi_toolbox
from pandapower import toolbox as pp_toolbox
from pandapower.auxiliary import pandapowerNet
from pandapower.io_utils import PPJSONEncoder, isinstance_partial
from pandas import concat
from shapely.geometry import LineString, Point
from shapely.ops import linemerge

from dave_core.create import create_grid


def get_grid_area(net, buffer=10, crs="epsg:4326", convex_hull=True):
    """
    Calculation of the grid area on the basis of an pandapower / pandapipes \
    model and the inclusion of a buffer.\n
    The crs will temporary project to epsg 3035 for adding the buffer in meter \
    as unit

    Input:
         **net** (pandapower/pandapipes net) - A energy grid in pandapower or \
             pandapipes format \n
         **buffer** (float, 10) - Buffer around the considered network \
             elements in meter \n
         **crs** (str, 'epsg:4326') - Definition of the network coordinate \
             reference system \n
         **convex_hull** (boolean, True)- If true the the convex hull will \
             calculated for the given lines instaed of onyly using a buffer \
             around the lines \n

    OUTPUT:
         **grid_area** (Shapely polygon) - Polygon which defines the grid area \
             for a given network

    """
    # define grid area by calculating the convexx hull for the lines/pipes
    if isinstance(net, pandapowerNet):
        grid_lines = GeoDataFrame(
            net.line, geometry=net.line_geodata.coords.apply(lambda x: LineString(x)), crs=crs
        )
    if isinstance(net, pandapipesNet):
        grid_lines = GeoDataFrame(
            net.pipe, geometry=net.pipe_geodata.coords.apply(lambda x: LineString(x)), crs=crs
        )  # 'epsg:23032'
    # change crs for using meter as unit
    if crs != "epsg:3035":
        grid_lines.to_crs(crs="epsg:3035", inplace=True)
    # define considered area
    if convex_hull:
        grid_area = grid_lines.geometry.unary_union.convex_hull
        # add buffer to the grid_area polygon
        grid_area_buffer = grid_area.buffer(buffer)
        grid_area_buffer = GeoSeries([grid_area_buffer], crs="epsg:3035")
        grid_area_buffer = grid_area_buffer.to_crs(crs=crs)
    else:
        # Create MultiLineString from Lines and merge them
        lines_merged = linemerge(grid_lines.geometry.to_list())
        grid_area = GeoSeries(lines_merged, crs="epsg:3035")
        # add buffer to the grid_area polygon
        grid_area_buffer = grid_area.buffer(buffer)
        grid_area_buffer = grid_area_buffer.to_crs(crs=crs)
    return grid_area_buffer.iloc[0]


def reduce_network(net, area, cross_border=True, crs="epsg:4326"):
    """
    Reduce a pandapower/pandapipes network to a smaller area of interest

    Input:
         **net** (pandapower/pandapipes net) - A energy grid in pandapower or \
             pandapipes format \n
         **area** (shapely Polygon) - Polygon of the considered network area \n
         **cross_border** (bool, default True) - Definition how to deal with \
             lines that going beyond the area border. If True these lines will \
             considered and their associated nodes outside the area border as \
             well. If False these lines will deleted and all network elements \
             are within the area border \n
         **crs** (str, default: 'epsg:4326') - Definition of the network \
             coordinate reference system \n

    OUTPUT:
         **net** (pandapower/pandapipes net) - network reduced to considered area
    """
    # TODO: Check if net and area are in the same crs. Otherwise change area crs to the net one

    if isinstance(net, pandapowerNet):
        if cross_border:
            # check lines which not intersecting with area
            lines = GeoDataFrame(
                net.line, geometry=net.line_geodata.coords.apply(lambda x: LineString(x)), crs=crs
            )
            lines_in = lines[lines.geometry.intersects(area)]
            buses_in_idx = set(concat([lines_in.from_bus, lines_in.to_bus]))
            buses_out_idx = list(set(net.bus.index) - buses_in_idx)
        else:
            # check buses which not intersecting with area
            buses = GeoDataFrame(
                net.bus, geometry=net.bus_geodata.apply(lambda x: Point(x), axis=1), crs=crs
            )
            buses_out_idx = buses[~buses.geometry.intersects(area)].index
        pp_toolbox.drop_buses(net, buses_out_idx, drop_elements=True)
    if isinstance(net, pandapipesNet):
        if cross_border:
            # check pipes which not intersecting with area
            pipes = GeoDataFrame(
                net.pipe, geometry=net.pipe_geodata.coords.apply(lambda x: LineString(x)), crs=crs
            )
            pipes_in = pipes[pipes.geometry.intersects(area)]
            junctions_in_idx = set(concat([pipes_in.from_junction, pipes_in.to_junction]))
            junctions_out_idx = list(set(net.junction.index) - junctions_in_idx)
        else:
            # check buses which not intersecting with area
            junctions = GeoDataFrame(
                net.junction,
                geometry=net.junction_geodata.apply(lambda x: Point(x), axis=1),
                crs=crs,
            )
            junctions_out_idx = junctions[~junctions.geometry.intersects(area)].index
        ppi_toolbox.drop_junctions(net, junctions_out_idx, drop_elements=True)
    return net


def request_geo_data(grid_area, crs, save_data=True):
    """
    This function requests all available geodata for a given area from DAVE.

    Input:
         **grid_area** (Shapely polygon) - Polygon which defines the considered grid area \n
         **crs** (str, default: 'epsg:4326') - Definition of the network \
             coordinate reference system \n
    
    OPTIONAL:
         **save_data** (boolean, default True) - if true, the resulting data will stored in a \
             local folder

    OUTPUT:
         **request_geodata** (pandapower net) - geodata for the grid_area from DAVE
    """
    if crs != "epsg:4326":
        # adjusted grid_area polygon to work with the DAVE main function, projection to 4326
        grid_area = GeoDataFrame({"name": ["own area"], "geometry": [grid_area]}, crs=crs)
        grid_area.to_crs(crs="epsg:4326", inplace=True)
        grid_area = grid_area.iloc[0].geometry
    # request geodata from DAVE
    _, net = create_grid(
        own_area=grid_area, geodata=["ALL"], convert_power=["pandapower"], save_data=save_data
    )
    # TODO: convert pandapower oder pandapipes jenachdem was abgefragt wird
    return net


def add_geodata(net, buffer=10, crs="epsg:4326", save_data=True):
    """
    This function extends a pandapower/pandapipes net with geodata from DAVE
    
    INPUT:
        **net** (pandapower net) - A pandapower network \n
        **dave_user** (str) - User name of a DAVE Account \n
        **dave_password** (str) - Password of a DAVE Account \n
    
    OPTIONAL:
        **buffer** (float) - Buffer around the considered network elements
         **crs** (str, default: 'epsg:4326') - Definition of the network coordinate reference \
             system \n
        **save_data** (boolean, default True) - if true, the resulting data will stored in a \
            local folder

    OUTPUT:
         **net** (pandapower/pandapipes net) - pandapower net extended with geodata
    """
    # get area polygon for the network
    area = get_grid_area(net, buffer=buffer, crs=crs)
    # request all available geodata for a given area from DAVE
    net_geodata = request_geo_data(area, crs, save_data)
    # extend net with geodata
    for typ in ["buildings", "roads", "railways", "landuse", "waterways"]:
        if typ in net_geodata.keys():
            if crs != "epsg:4326":
                # projection to original crs
                net[typ] = net_geodata[typ].to_crs(crs=crs, inplace=True)
            else:
                net[typ] = net_geodata[typ]
    return net
