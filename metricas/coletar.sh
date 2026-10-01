#!/bin/bash
# Coleta as métricas de UM cenário.
# Uso: ./metricas/coletar.sh rip|ospf|qrouting [down|loss]
#   down = derruba a interface (falha com detecção por link)
#   loss = enlace continua "up" mas descarta 100% (falha silenciosa)
CEN=${1:?uso: $0 rip|ospf|qrouting [down|loss]}
MODO=${2:-down}
cd "$(dirname "$0")/.."                 # raiz do projeto
SAIDA="metricas/resultados/$CEN"
DUR=60                                  # segundos de captura do tráfego de controle
INTERVALO=0.1                           # intervalo do ping de falha (s)
C() { echo "clab-trabalho1-$1"; }

case $CEN in
  rip)      FILTRO="udp port 520"; ESPERA=45; FA="1 eth3 30"; FB="5 eth1 30" ;;
  ospf)     FILTRO="ip proto 89";  ESPERA=45; FA="1 eth3 30"; FB="5 eth1 30" ;;
  qrouting) FILTRO="icmp";         ESPERA=15; FA="2 eth2 5";  FB="4 eth1 5"  ;;
  *) echo "Cenário inválido: $CEN"; exit 1 ;;
esac
read RA IFA DA <<< "$FA"
read RB IFB DB <<< "$FB"

rm -rf "$SAIDA"; mkdir -p "$SAIDA"
echo "DUR=$DUR INTERVALO=$INTERVALO MODO=$MODO" > "$SAIDA/info.txt"

echo "== [$CEN] iniciando cenário =="
./parar.sh
./algoritmo/aplicar_delays.sh
case $CEN in
  rip)      ./rip/iniciar.sh ;;
  ospf)     ./ospf/iniciar.sh ;;
  qrouting) python3 algoritmo/qrouting.py --log "$SAIDA/eventos.csv" > "$SAIDA/qrouting.log" 2>&1 &
            QPID=$! ;;
esac
echo "Aguardando convergência (${ESPERA}s)..."
sleep $ESPERA
docker exec $(C h1) ping -c 2 -W 2 192.168.2.10 > /dev/null \
  || echo "AVISO: h1 não alcança h2. Verifique antes de continuar (Ctrl+C)."

echo "== 1/4 tamanho da tabela de rotas =="
for i in 1 2 3 4 5 6 7; do
  n=$(docker exec $(C r$i) ip route | grep -vc eth0)   # ignora rotas da rede de gerência
  echo "r$i $n" >> "$SAIDA/rotas.txt"
done
docker exec $(C h1) traceroute -n -w 1 -q 1 192.168.2.10 > "$SAIDA/caminho_antes.txt"

echo "== 2/4 tráfego de controle (${DUR}s) =="
for i in 1 2 3 4 5 6 7; do
  docker exec -d $(C r$i) sh -c "rm -f /tmp/ctrl.pcap; timeout $DUR tcpdump -i any -Q out -nn -w /tmp/ctrl.pcap $FILTRO"
done
sleep $((DUR + 3))
for i in 1 2 3 4 5 6 7; do
  docker cp $(C r$i):/tmp/ctrl.pcap "$SAIDA/ctrl_r$i.pcap"
done

echo "== 3/4 delay fim a fim =="
docker exec $(C h1) ping -c 50 -i 0.2 192.168.2.10 > "$SAIDA/rtt.txt"

echo "== 4/4 falha de enlace (modo $MODO) =="
docker exec $(C h1) ping -c 600 -i $INTERVALO 192.168.2.10 > "$SAIDA/falha.txt" &
PP=$!
sleep 5
if [ "$MODO" = "down" ]; then
  docker exec $(C r$RA) ip link set $IFA down
else
  docker exec $(C r$RA) tc qdisc replace dev $IFA root netem delay ${DA}ms loss 100%
  docker exec $(C r$RB) tc qdisc replace dev $IFB root netem delay ${DB}ms loss 100%
fi
sleep 30
docker exec $(C h1) traceroute -n -w 1 -q 1 192.168.2.10 > "$SAIDA/caminho_depois.txt"
wait $PP

echo "Restaurando enlace e encerrando..."
if [ "$MODO" = "down" ]; then
  docker exec $(C r$RA) ip link set $IFA up
else
  docker exec $(C r$RA) tc qdisc replace dev $IFA root netem delay ${DA}ms
  docker exec $(C r$RB) tc qdisc replace dev $IFB root netem delay ${DB}ms
fi
[ -n "$QPID" ] && kill $QPID 2>/dev/null
sleep 3
./parar.sh
echo "Pronto: $SAIDA"