import pandapower as pp
import math

from dave import dave_output_dir

# hier wird das Stromnetzmodell anhand der grid_data erstellt. ruaskommen soll dan fertiges pp netz als pickel(oder json?)

# hier noch if abfragen bei den einzelnen komponenten hin zur abfrage ob empty. 

# voltage_level sollte auch in dem pandapower modell mit eingetragen werden. 


def create_power_grid(grid_data):
    """
    This function creates papandapower network.

    INPUT:
        **grid_data** (attrdict) - calculated grid data from dave

    OUTPUT:
        **net** (attrdict) - PANDAPOWER attrdict with grid data

    EXAMPLE:

    """
    print('create pandapower network for target area')
    print('-----------------------------------------')
    # create empty network
    net = pp.create_empty_network()
    
    # --- create extra high voltage topology
    # create buses
    if not grid_data.ehv_data.ehv_nodes.empty:
        for i, bus in grid_data.ehv_data.ehv_nodes.iterrows():
            pp.create_bus(net,
                          name=bus.dave_name,
                          vn_kv=bus.voltage_kv,
                          geodata=bus.geometry.coords[:][0])
            # additional Informations
            bus_id = pp.get_element_index(net, 
                                          element='bus', 
                                          name=bus.dave_name)
            net.bus.at[bus_id, 'ego_bus_id'] = bus.ego_bus_id
            net.bus.at[bus_id, 'ego_version'] = bus.ego_version
            net.bus.at[bus_id, 'tso_name'] = bus.tso_name
    # create lines
    if not grid_data.ehv_data.ehv_lines.empty:
        for i, line in grid_data.ehv_data.ehv_lines.iterrows():
            line_coords = line.geometry[0].coords[:]
            c_nf = float(line.b)/(2*math.pi*float(line.frequency))*1E09
            from_bus = net.bus[net.bus.ego_bus_id == line.bus0].index[0]
            to_bus = net.bus[net.bus.ego_bus_id == line.bus1].index[0]
            pp.create_line_from_parameters(net, 
                                           from_bus=from_bus,
                                           to_bus=to_bus,
                                           length_km=line.length_km,
                                           r_ohm_per_km=float(line.r)/line.length_km,
                                           x_ohm_per_km=float(line.x)/line.length_km,
                                           c_nf_per_km=c_nf/line.length_km,
                                           max_i_ka= ((float(line.s_nom_mva)*1E06)/(line.voltage_kv*1E03))*1E-03,
                                           name=line.dave_name,
                                           type='ol',
                                           geodata=[list(coords) for coords in line_coords],
                                           parallel=line.cables/3)
            # additional Informations
            line_id = pp.get_element_index(net, 
                                           element='line', 
                                           name=line.dave_name)
            net.line.at[line_id, 'ego_line_id'] = line.ego_line_id
            net.line.at[line_id, 'ego_version'] = line.ego_version

    # --- create high voltage topology
    # create buses
    if not grid_data.hv_data.hv_nodes.empty:
        for i, bus in grid_data.hv_data.hv_nodes.iterrows():
            pp.create_bus(net,
                          name=bus.dave_name,
                          vn_kv=bus.voltage_kv,
                          geodata=bus.geometry.coords[:][0])
            # additional Informations
            bus_id = pp.get_element_index(net, 
                                          element='bus',
                                          name=bus.dave_name)
            net.bus.at[bus_id, 'ego_bus_id'] = bus.ego_bus_id
            net.bus.at[bus_id, 'ego_version'] = bus.ego_version
    # create lines 
    if not grid_data.hv_data.hv_lines.empty:
        for i, line in grid_data.hv_data.hv_lines.iterrows():
            line_coords = line.geometry[0].coords[:]
            c_nf = float(line.b)/(2*math.pi*float(line.frequency))*1E09
            from_bus = net.bus[net.bus.ego_bus_id == line.bus0].index[0]
            to_bus = net.bus[net.bus.ego_bus_id == line.bus1].index[0]
            pp.create_line_from_parameters(net, 
                                           from_bus=from_bus,
                                           to_bus=to_bus,
                                           length_km=line.length_km,
                                           r_ohm_per_km=float(line.r)/line.length_km,
                                           x_ohm_per_km=float(line.x)/line.length_km,
                                           c_nf_per_km=c_nf/line.length_km,
                                           max_i_ka= ((float(line.s_nom_mva)*1E06)/110E03)*1E-03,
                                           name=line.dave_name,
                                           type='ol',
                                           geodata=[list(coords) for coords in line_coords],
                                           parallel=line.cables/3)
            # additional Informations
            line_id = pp.get_element_index(net, 
                                           element='line',
                                           name=line.dave_name)
            net.line.at[line_id, 'ego_line_id'] = line.ego_line_id
            net.line.at[line_id, 'ego_version'] = line.ego_version

            
           
    # --- create medium voltage topology
    
    
    # --- create low voltage topology
    # create buses
    vn_kv_lv = 0.4
    if not grid_data.lv_data.lv_nodes.empty:
        for i, bus in grid_data.lv_data.lv_nodes.iterrows():
            bus_geoedata = bus.geometry.coords[:][0]
            pp.create_bus(net,
                          name=bus.dave_name,
                          vn_kv=vn_kv_lv,
                          geodata=bus_geoedata)
            # additional Informations
            bus_id = pp.get_element_index(net, 
                                          element='bus',
                                          name=bus.dave_name)
            net.bus.at[bus_id, 'node_type'] = bus.node_type

    # lv buses for road junctions
    if not grid_data.roads.road_junctions.empty:
        for i, junction in grid_data.roads.road_junctions.items():
            junction_point = junction.coords[:][0]
            pp.create_bus(net,
                          name=f'road junction {i}',
                          vn_kv=vn_kv_lv,
                          geodata=junction_point,
                          type='m')
    # create lines
    std_type = 'NAYY 4x150 SE'  # dummy value, must be changed
    # lv lines for buildings
    if not grid_data.lv_data.lv_lines.empty:
        for i, line in grid_data.lv_data.lv_lines.iterrows():
            line_coords = line.geometry.coords[:]
            start_bus = net.bus_geodata[net.bus_geodata.x == line_coords[0][0]].index[0]
            end_bus = net.bus_geodata[net.bus_geodata.x == line_coords[len(line_coords)-1][0]].index[0]
            pp.create_line(net,
                           name=line.dave_name,
                           from_bus=start_bus,
                           to_bus=end_bus,
                           length_km=line.length_m/1000,
                           std_type=std_type,
                           geodata=[list(coords) for coords in line_coords])
            # additional Informations
            line_id = pp.get_element_index(net, 
                                          element='line',
                                          name=line.dave_name)
            net.line.at[line_id, 'line_type'] = line.line_type
    # --- create transformers
    # create ehv/ehv transformers
    if not grid_data.components_power.transformers.ehv_ehv.empty:
        for i, trafo in grid_data.components_power.transformers.ehv_ehv.iterrows():
            trafo_geometry = trafo.geometry.coords[:][0]
            hv_bus = net.bus[net.bus.ego_bus_id == trafo.bus1].index[0]
            lv_bus = net.bus[net.bus.ego_bus_id == trafo.bus0].index[0]
            
            # trafo über parameter. Dafür müssen die Parameter noch berechnet werden
            # aber wie? wenn ich nur r,x,b, gegeben habe
            pp.create_transformer_from_parameters(net, 
                                                  hv_bus=hv_bus, 
                                                  lv_bus=lv_bus, 
                                                  sn_mva=trafo.s_nom_mva, 
                                                  vn_hv_kv=trafo.voltage_kv_os, 
                                                  vn_lv_kv=trafo.voltage_kv_us, 
                                                  vkr_percent=0,  # dummy value
                                                  vk_percent=10,  # dummy value
                                                  pfe_kw=0,  # dummy value accepted as ideal
                                                  i0_percent=0, # dummy value accepted as ideal
                                                  shift_degree=trafo.phase_shift, 
                                                  name=f'EHV/EHV Trafo {i}')
            # additional Informations
            trafo_id = pp.get_element_index(net, 
                                            element='trafo',
                                            name=f'EHV/EHV Trafo {i}')
            #net.trafo.at[trafo_id, 'geometry'] = [[trafo_geometry]]
            net.line.at[trafo_id, 'ego_trafo_id'] = trafo.ego_trafo_id
            net.line.at[trafo_id, 'ego_version'] = trafo.ego_version
    # create ehv/hv transformers
    if not grid_data.components_power.transformers.ehv_hv.empty:
        for i, trafo in grid_data.components_power.transformers.ehv_hv.iterrows():
            trafo_geometry = trafo.geometry.coords[:][0]
            hv_bus = net.bus[net.bus.ego_bus_id == trafo.bus1].index[0]
            lv_bus = net.bus[net.bus.ego_bus_id == trafo.bus0].index[0]
            
            # trafo über parameter. Dafür müssen die Parameter noch berechnet werden
            # aber wie? wenn ich nur r,x,b, gegeben habe
            pp.create_transformer_from_parameters(net, 
                                                  hv_bus=hv_bus, 
                                                  lv_bus=lv_bus, 
                                                  sn_mva=trafo.s_nom_mva, 
                                                  vn_hv_kv=trafo.voltage_kv_os, 
                                                  vn_lv_kv=trafo.voltage_kv_us, 
                                                  vkr_percent=0,  # dummy value 
                                                  vk_percent=10,   # dummy value
                                                  pfe_kw=0,  # dummy value accepted as ideal
                                                  i0_percent=0, # dummy value accepted as ideal
                                                  shift_degree=trafo.phase_shift, 
                                                  name=f'EHV/HV Trafo {i}')
            # additional Informations
            trafo_id = pp.get_element_index(net, 
                                            element='trafo',
                                            name=f'EHV/HV Trafo {i}')
            #net.trafo.at[trafo_id, 'geometry'] = trafo_geometry
            net.line.at[trafo_id, 'ego_trafo_id'] = trafo.ego_trafo_id
            net.line.at[trafo_id, 'ego_version'] = trafo.ego_version
        



    
    # --- create loads
    
    # ---create generators
            
            
    # save grid model in the dave output folder
    file_path = dave_output_dir + '\\dave_power_grid.p'
    pp.to_pickle(net, file_path)
    
    
    return net