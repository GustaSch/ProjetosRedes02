#!/bin/bash
for i in 1 2 3 4 5 6 7; do
  docker exec clab-trabalho1-r$i birdc down >/dev/null 2>&1 || true
  docker exec clab-trabalho1-r$i ip route flush proto static >/dev/null 2>&1 || true
done
echo "BIRD parado e rotas estáticas removidas em todos os roteadores."