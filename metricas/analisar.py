#!/usr/bin/env python3
"""Lê metricas/resultados/<cenario>/ e gera resumo.csv + gráficos em metricas/graficos/."""
import csv, re, struct
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAIZ = Path(__file__).parent
RES, GRAF = RAIZ / "resultados", RAIZ / "graficos"
GRAF.mkdir(exist_ok=True)
CENARIOS = [("rip", "RIP"), ("ospf", "OSPF"), ("qrouting", "Q-routing")]
CORES = ["#4C72B0", "#55A868", "#C44E52"]
AJUSTE = {113: 2, 276: 6}      # cabeçalho de captura "any" -> equivale a Ethernet (14 B)


def ler_pcap(caminho):
    with open(caminho, "rb") as f:
        g = f.read(24)
        if len(g) < 24:
            return 0, 0
        magic = struct.unpack("<I", g[:4])[0]
        e = "<" if magic in (0xA1B2C3D4, 0xA1B23C4D) else ">"
        link = struct.unpack(e + "I", g[20:24])[0]
        aj = AJUSTE.get(link, 0)
        n = b = 0
        while True:
            h = f.read(16)
            if len(h) < 16:
                break
            _, _, incl, orig = struct.unpack(e + "IIII", h)
            f.seek(incl, 1)
            n += 1
            b += orig - aj
    return n, b


def info(d):
    kv = dict(p.split("=") for p in (d / "info.txt").read_text().split())
    return float(kv["DUR"]), float(kv["INTERVALO"])


linhas = []
for cen, nome in CENARIOS:
    d = RES / cen
    if not d.exists():
        print(f"[aviso] sem dados de {nome}; pulando")
        continue
    dur, interv = info(d)
    rotas = {l.split()[0]: int(l.split()[1]) for l in (d / "rotas.txt").read_text().splitlines()}
    pk = by = 0
    for i in range(1, 8):
        n, b = ler_pcap(d / f"ctrl_r{i}.pcap")
        pk += n
        by += b
    rtt = re.search(r"= [\d.]+/([\d.]+)/", (d / "rtt.txt").read_text())
    f = re.search(r"(\d+) packets transmitted, (\d+) received", (d / "falha.txt").read_text())
    perdidos = int(f.group(1)) - int(f.group(2))
    linhas.append({
        "cenario": nome,
        "rotas_r1": rotas["r1"],
        "rotas_total": sum(rotas.values()),
        "pacotes_controle": pk,
        "bytes_controle": by,
        "pacotes_por_s": round(pk / dur, 2),
        "bytes_por_s": round(by / dur, 1),
        "rtt_medio_ms": float(rtt.group(1)),
        "pacotes_perdidos": perdidos,
        "convergencia_s": round(perdidos * interv, 1),
    })

with open(RES / "resumo.csv", "w", newline="") as fcsv:
    w = csv.DictWriter(fcsv, fieldnames=list(linhas[0]))
    w.writeheader()
    w.writerows(linhas)
for l in linhas:
    print(l)

METRICAS = [
    ("rotas_total", "Rotas nas tabelas (soma dos 7 roteadores)", "rotas"),
    ("pacotes_por_s", "Pacotes de controle por segundo", "pacotes/s"),
    ("bytes_por_s", "Taxa de transmissão de controle", "bytes/s"),
    ("rtt_medio_ms", "Delay fim a fim h1→h2 (RTT médio)", "ms"),
    ("convergencia_s", "Tempo de convergência após falha", "s (perdas × intervalo)"),
]
nomes = [l["cenario"] for l in linhas]
cores = CORES[:len(nomes)]


def barras(ax, chave, titulo, unidade):
    vals = [l[chave] for l in linhas]
    ax.bar(nomes, vals, color=cores)
    ax.set_title(titulo, fontsize=10)
    ax.set_ylabel(unidade)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:g}", ha="center", va="bottom", fontsize=9)


fig, axs = plt.subplots(2, 3, figsize=(14, 7))
for ax, (k, t, u) in zip(axs.flat, METRICAS):
    barras(ax, k, t, u)
axs.flat[-1].axis("off")
fig.suptitle("Comparação: RIP × OSPF × Q-routing", fontsize=13)
fig.tight_layout()
fig.savefig(GRAF / "comparacao.png", dpi=150)
for k, t, u in METRICAS:
    fig, ax = plt.subplots(figsize=(5.5, 4))
    barras(ax, k, t, u)
    fig.tight_layout()
    fig.savefig(GRAF / f"{k}.png", dpi=150)
    plt.close(fig)
print("Gráficos salvos em metricas/graficos/")