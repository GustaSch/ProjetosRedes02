#!/usr/bin/env python3
"""Gera o bird.conf de RIP de cada roteador em rip/configs/."""
from pathlib import Path

UPDATE, TIMEOUT, GARBAGE = 5, 20, 20   # segundos; documente no README

# interfaces de enlace de cada roteador (mesmas do OSPF)
ENLACES = {
    1: ["eth1", "eth2", "eth3"],
    2: ["eth1", "eth2", "eth3"],
    3: ["eth1", "eth2", "eth3"],
    4: ["eth1", "eth2"],
    5: ["eth1", "eth2", "eth3", "eth4"],
    6: ["eth1", "eth2"],
    7: ["eth1", "eth2", "eth3"],
}
LANS = {1: ["eth4"], 7: ["eth4"]}   # anunciadas, mas passivas

saida = Path(__file__).parent / "configs"
saida.mkdir(exist_ok=True)

for n, ifaces in ENLACES.items():
    lans = LANS.get(n, [])
    anunciadas = ifaces + lans + ["lo"]
    lista = ", ".join(f'"{i}"' for i in anunciadas)
    linhas = [
        f"router id 10.255.0.{n};",
        "",
        "protocol device { }",
        "",
        "protocol direct {",
        "    ipv4;",
        f"    interface {lista};",
        "}",
        "",
        "protocol kernel {",
        "    ipv4 { import none; export where source = RTS_RIP; };",
        "}",
        "",
        "protocol rip rip1 {",
        "    ipv4 { import all; export all; };",
    ]
    for nome in ifaces:
        linhas.append(
            f'    interface "{nome}" {{ version 2; update time {UPDATE}; '
            f'timeout time {TIMEOUT}; garbage time {GARBAGE}; }};'
        )
    for nome in lans:
        linhas.append(f'    interface "{nome}" {{ passive; }};')
    linhas += ["}", ""]
    (saida / f"r{n}.conf").write_text("\n".join(linhas))
    print(f"gerado rip/configs/r{n}.conf")