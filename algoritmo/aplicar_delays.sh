#!/bin/bash
# Aplica atraso (ms) nas duas pontas de cada enlace. Valem para os 3 cenários.
aplicar() {  # roteadorA ifA roteadorB ifB atraso
  docker exec clab-trabalho1-r$1 tc qdisc replace dev $2 root netem delay ${5}ms
  docker exec clab-trabalho1-r$3 tc qdisc replace dev $4 root netem delay ${5}ms
}
aplicar 1 eth1 2 eth1 5
aplicar 1 eth2 3 eth1 10
aplicar 1 eth3 5 eth1 30
aplicar 2 eth2 4 eth1 5
aplicar 2 eth3 5 eth2 10
aplicar 3 eth2 5 eth3 10
aplicar 3 eth3 6 eth1 10
aplicar 4 eth2 7 eth1 5
aplicar 5 eth4 7 eth2 30
aplicar 6 eth2 7 eth3 10
echo "Atrasos aplicados."