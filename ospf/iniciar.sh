#!/bin/bash
# Inicia o cenário OSPF nos 7 roteadores
cd "$(dirname "$0")"
python3 gerar_configs.py
for i in 1 2 3 4 5 6 7; do
  c=clab-trabalho1-r$i
  docker exec $c birdc down >/dev/null 2>&1 || true   # encerra BIRD antigo
  docker exec $c mkdir -p /run/bird
  docker cp configs/r$i.conf $c:/etc/bird/bird.conf
  docker exec $c bird -c /etc/bird/bird.conf
done
echo "OSPF iniciado. Aguarde uns 10-20 s para as adjacências fecharem."