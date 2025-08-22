.. _generators:

#############################
Generators
#############################

DAVE provides functions to create renewable and conventionell power plants

.. autofunction:: dave_core.components.power_plants.create_renewable_powerplants

.. autofunction:: dave_core.components.power_plants.create_conventional_powerplants


.. zusätzlich schreiben: This function checks the distance between a power plant and the associated grid node. If the distance is greater than 50 meteres, a auxillary node for the power plant and a connection line to the originial node will be created.
