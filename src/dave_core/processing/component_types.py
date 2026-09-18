from math import ceil
from random import choices

from dask_geopandas import from_geopandas
from networkx import descendants
from pandapower.std_types import basic_line_std_types
from pandapower.std_types import basic_trafo_std_types
from pandas import DataFrame

from dave_core.model_utils import create_directed_graph
from dave_core.model_utils import direction_away_from_node
from dave_core.progressbar import create_tqdm
from dave_core.progressbar import create_tqdm_dask
from dave_core.settings import dave_settings


def node_gen_power(grid_data, bus_name):
    """
    This function collects the generation power for a node in the network based on the sum of \
    power plants which are connected to it
    returns power in kW
    """
    # get generated power from renewable power plants in kw
    if not grid_data.components_power.renewable_powerplants.empty:
        power_ren_plants = grid_data.components_power.renewable_powerplants[
            grid_data.components_power.renewable_powerplants.bus == bus_name
        ]
        if power_ren_plants.empty:
            power_ren_plants = 0
        else:
            power_ren_plants = power_ren_plants.electrical_capacity_kw.astype("float").sum()
    else:
        power_ren_plants = 0

    # get generated power from conventional power plants in kw
    if not grid_data.components_power.conventional_powerplants.empty:
        power_conv_plants = grid_data.components_power.conventional_powerplants[
            grid_data.components_power.conventional_powerplants.bus == bus_name
        ]
        if power_conv_plants.empty:
            power_conv_plants = 0
        else:
            power_conv_plants = power_conv_plants.electrical_capacity_kw.astype("float").sum()
    else:
        power_conv_plants = 0
    # calculate generation power for node and return
    return power_ren_plants + power_conv_plants


def node_consum_power(grid_data, bus_name):
    """
    This function collects the consumption power for a node in the network based on loads which are \
    connected to it
    returns power in kW
    """
    # get consumed power from loads
    if not grid_data.components_power.loads.empty:
        power_loads = grid_data.components_power.loads[
            grid_data.components_power.loads.bus == bus_name
        ]
        if power_loads.empty:
            power_loads = 0
        else:
            power_loads = power_loads.p_mw.sum()
    else:
        power_loads = 0

    # calculate consumption power for node and return
    return power_loads * 1000


def descendant_line_power(graph, nodes, line_nodes):
    """
    This function calculates the descendant generation and consumption power for a line

    INPUT:
        **graph** (networkx graph) - directed graph \n
        **nodes** (DataFrame) - grid nodes \n
        **line_nodes** (tuple) - from and to bus of the line to calculate power for \n
    """
    # check line direction to get right to_bus
    if line_nodes in list(graph.edges):
        node_rel = line_nodes[1]
    elif (line_nodes[1], line_nodes[0]) in list(graph.edges):
        node_rel = line_nodes[0]
    else:
        raise TypeError("Line is missing in graph")
    # collect all descendant nodes for line of interest
    nodes_desc = descendants(graph, node_rel)
    nodes_desc = [*list(nodes_desc), node_rel]
    # summarize generation and consumption power
    power_gen_desc_kw = nodes[nodes.dave_name.isin(nodes_desc)].power_gen_kw.sum()
    power_load_desc_kw = nodes[nodes.dave_name.isin(nodes_desc)].power_load_kw.sum()
    return (power_gen_desc_kw, power_load_desc_kw)


def find_line_std_type(std_types, line_type, line_power):
    """
    This function searches the suitable standarttype for a line based on type and max power that flows over it

    INPUT:
        **standard_types** (DataFrame) - DataFrame which includes all line standard types that can \
            be used in the network model.
        **line_type** (str) - DataFrame
        **line_power** (float) - Maximal power that flows over the line
    """
    # filter relevant standard types by line type and max power
    std_types_rel = std_types[(std_types.type == line_type) & (std_types.max_power_kw > line_power)]
    # select the standard type with the minimum suitable power
    if not std_types_rel.empty:
        std_type = (
            std_types_rel[std_types_rel.max_power_kw == std_types_rel.max_power_kw.min()]
            .iloc[0]
            .name
        )
        parallel = 1
    else:
        # take the biggest transformer and count how much in parralel will be needed
        std_type = std_types[std_types.type == line_type].max_power_kw.idxmax()
        parallel = ceil(line_power / std_types.loc[std_type].max_power_kw)
    return std_type, parallel


