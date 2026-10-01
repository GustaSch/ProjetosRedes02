#!/bin/bash
# Inicia o cenário RIP nos 7 roteadores
cd "$(dirname "$0")"
../parar.sh                      # garante que nenhum outro cenário está ativo
python3 gerar_configs.py
for i in 1 2 3 4 5 6 7; do
  c=clab-trabalho1-r$i
  docker exec $c mkdir -p /run/bird
  docker cp configs/r$i.conf $c:/etc/bird/bird.conf
  docker exec $c bird -c /etc/bird/bird.conf
done
echo "RIP iniciado. Aguarde uns 10-20 s para a tabela convergir."