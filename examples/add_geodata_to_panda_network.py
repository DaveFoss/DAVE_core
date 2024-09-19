import pandapower as pp

from dave_core.converter.extend_panda import add_geodata

# create pandapower or pandapipes network
net = pp.networks.mv_oberrhein("generation")

# add geodata to the pandapower network
net = add_geodata(net, crs="epsg:31467")

# show new pandapower dataset with geographical informations
print(net)