def find_trafo_std_type(std_types, trafo_power):
    """
    This function searches the suitable standarttype for a trafo based on max power that flows over it

    INPUT:
        **standard_types** (DataFrame) - DataFrame which includes all trafo standard types that can \
            be used in the network model.
        **trafo_power** (float) - Maximal power that flows over the line
    """
    # filter relevant standard types by line type and max power
    std_types_rel = std_types[std_types.max_power_kva > trafo_power]
    # select the standard type with the minimum suitable power
    if not std_types_rel.empty:
        std_type = (
            std_types_rel[std_types_rel.max_power_kva == std_types_rel.max_power_kva.min()]
            .iloc[0]
            .name
        )
        parallel = 1
    else:
        # take the biggest transformer and count how much in parralel will be needed
        std_type = std_types.max_power_kva.idxmax()
        parallel = ceil(trafo_power / std_types.loc[std_type].max_power_kva)
    return std_type, parallel


def calculate_line_types_lv(grid_data, ol_share, standard_types=None, line_loading_design=0.7):
    # TODO: adding real option resp. values from structure data for ol_share
    """
    This function searches for the suitable line standardtype based on the balanced downstream power

    Attention: Only usable for beam networks!

    INPUT:
        **grid_data** (DAVE dict) - DAVE dataset \n
        **ol_share** (float) - Share of overhead lines to distribute line types in the network. \
            Number has to be between 0 and 1\n

    OPTIONAL:
        **standard_types** (DataFrame, default None) - DataFrame which includes all line standard \
            types that can be used in the network model. Per default all suitable standard types \
            from pandapower will be used \n
        **line_loading_design** (float, default 0.7) - Defines what percentage of the maximum power \
            of the line standard types may be utilized \n
    """
    # add generation and consumption power for each network node
    nodes = grid_data.lv_data.lv_nodes
    nodes_name_dask = from_geopandas(nodes.dave_name, npartitions=dave_settings["cpu_number"])
    with create_tqdm_dask(desc="Calculate generation per node", bar_type="sub_bar"):
        nodes["power_gen_kw"] = nodes_name_dask.apply(
            lambda x, grid_data=grid_data: node_gen_power(grid_data, bus_name=x),
            meta=nodes_name_dask,
        ).compute()
    with create_tqdm_dask(desc="Calculate demand per node", bar_type="sub_bar"):
        nodes["power_load_kw"] = nodes_name_dask.apply(
            lambda x, grid_data=grid_data: node_consum_power(grid_data, bus_name=x),
            meta=nodes_name_dask,
        ).compute()
    # create directed graph
    lines = grid_data.lv_data.lv_lines
    # lines_dask = from_geopandas(lines, npartitions=dave_settings["cpu_number"])
    # with create_tqdm_dask(desc="search from nodes for graph", bar_type="sub_bar"):
    #     lines.from_node = lines_dask.from_node.apply(
    #         lambda x: nodes[nodes.dave_name == x].index[0], meta=lines_dask
    #     ).compute()
    # with create_tqdm_dask(desc="search to nodes for graph", bar_type="sub_bar"):
    #     lines.to_node = lines_dask.to_node.apply(
    #         lambda x: nodes[nodes.dave_name == x].index[0], meta=lines_dask
    #     ).compute()
    graph = create_directed_graph(nodes, lines)
    # bringing lines in correct direction from slack bus
    graph = direction_away_from_node(
        graph,
        target_node=nodes[
            nodes.node_type.isin(["trafo_connection", "mvlv_substation"])
        ].dave_name.to_list(),
    )
    # calculate descendant power for lines
    lines_dask = from_geopandas(lines, npartitions=dave_settings["cpu_number"])
    with create_tqdm_dask(desc="calculate descendant power", bar_type="sub_bar"):
        line_power_desc = lines_dask.apply(
            lambda x, graph=graph, nodes=nodes: descendant_line_power(
                graph, nodes, (x.from_node, x.to_node)
            ),
            axis=1,
            meta=lines_dask,
        ).compute()
    lines["power_gen_desc_kw"] = line_power_desc.apply(lambda x: x[0])
    lines["power_load_desc_kw"] = line_power_desc.apply(lambda x: x[1])

    # --- find suitable standart types
    # define standard types
    if not standard_types:
        # get list of standart types from pandapower and reduce them to low voltage lines
        lines_std = DataFrame.from_dict(basic_line_std_types(), orient="index")
        lines_std = lines_std[lines_std.voltage_rating == "LV"]
        # calculate max_power
        lines_std["max_power_kw"] = lines_std.max_i_ka.apply(
            lambda x: x * 400 * line_loading_design
        )  # the voltage of lv is 400V
    else:
        pass  # TODO: Das noch schreiben
        # werden hier ncoh anpassungen benötigt?? Evt auch Leistung bestimmen, ggf. kann ich das raus ziehen aus if/else
        # die Std types auch in dem dave dataset speichern, damit da später (z.B. beim konvertieren zu pp drauf zurück gegriffen werden kann)

    """
    TODO: develop method to distribute ol and cs
    => Temporär mittels Zufallsentscheidung

    Bedingungen:
        1. Das Verhältnis zwischen cs und ol sollte optional sein und als default den wert der\
            region haben (gemessen an den Veröffentlichten Leitungslängen, des entsprechenden NBs)
        2. Für die Hausanschlussleitung sollte der gleiche typ gelten wie für die Verbindungsleitung
    """
    # define if line is a cable or a overhead line (calculate random distribution)
    type_options = ["ol", "cs"]
    type_share = [ol_share, 1 - ol_share]
    lines["type"] = choices(type_options, weights=type_share, k=len(lines))  # noqa: S311

    # choose std type
    lines_dask = from_geopandas(lines, npartitions=dave_settings["cpu_number"])
    with create_tqdm_dask(desc="define std type for lines", bar_type="sub_bar"):
        lines_std_def = lines_dask.apply(
            lambda x, lines_std=lines_std: find_line_std_type(
                lines_std, x.type, max(x.power_gen_desc_kw, x.power_load_desc_kw)
            ),
            axis=1,
            meta=lines_dask,
        ).compute()
    lines["std_type"] = lines_std_def.apply(lambda x: x[0])
    lines["parallel"] = lines_std_def.apply(lambda x: x[1])


