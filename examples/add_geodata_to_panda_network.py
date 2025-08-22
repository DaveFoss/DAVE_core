# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.

import pandapower as pp

from dave_core.converter.extend_panda import add_geodata

# create pandapower or pandapipes network
net = pp.networks.mv_oberrhein("generation")

# add geodata to the pandapower network
net = add_geodata(net)

# show new pandapower dataset with geographical informations
print(net)
