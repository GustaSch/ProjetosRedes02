#!/usr/bin/env python3
"""Q-routing (Boyan & Littman, 1994), variante full-echo, com atrasos reais medidos.

Cada roteador x mantém Q[x][d][y]: estimativa (ms) do tempo de entrega ao
destino d passando pelo vizinho y. A cada sonda:
    Q[x][d][y] += alpha * (s_xy + t - Q[x][d][y])
onde s_xy é o atraso do enlace x-y (medido com ping) e t = min_z Q[y][d][z]
(0 se y é o próprio destino; z != x, como split horizon).
As rotas instaladas seguem o menor Q.
"""
import argparse, csv, os, re, subprocess, time
from concurrent.futures import ThreadPoolExecutor

PREFIXO = "clab-trabalho1-r"
INF = 1000.0                      # ms: penalidade de enlace caído
ROUTERS = range(1, 8)

# (rot_a, if_a, ip_a, rot_b, if_b, ip_b, rede)
LINKS = [
    (1, "eth1", "10.0.12.1", 2, "eth1", "10.0.12.2", "10.0.12.0/30"),
    (1, "eth2", "10.0.13.1", 3, "eth1", "10.0.13.2", "10.0.13.0/30"),
    (1, "eth3", "10.0.15.1", 5, "eth1", "10.0.15.2", "10.0.15.0/30"),
    (2, "eth2", "10.0.24.1", 4, "eth1", "10.0.24.2", "10.0.24.0/30"),
    (2, "eth3", "10.0.25.1", 5, "eth2", "10.0.25.2", "10.0.25.0/30"),
    (3, "eth2", "10.0.35.1", 5, "eth3", "10.0.35.2", "10.0.35.0/30"),
    (3, "eth3", "10.0.36.1", 6, "eth1", "10.0.36.2", "10.0.36.0/30"),
    (4, "eth2", "10.0.47.1", 7, "eth1", "10.0.47.2", "10.0.47.0/30"),
    (5, "eth4", "10.0.57.1", 7, "eth2", "10.0.57.2", "10.0.57.0/30"),
    (6, "eth2", "10.0.67.1", 7, "eth3", "10.0.67.2", "10.0.67.0/30"),
]

# prefixo -> roteadores que o possuem
DONOS = {l[6]: [l[0], l[3]] for l in LINKS}
DONOS.update({f"10.255.0.{n}/32": [n] for n in ROUTERS})
DONOS["192.168.1.0/24"] = [1]
DONOS["192.168.2.0/24"] = [7]

# VIZ[x][y] = (interface de x, IP de y no enlace)
VIZ = {n: {} for n in ROUTERS}
for a, ia, ipa, b, ib, ipb, _ in LINKS:
    VIZ[a][b] = (ia, ipb)
    VIZ[b][a] = (ib, ipa)

SONDAS = 0                        # pings enviados (cada um = 2 pacotes)


def sh(n, cmd):
    return subprocess.run(["docker", "exec", f"{PREFIXO}{n}"] + cmd.split(),
                          capture_output=True, text=True)


def medir_enlace(l):
    a, ia, _, b, _, ipb, _ = l
    r = sh(a, f"ping -c 1 -W 1 -I {ia} {ipb}")
    m = re.search(r"time=([\d.]+) ms", r.stdout)
    return a, b, (float(m.group(1)) / 2 if m else INF)   # atraso de ida


def medir_todos(pool):
    global SONDAS
    atraso = {}
    for a, b, d in pool.map(medir_enlace, LINKS):
        atraso[(a, b)] = atraso[(b, a)] = d
    SONDAS += len(LINKS)
    return atraso


def melhor(Q, x, d):
    y = min(Q[x][d], key=Q[x][d].get)
    return y, Q[x][d][y]


def rodada(Q, atraso, alpha):
    """Atualiza a estimativa de TODOS os vizinhos de cada roteador (full-echo).

    t = melhor estimativa do vizinho y até d, ignorando x como retorno
    (split horizon), o que evita laços de dois roteadores.
    """
    for x in ROUTERS:
        for d in ROUTERS:
            if d == x:
                continue
            for y in VIZ[x]:
                if y == d:
                    t = 0.0
                else:
                    t = min((Q[y][d][z] for z in VIZ[y] if z != x), default=INF)
                alvo = min(INF, atraso[(x, y)] + t)
                Q[x][d][y] += alpha * (alvo - Q[x][d][y])


def calcular_rotas(Q, atual):
    """Escolhe o próximo salto de cada roteador para cada prefixo (com histerese)."""
    novas = {}
    for x in ROUTERS:
        for net, donos in DONOS.items():
            if x in donos:
                continue
            v, o, y = min((melhor(Q, x, o)[1], o, melhor(Q, x, o)[0]) for o in donos)
            ant = atual.get((x, net))
            if ant is not None and ant != y:
                v_ant = Q[x][o][ant]
                if v_ant < INF / 2 and v_ant <= v * 1.10 + 0.5:
                    y = ant                       # histerese: evita oscilação
            novas[(x, net)] = (y, Q[x][o][y])
    return novas


def instalar(m):
    x, net, y = m
    iface, ip = VIZ[x][y]
    sh(x, f"ip route replace {net} via {ip} dev {iface} proto static metric 20")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--intervalo", type=float, default=1.0)
    ap.add_argument("--treino", type=int, default=300)
    ap.add_argument("--rodadas", type=int, default=5)
    ap.add_argument("--log", default="metricas/resultados/qrouting_eventos.csv")
    args = ap.parse_args()

    pool = ThreadPoolExecutor(max_workers=10)
    for n in ROUTERS:                                   # garante cenário limpo
        sh(n, "birdc down")
        sh(n, "ip route flush proto static")
    os.makedirs(os.path.dirname(args.log), exist_ok=True)

    Q = {x: {d: {y: 0.0 for y in VIZ[x]} for d in ROUTERS if d != x}
         for x in ROUTERS}
    atraso = medir_todos(pool)
    for _ in range(args.treino):                        # treino inicial (local)
        rodada(Q, atraso, args.alpha)

    atual, t0 = {}, time.time()
    with open(args.log, "w", newline="") as f:
        log = csv.writer(f)
        log.writerow(["tempo_s", "roteador", "prefixo", "proximo_salto", "estimativa_ms"])
        print("Q-routing ativo. Ctrl+C para encerrar.")
        try:
            while True:
                atraso = medir_todos(pool)
                for _ in range(args.rodadas):
                    rodada(Q, atraso, args.alpha)
                novas = calcular_rotas(Q, atual)
                mud = [(x, net, y) for (x, net), (y, _) in novas.items()
                       if atual.get((x, net)) != y]
                if mud:
                    list(pool.map(instalar, mud))
                    t = round(time.time() - t0, 2)
                    for x, net, y in mud:
                        atual[(x, net)] = y
                        log.writerow([t, f"R{x}", net, f"R{y}", round(novas[(x, net)][1], 1)])
                        print(f"[{t:7.2f}s] R{x}: {net} via R{y} (~{novas[(x, net)][1]:.1f} ms)")
                    f.flush()
                time.sleep(args.intervalo)
        except KeyboardInterrupt:
            dur = time.time() - t0
            print(f"\nSondas: {SONDAS} pings (~{SONDAS * 2} pacotes, "
                  f"~{SONDAS * 2 * 98} bytes) em {dur:.0f} s")


if __name__ == "__main__":
    main()