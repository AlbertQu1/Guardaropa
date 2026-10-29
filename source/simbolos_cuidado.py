"""Diccionario de simbolos de cuidado textil (ISO 3758 / GINETEX).
La IA solo identifica cuales codigos aparecen en la etiqueta; la traduccion a instrucciones
es determinista y sale de aqui, asi el resultado es consistente."""

# codigo -> (grupo, campo, valor, descripcion para mostrar)
SIMBOLOS: dict[str, tuple[str, str, object, str]] = {
    # Lavado (tina)
    "lavado_95": ("lavado", "temperatura_max", 95, "Lavar a máquina máx. 95 °C"),
    "lavado_70": ("lavado", "temperatura_max", 70, "Lavar a máquina máx. 70 °C"),
    "lavado_60": ("lavado", "temperatura_max", 60, "Lavar a máquina máx. 60 °C"),
    "lavado_60_suave": ("lavado", "temperatura_max", 60, "Lavar máx. 60 °C, ciclo suave"),
    "lavado_50": ("lavado", "temperatura_max", 50, "Lavar a máquina máx. 50 °C"),
    "lavado_40": ("lavado", "temperatura_max", 40, "Lavar a máquina máx. 40 °C"),
    "lavado_40_suave": ("lavado", "temperatura_max", 40, "Lavar máx. 40 °C, ciclo suave"),
    "lavado_40_muy_suave": ("lavado", "temperatura_max", 40, "Lavar máx. 40 °C, ciclo muy suave"),
    "lavado_30": ("lavado", "temperatura_max", 30, "Lavar a máquina máx. 30 °C"),
    "lavado_30_suave": ("lavado", "temperatura_max", 30, "Lavar máx. 30 °C, ciclo suave"),
    "lavado_30_muy_suave": ("lavado", "temperatura_max", 30, "Lavar máx. 30 °C, ciclo muy suave"),
    "lavado_mano": ("lavado", "lavado", "mano", "Lavar a mano (máx. 40 °C)"),
    "no_lavar": ("lavado", "lavado", "no_lavar", "No lavar"),
    # Blanqueador (triangulo)
    "blanqueador_cualquiera": ("blanqueador", "blanqueador", "si", "Admite cualquier blanqueador"),
    "blanqueador_sin_cloro": ("blanqueador", "blanqueador", "sin_cloro", "Solo blanqueador sin cloro"),
    "no_blanqueador": ("blanqueador", "blanqueador", "no", "No usar blanqueador"),
    # Secadora (cuadro con circulo)
    "secadora_normal": ("secadora", "secadora", "alta", "Secadora a temperatura normal"),
    "secadora_baja": ("secadora", "secadora", "baja", "Secadora a temperatura baja"),
    "secadora_sin_calor": ("secadora", "secadora", "sin_calor", "Secadora sin calor"),
    "no_secadora": ("secadora", "secadora", "no", "No usar secadora"),
    # Secado natural (cuadro con lineas)
    "secar_colgado": ("secado", "secado", "colgado", "Secar colgado"),
    "secar_escurriendo": ("secado", "secado", "escurrir", "Secar colgado sin exprimir"),
    "secar_plano": ("secado", "secado", "plano", "Secar en plano"),
    "secar_sombra": ("secado", "secado", "sombra", "Secar a la sombra"),
    "no_exprimir": ("secado", "notas", "no exprimir", "No exprimir ni retorcer"),
    # Planchado
    "planchar_alta": ("planchado", "planchado", "alta", "Planchar máx. 200 °C"),
    "planchar_media": ("planchado", "planchado", "media", "Planchar máx. 150 °C"),
    "planchar_baja": ("planchado", "planchado", "baja", "Planchar máx. 110 °C, sin vapor"),
    "no_planchar": ("planchado", "planchado", "no", "No planchar"),
    "no_vapor": ("planchado", "notas", "sin vapor", "No usar vapor"),
    # Limpieza profesional (circulo)
    "tintoreria_p": ("tintoreria", "tintoreria", "si", "Limpieza en seco (P)"),
    "tintoreria_f": ("tintoreria", "tintoreria", "si", "Limpieza en seco, solventes suaves (F)"),
    "tintoreria_a": ("tintoreria", "tintoreria", "si", "Limpieza en seco, cualquier solvente (A)"),
    "limpieza_humeda_w": ("tintoreria", "tintoreria", "si", "Limpieza húmeda profesional (W)"),
    "no_tintoreria": ("tintoreria", "tintoreria", "no", "No limpiar en seco"),
}

CODIGOS = list(SIMBOLOS)


def describir(codigos: list[str]) -> list[dict]:
    """Para mostrar en la app: cada simbolo con su grupo y significado oficial."""
    return [{"codigo": c, "grupo": SIMBOLOS[c][0], "descripcion": SIMBOLOS[c][3]} for c in codigos if c in SIMBOLOS]


def traducir(codigos: list[str]) -> dict:
    """Codigos detectados -> campos de cuidado (lavado, temperatura_max, blanqueador, ...)."""
    cuidado: dict = {"simbolos": [c for c in codigos if c in SIMBOLOS]}
    notas: list[str] = []
    for c in cuidado["simbolos"]:
        _, campo, valor, _ = SIMBOLOS[c]
        if campo == "notas":
            notas.append(str(valor))
        elif campo == "temperatura_max":
            cuidado["lavado"] = cuidado.get("lavado") or "maquina"
            cuidado["temperatura_max"] = min(cuidado.get("temperatura_max") or 999, valor)
        else:
            cuidado[campo] = valor
    if cuidado.get("lavado") == "mano":
        cuidado["temperatura_max"] = cuidado.get("temperatura_max") or 40
    cuidado["notas_simbolos"] = notas
    return cuidado
