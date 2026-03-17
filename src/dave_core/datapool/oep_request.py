# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from time import sleep

from geopandas import GeoDataFrame
from pandas import DataFrame
from requests import get
from shapely.geometry import Point
from shapely.wkb import loads

from dave_core.settings import dave_settings

oep_url = "https://openenergyplatform.org"


def request_to_df(request):
    """
    This function converts requested data into a DataFrame
    """
    if request.status_code == 200:  # 200 is the code of a successful request
        # if request is empty their will be an JSONDecodeError
        try:
            request_df = DataFrame(request.json())
        except Exception:
            request_df = DataFrame()
    else:
        request_df = DataFrame()
    return request_df


def data_request(schema, table, where):
    # request data from OEP
    while 1:
        try:
            request = get(
                "".join(
                    [
                        oep_url,
                        "/api/v0/schema/",
                        schema,
                        "/tables/",
                        table,
                        "/rows/?where=" if where is not None else "/rows/",
                        where if where is not None else "",
                    ]
                ),
                timeout=600,
                verify=False,
            )
            break
        except ConnectionError:
            # add time delay
            sleep(dave_settings["osm_time_delay"])
    # request meta information from OEP
    meta_request = get(
        "".join([oep_url, "/api/v0/schema/", schema, "/tables/", table, "/meta/"]),
        timeout=180,
        verify=False,
    )
    return request, meta_request


def oep_request(table, schema=None, where=None, geometry=None):
    """
    This function is to requesting data from the open energy platform.\
    The available data is to find on https://openenergy-platform.org/dataedit/schemas

    INPUT:
        **table** (string) - table name of the searched data

    OPTIONAL:
        **schema** (string, default None) - schema name of the searched data. By default DAVE \
            search for the schema in the settings file via table name example: 'postcode=34225'
        **where** (string, default None) - filter the table of the searched \
            data. example: 'postcode=34225'
        **geometry** (string, default None) - name of the geometry parameter in the OEP dataset to \
            transform it from WKB to WKT

    OUTPUT:
        **requested_data** (DataFrame) - table of the requested data
    """

    if schema is None:
        schema = dave_settings["oep_tables"][table][0]
    # request data directly from oep
    if where is None and dave_settings["oep_tables"][table][2] is not None:
        request, meta_request = data_request(schema, table, dave_settings["oep_tables"][table][2])
    else:
        request, meta_request = data_request(schema, table, where)
    # convert data to dataframe
    request_data = request_to_df(request)
    # check for geometry parameter
    if geometry is None:
        geometry = dave_settings["oep_tables"][table][1]
    if geometry is not None:
        # --- convert into geopandas DataFrame with right crs
        # transform WKB to WKT / Geometry
        request_data["geometry"] = request_data[geometry].apply(lambda x: loads(x, hex=True))
        # create geoDataFrame
        request_data = GeoDataFrame(
            request_data,
            crs=dave_settings["crs_main"],
            geometry=request_data.geometry,
        )
    # fix some mistakes in the oep data
    if table == "ego_pf_hv_transformer":
        # change geometry to point because in original data the geometry was lines with length 0
        request_data["geometry"] = request_data.geometry.apply(
            lambda x: Point(x.geoms[0].coords[:][0][0], x.geoms[0].coords[:][0][1])
        )
    if table == "ego_dp_mvlv_substation":
        # change wrong crs from oep
        request_data.crs = dave_settings["crs_meter"]
        request_data = request_data.to_crs(dave_settings["crs_main"])

    # convert meta data to meta dict
    if meta_request.status_code == 200:  # 200 is the code of a successful request
        request_meta = meta_request.json()
        # create dict
        meta_data = {
            "Main": DataFrame(
                {
                    "Titel": request_meta["title"],
                    "Description": request_meta["description"],
                    "Spatial": request_meta["resources"][0]["spatial"],
                    "Licenses": request_meta["metaMetadata"]["metadataLicense"],
                    "metadata_version": request_meta["metaMetadata"]["metadataVersion"],
                },
                index=[0],
            ),
            "Sources": DataFrame(request_meta["resources"][0]["sources"]),
            "Data": DataFrame(request_meta["resources"][0]["schema"]["fields"]),
        }
    else:
        meta_data = {}
    return request_data, meta_data
