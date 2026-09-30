#!/usr/bin/env python3
"""Gera o bird.conf de OSPF de cada roteador em ospf/configs/."""
from pathlib import Path

HELLO, DEAD = 2, 8   # temporizadores OSPF (s); documente no README

# interface -> custo OSPF (enlaces entre roteadores)
ENLACES = {
    1: {"eth1": 10, "eth2": 10, "eth3": 10},
    2: {"eth1": 10, "eth2": 10, "eth3": 20},
    3: {"eth1": 10, "eth2": 20, "eth3": 10},
    4: {"eth1": 10, "eth2": 10},
    5: {"eth1": 10, "eth2": 20, "eth3": 20, "eth4": 10},
    6: {"eth1": 10, "eth2": 10},
    7: {"eth1": 10, "eth2": 10, "eth3": 10},
}
# interfaces de LAN: anunciadas, mas sem enviar mensagens OSPF
LANS = {1: ["eth4"], 7: ["eth4"]}

saida = Path(__file__).parent / "configs"
saida.mkdir(exist_ok=True)

for n, ifaces in ENLACES.items():
    linhas = [
        f"router id 10.255.0.{n};",
        "",
        "protocol device { }",
        "",
        "protocol kernel {",
        "    ipv4 { import none; export all; };",
        "}",
        "",
        "protocol ospf v2 ospf1 {",
        "    ipv4 { import all; export all; };",
        "    area 0 {",
    ]
    for nome, custo in ifaces.items():
        linhas.append(
            f'        interface "{nome}" {{ type ptp; cost {custo}; '
            f'hello {HELLO}; dead {DEAD}; }};'
        )
    for nome in LANS.get(n, []) + ["lo"]:
        linhas.append(f'        interface "{nome}" {{ stub yes; }};')
    linhas += ["    };", "}", ""]
    (saida / f"r{n}.conf").write_text("\n".join(linhas))
    print(f"gerado ospf/configs/r{n}.conf")