def calculate_trafo_types_lv(grid_data, standard_types=None, trafo_loading_design=0.7):
    """
    This function searches for the suitable trafo standardtype based on the balanced downstream power

    Attention: Only usable for beam networks!

    INPUT:
        **grid_data** (DAVE dict) - DAVE dataset \n

    OPTIONAL:
        **standard_types** (DataFrame, default None) - DataFrame which includes all line standard \
            types that can be used in the network model. Per default all suitable standard types \
            from pandapower will be used \n
        **trafo_loading_design** (float, default 0.7) - Defines what percentage of the maximum power \
            of the standard types trafos may be utilized \n
    """
    # TODO: hier Methode zur Auswahl der Trafotypes, das kann auch über die gen und load maxs gehen.
    # Die Werte müsste ich dann in line types in grid_data schreiben oder als globale function und
    # dann hier und in lines checken ob der Wert schon berechnet wurde

    # calculate max power that flows over transformers
    trafos = grid_data.components_power.transformers.mv_lv
    nodes = grid_data.lv_data.lv_nodes
    lines = grid_data.lv_data.lv_lines[
        grid_data.lv_data.lv_lines.line_type == "line_mvlv_transformer"
    ]
    # get maximum power flow over transformer from suitable line
    if len(trafos) > 0:
        # Assumption that every net group has only one transformer      # TODO: consider the case that one netgroup has more than one transformer (meshed grid)
        trafos["max_power_kw"] = trafos.bus_lv.apply(
            lambda x: max(
                lines[
                    lines.from_node == nodes[nodes.dave_name == x].iloc[0].dave_name
                ].power_gen_desc_kw.sum(),
                lines[
                    lines.from_node == nodes[nodes.dave_name == x].iloc[0].dave_name
                ].power_load_desc_kw.sum(),
            )
        )
    else:
        # no transformer in the considered area
        raise ValueError(
            "There is no transformer in the considered area. This case is not covered yet"
        )

    # --- find suitable standart types
    # define standard types
    if not standard_types:
        # get list of standart types from pandapower and reduce them to low voltage lines
        trafos_std = DataFrame.from_dict(basic_trafo_std_types(), orient="index")
        trafos_std = trafos_std[
            (trafos_std.vn_lv_kv == 0.4) & (trafos_std.vn_hv_kv == dave_settings["mv_voltage"])
        ]
        trafos_std["max_power_kva"] = trafos_std.sn_mva.apply(
            lambda x: x * 1000 * trafo_loading_design
        )
    else:
        pass  # TODO: Das noch schreiben
        # werden hier noch anpassungen benötigt?? Evt auch Leistung bestimmen, ggf. kann ich das raus ziehen aus if/else
        # die Std types auch in dem dave dataset speichern, damit da später (z.B. beim konvertieren zu pp drauf zurück gegriffen werden kann)

    with create_tqdm_dask(desc="define std type for trafos", bar_type="sub_bar"):
        trafos_std = trafos.max_power_kw.apply(
            lambda x, trafos_std=trafos_std: find_trafo_std_type(trafos_std, x)
        )
    trafos["std_type"] = trafos_std.apply(lambda x: x[0])
    trafos["parallel"] = trafos_std.apply(lambda x: x[1])


def lv_processing_components(grid_data):
    # set main progress bar for lv topology
    pbar = create_tqdm(desc="processing low voltage topology", bar_type="main_bar")
    # processing line data
    ol_share = (
        0.3357  # TODO: delet example when adding real option resp. values from structure data
    )
    calculate_line_types_lv(grid_data, ol_share, standard_types=None, line_loading_design=0.7)
    # update progress
    pbar.update(50)
    pbar.refresh()
    # processing transformer data
    calculate_trafo_types_lv(grid_data)
    # update progress
    pbar.update(50)
    pbar.refresh()
