# Copyright (c) 2022-2024 by Fraunhofer Institute for Energy Economics and Energy System Technology (IEE)
# Kassel and individual contributors (see AUTHORS file for details).
# All rights reserved.
# Copyright (c) 2024-2025 DAVE_core contributors
# Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.


from pandapower import from_json

# funktionen um die Netzmodelle aus elektrotechnischer sicht zu plausibilisieren

# funktioniert LAstfluss (iterativ über die einzelnen netzgruppen
# => Wirklich einzeln rechnen
# passen die Werte oder gibt es besondere ausreißer? Könnte man auch checken ob der max wert viel höher ist als der avarage


# convert to pandapower
# read pandapower
net = from_json(
    r"C:\Users\tbanze\Eigene Datein\SimBench Sektor\Netzmodell Düsseldorf\duesseldorf_dave_pandapower.json"
)
# !!! in dem net sind keine Gruppen, das muss im Converter angepasst werden. Es sind auch keine  ext grids drin


# Überlegen, ob ich hier auch das dave netz nehme, nach den netzgruppen filter und dann erst zu pp convertiere
