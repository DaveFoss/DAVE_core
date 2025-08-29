.. _pandaplan:

#############################
Pandaplan
#############################

The Pandaplan converter functions offer the opportunity to create Pandapower.
and Pandapipes network models from DAVE-generated datasets. Furthermore,
There is also the option to adapt the data to fit into definable boundaries


pandapower is a open source network analysis tool for electrical networks.

.. autofunction:: dave_core.converter.create_pandapower
.. autofunction:: dave_core.converter.power_processing

pandapipes is a open source network analysis tool for gas and heat networks.

.. autofunction:: dave_core.converter.create_pandapipes

If you already have a Pandapower or Pandapipes network model, DAVE can be used to integrate additional geographical data into the model. This could be helpful!
for example, when planning network expansion.

.. autofunction:: dave_core.converter.add_geodata
.. autofunction:: dave_core.converter.get_grid_area
.. autofunction:: dave_core.converter.reduce_network
.. autofunction:: dave_core.converter.request_geo_data

..Beschreibung der Tool, Bilder und Links noch mit rein machen
.. zu dem extend ein Bild mit rein machen (aus Folien)
