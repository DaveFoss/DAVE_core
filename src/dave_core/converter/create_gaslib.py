# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details). All rights reserved.
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

from copy import copy

from lxml import etree

from dave_core.converter.read_gaslib import read_gaslib_cs
from dave_core.progressbar import create_tqdm
from dave_core.settings import dave_settings


def create_gaslib(grid_data, output_folder, save_data=True):
    """
    This function creates a network in gaslib format based of an DAVE dataset

    INPUT:
        **grid_data** (attrdict) - calculated grid data from DAVE
        **output_folder** (str) - patht to the location where the results will be saved

    OPTIONAL:
        **save_data** (boolean, default True) - if true, the resulting data will stored in a \
            local folder

    """
    # set progress bar
    pbar = create_tqdm(desc="create gaslib model")

    # define network
    nsm = {
        None: "http://gaslib.zib.de/Gas",
        "framework": "http://gaslib.zib.de/Framework",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    network = etree.Element("network", nsmap=nsm)
    network.attrib[
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
    ] = "http://gaslib.zib.de/Gas Gas.xsd"
    information = etree.Element("{http://gaslib.zib.de/Framework}information")
    nodes = etree.Element("{http://gaslib.zib.de/Framework}nodes")
    connections = etree.Element("{http://gaslib.zib.de/Framework}connections")

    # import gaslib cs file for compressor station reference
    gaslib_cs_data, gaslib_data_cs_xml = read_gaslib_cs()

    # define cs file
    nsm = {
        None: "http://gaslib.zib.de/CompressorStations",
        "framework": "http://gaslib.zib.de/CompressorStations",
        "gas": "http://gaslib.zib.de/Gas",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    compressorStations = etree.Element("compressorStations", nsmap=nsm)
    compressorStations.attrib[
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
    ] = "http://gaslib.zib.de/CompressorStations http://gaslib.zib.de/schema/CompressorStations.xsd"

    # --- create informations
    information.attrib["title"] = "Grid model generated by DaVe"
    # check diffrent area options
    area_type = grid_data.target_input.typ.iloc[0]
    if area_type in ["postalcode", "town name"]:
        area_data = grid_data.target_input.data.iloc[0]
    elif area_type == "federal state":
        area_data = grid_data.target_input.federal_states.iloc[0]
    elif area_type == "nuts region":
        area_data = grid_data.target_input.nuts_regions.iloc[0]
    elif area_type == "own area":
        area_data = "A user given shapefile defines the grid area"
    information.attrib["area"] = f"{area_type}: {area_data}"
    information.attrib["grid_levels"] = str(
        grid_data.target_input.gas_levels.iloc[0]
    )
    information.attrib["dave_version"] = dave_settings["dave_version"]

    # read data from dave dictionary
    nodes_dave = grid_data.hp_data.hp_junctions
    # set junctions external to the considered area to import and export to 1
    nodes_dave["is_import"] = nodes_dave.apply(
        lambda x: True if x.external is True else x.is_import, axis=1
    )
    nodes_dave["is_export"] = nodes_dave.apply(
        lambda x: True if x.external is True else x.is_export, axis=1
    )
    # nodes_dave_ext = nodes_dave[nodes_dave.external == True].dave_name.to_list()
    pipes_dave = grid_data.hp_data.hp_pipes
    compressors_dave = grid_data.components_gas.compressors
    sources_dave = grid_data.components_gas.sources
    sinks_dave = grid_data.components_gas.sinks
    # --- create nodes
    # set dict for mapping ids
    mapping = {}
    # Cases of export, import
    # Case 0,0 => in node (connection)
    # Case 0,1 => source
    # Case 1,0 => sink
    # Case 1,1 => source and sink
    for _, node in nodes_dave.iterrows():
        # derivate max pressure from connected lines
        node_max_pressure = pipes_dave[
            (pipes_dave.from_junction == node.dave_name)
            | (pipes_dave.to_junction == node.dave_name)
        ].max_pressure_bar.min()
        if node.is_export == node.is_import:
            innode = etree.Element("innode", {"alias": "", "y": "", "x": ""})
            innode.attrib["geoWGS84Long"] = str(node.long)
            innode.attrib["geoWGS84Lat"] = str(node.lat)
            innode_id = f"innode_{node.dave_name}"
            innode.attrib["id"] = innode_id
            mapping[node.dave_name] = innode_id
            etree.SubElement(
                innode, "height", {"unit": "m", "value": str(node.height_m)}
            )
            etree.SubElement(
                innode, "presssureMin", {"unit": "bar", "value": "1.0"}
            )  # !!! Annahme
            etree.SubElement(
                innode,
                "presssureMax",
                {"unit": "bar", "value": str(node_max_pressure)},
            )
            nodes.append(innode)

        if (not node.is_export and node.is_import) or (
            node.is_export and node.is_import
        ):
            source = etree.Element("source", {"alias": "", "y": "", "x": ""})
            source.attrib["geoWGS84Long"] = str(node.long)
            source.attrib["geoWGS84Lat"] = str(node.lat)
            source_id = f"source_{node.dave_name}"
            source.attrib["id"] = source_id
            mapping[node.dave_name] = source_id
            etree.SubElement(
                source, "height", {"unit": "m", "value": str(node.height_m)}
            )
            etree.SubElement(
                source, "presssureMin", {"unit": "bar", "value": "1.0"}
            )  # !!! Annahme
            etree.SubElement(
                source,
                "presssureMax",
                {"unit": "bar", "value": str(node_max_pressure)},
            )
            etree.SubElement(
                source,
                "flowMin",
                {"unit": "1000m_cube_per_hour", "value": "0"},
            )  # !!! annahme
            # get flow max value from soure data or calculate from pipes for external nodes
            if not node.is_export and node.is_import:
                source_dave = sources_dave[
                    sources_dave.junction == node.dave_name
                ].iloc[0]
                flow_max_source = str(
                    source_dave["max_supply_M_m3_per_d"] * 1000 / 24
                )
            elif node.is_export and node.is_import:
                source_pipes = pipes_dave[
                    (pipes_dave.from_junction == node.dave_name)
                    | (pipes_dave.to_junction == node.dave_name)
                ]
                flow_max_source = str(
                    source_pipes["max_cap_M_m3_per_d"].sum() * 1000 / 24
                )
            etree.SubElement(
                source,
                "flowMax",
                {"unit": "1000m_cube_per_hour", "value": flow_max_source},
            )
            etree.SubElement(
                source, "gasTemperature", {"unit": "Celsius", "value": "15"}
            )  # !!! annahme
            etree.SubElement(
                source,
                "calorificValue",
                {"unit": "MJ_per_m_cube", "value": "41.342270292"},
            )  # !!! annahme
            etree.SubElement(
                source,
                "normDensity",
                {"unit": "kg_per_m_cube", "value": "0.82"},
            )  # !!! annahme
            etree.SubElement(
                source, "coefficient-A-heatCapacity", {"value": "31.61010551"}
            )  # !!! annahme
            etree.SubElement(
                source,
                "coefficient-B-heatCapacity",
                {"value": "-0.004284754861"},
            )  # !!! annahme
            etree.SubElement(
                source, "coefficient-C-heatCapacity", {"value": "8.019089e-05"}
            )  # !!! annahme
            etree.SubElement(
                source,
                "molarMass",
                {"unit": "kg_per_kmol", "value": "18.0488790169"},
            )  # !!! annahme
            etree.SubElement(
                source,
                "pseudocticticalPressure",
                {"unit": "bar", "value": "46.7020607"},
            )  # !!! annahme
            etree.SubElement(
                source,
                "pseudocticticalTemperature",
                {"unit": "K", "value": "202.4395142"},
            )  # !!! annahme
            nodes.append(source)

        if (node.is_export and not node.is_import) or (
            node.is_export and node.is_import
        ):
            sink = etree.Element("sink", {"alias": "", "y": "", "x": ""})
            sink.attrib["geoWGS84Long"] = str(node.long)
            sink.attrib["geoWGS84Lat"] = str(node.lat)
            sink_id = f"sink_{node.dave_name}"
            sink.attrib["id"] = sink_id
            mapping[node.dave_name] = sink_id
            etree.SubElement(
                sink, "height", {"unit": "m", "value": str(node.height_m)}
            )
            etree.SubElement(
                sink, "presssureMin", {"unit": "bar", "value": "1.0"}
            )  # !!! Todos Robert schaut in Gaslib nach
            etree.SubElement(
                sink,
                "presssureMax",
                {"unit": "bar", "value": str(node_max_pressure)},
            )
            etree.SubElement(
                sink, "flowMin", {"unit": "1000m_cube_per_hour", "value": "0"}
            )  # !!! annahme
            # get flow max value from sink data or calculate from pipes for external nodes
            if node.is_export and not node.is_import:
                sink_dave = sinks_dave[
                    sinks_dave.junction == node.dave_name
                ].iloc[0]
                # overwrite flowMax assumption
                flow_max_sink = str(
                    sink_dave.max_demand_M_m3_per_d * 1000 / 24
                )
            elif node.is_export is True and node.is_import is True:
                sinks_pipes = pipes_dave[
                    (pipes_dave.from_junction == node.dave_name)
                    | (pipes_dave.to_junction == node.dave_name)
                ]
                flow_max_sink = str(
                    sinks_pipes["max_cap_M_m3_per_d"].sum() * 1000 / 24
                )
            etree.SubElement(
                sink,
                "flowMax",
                {"unit": "1000m_cube_per_hour", "value": flow_max_sink},
            )  # assumption but will overwritten at the sinks
            height = etree.Element("height")
            height.attrib["unit"] = "m"
            height.attrib["value"] = str(node.height_m)
            sink.append(height)
            nodes.append(sink)

        if node.is_export and node.is_import:
            # overwrite mapping entry
            mapping[node.dave_name] = [innode_id, source_id, sink_id]
            # get neighboring pipline to use their charakteristics
            pipe_neighbor = pipes_dave[
                (pipes_dave.from_junction == node.dave_name)
                | (pipes_dave.to_junction == node.dave_name)
            ].iloc[0]
            # create seperated lines for the sink and source
            short_pipe_sink = etree.Element("shortPipe")
            short_pipe_sink.attrib["alias"] = ""
            short_pipe_sink.attrib["id"] = f"short_pipe_{sink_id}_{innode_id}"
            short_pipe_sink.attrib["from"] = sink_id
            short_pipe_sink.attrib["to"] = innode_id
            etree.SubElement(
                short_pipe_sink,
                "flowMin",
                {
                    "unit": "1000m_cube_per_hour",
                    "value": str(
                        -pipe_neighbor.max_cap_M_m3_per_d * 1000 / 24
                    ),
                },
            )
            etree.SubElement(
                short_pipe_sink,
                "flowMax",
                {
                    "unit": "1000m_cube_per_hour",
                    "value": str(pipe_neighbor.max_cap_M_m3_per_d * 1000 / 24),
                },
            )
            connections.append(short_pipe_sink)
            short_pipe_source = etree.Element("shortPipe")
            short_pipe_source.attrib["alias"] = ""
            short_pipe_source.attrib["id"] = (
                f"short_pipe_{source_id}_{innode_id}"
            )
            short_pipe_source.attrib["from"] = source_id
            short_pipe_source.attrib["to"] = innode_id
            etree.SubElement(
                short_pipe_source,
                "flowMin",
                {
                    "unit": "1000m_cube_per_hour",
                    "value": str(
                        -pipe_neighbor.max_cap_M_m3_per_d * 1000 / 24
                    ),
                },
            )
            etree.SubElement(
                short_pipe_source,
                "flowMax",
                {
                    "unit": "1000m_cube_per_hour",
                    "value": str(pipe_neighbor.max_cap_M_m3_per_d * 1000 / 24),
                },
            )
            connections.append(short_pipe_source)

    # --- create connections
    # create pipes
    for _, pipe_dave in pipes_dave.iterrows():
        pipe = etree.Element("pipe")
        pipe.attrib["from"] = (
            mapping[pipe_dave.from_junction]
            if isinstance(mapping[pipe_dave.from_junction], str)
            else mapping[pipe_dave.from_junction][0]
        )
        pipe.attrib["to"] = (
            mapping[pipe_dave.to_junction]
            if isinstance(mapping[pipe_dave.to_junction], str)
            else mapping[pipe_dave.to_junction][0]
        )
        pipe.attrib["id"] = (
            f"pipe_{mapping[pipe_dave.from_junction]}_{mapping[pipe_dave.to_junction]}"
        )
        etree.SubElement(
            pipe, "length", {"unit": "km", "value": str(pipe_dave.length_km)}
        )
        etree.SubElement(
            pipe,
            "diameter",
            {"unit": "mm", "value": str(pipe_dave.diameter_mm)},
        )
        etree.SubElement(
            pipe,
            "pressureMax",
            {"unit": "bar", "value": str(pipe_dave.max_pressure_bar)},
        )
        etree.SubElement(
            pipe,
            "flowMin",
            {
                "unit": "1000m_cube_per_hour",
                "value": str(-pipe_dave.max_cap_M_m3_per_d * 1000 / 24),
            },
        )
        etree.SubElement(
            pipe,
            "flowMax",
            {
                "unit": "1000m_cube_per_hour",
                "value": str(pipe_dave.max_cap_M_m3_per_d * 1000 / 24),
            },
        )
        etree.SubElement(
            pipe,
            "roughness",
            {"unit": "mm", "value": str(pipe_dave.roughness)},
        )
        etree.SubElement(
            pipe,
            "heatTransferCoefficient",
            {"unit": "W_per_m_square_per_K", "value": "2"},
        )  # !!! annahme
        connections.append(pipe)
    # create compressor station
    for _, compressor in compressors_dave.iterrows():
        nodeid = (
            mapping[compressor.junction]
            if isinstance(mapping[compressor.junction], str)
            else mapping[compressor.junction][0]
        )
        for node in nodes:
            if node.get("id") == nodeid:
                break
        nodecopy = node
        nodecopy.attrib["id"] = nodeid + "_copy"
        nodes.append(nodecopy)

        for con in connections:
            if con.tag == "pipe":
                if con.get("from") == nodeid:
                    con.attrib["from"] = nodeid + "_copy"
        comp = etree.Element("compressorStation")
        comp.attrib["from"] = nodeid
        comp.attrib["to"] = nodeid + "_copy"
        comp.attrib["alias"] = ""
        comp.attrib["gasCoolerExisting"] = "1"
        comp.attrib["fuelGasVertex"] = nodeid
        comp.attrib["internalBypassRequired"] = "0"
        comp.attrib["id"] = compressor.dave_name

        etree.SubElement(
            comp, "flowMin", {"unit": "1000m_cube_per_hour", "value": "0"}
        )
        etree.SubElement(
            comp,
            "flowMax",
            {
                "unit": "1000m_cube_per_hour",
                "value": str(compressor.max_cap_M_m3_per_d * 1000 / 24),
            },
        )
        etree.SubElement(
            comp, "pressureLossIn", {"unit": "bar", "value": "0.8"}
        )  # !!! annahme
        etree.SubElement(
            comp, "pressureLossOut", {"unit": "bar", "value": "0.2"}
        )  # !!! annahme
        etree.SubElement(
            comp, "pressureInMin", {"unit": "bar", "value": "21.0"}
        )  # !!! Todo. aus gaslib nehmen
        etree.SubElement(
            comp,
            "pressureOutMax",
            {"unit": "bar", "value": str(compressor.max_pressure_bar)},
        )

        connections.append(comp)

        # !!! Todo: compressor Station
        # !!! Richtiger Wert Anzahl der Turbinen "num_turb" und MW
        # !!! Mapping liste Anzahl turbinen und Leistung zu CS
        mapped_cs_id = "compressorStation_5"  # !!! dummy value

        for station in gaslib_data_cs_xml:
            print(station.attrib["id"])
            if station.attrib["id"] == mapped_cs_id:
                # copy compressorstation data from gaslib cs file and change id
                temp_station = copy(station)
                temp_station.attrib["id"] = compressor.dave_name
                # wirte compressorstation in DAVE cs file
                compressorStations.append(temp_station)

    # --- save gaslib model in the dave output folder
    if save_data:
        # write net file
        file_path = output_folder + "\\dave_gaslib.net"
        network.append(information)
        network.append(nodes)
        network.append(connections)
        tree = etree.ElementTree()
        tree._setroot(network)
        tree.write(
            file_path,
            pretty_print=True,
            encoding="UTF-8",
            xml_declaration=True,
        )
        # write cs file
        file_path = output_folder + "\\dave_gaslib.cs"
        tree = etree.ElementTree()
        tree._setroot(compressorStations)
        tree.write(
            file_path,
            pretty_print=True,
            encoding="UTF-8",
            xml_declaration=True,
        )

    # update progress
    pbar.update(100)  # !!! Muss noch verteilt werden
    # return net
