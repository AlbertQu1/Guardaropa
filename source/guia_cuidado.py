"""Guia de cuidado: como leer los simbolos, cuidado tipico por tela y por articulo de la casa.
Tambien estima los simbolos de una prenda sin etiqueta (o ilegible) a partir de su tela. Sin IA."""

import unicodedata

from source.simbolos_cuidado import SIMBOLOS

GRUPOS = [
    {"grupo": "lavado", "nombre": "Lavado", "como_leer":
        "La tina. El número es la temperatura máxima del agua. Una raya debajo = ciclo suave; "
        "dos rayas = muy suave. La mano = solo a mano. Tachada = no lavar con agua."},
    {"grupo": "blanqueador", "nombre": "Blanqueador", "como_leer":
        "El triángulo. Vacío = cualquier blanqueador (incluye cloro). Con dos rayas = solo sin cloro "
        "(oxigenado). Tachado = nada de blanqueador."},
    {"grupo": "secadora", "nombre": "Secadora", "como_leer":
        "Cuadro con círculo. Un punto = calor bajo, dos puntos = normal, círculo relleno = sin calor. "
        "Tachado = no meter a la secadora."},
    {"grupo": "secado", "nombre": "Secado natural", "como_leer":
        "Cuadro sin círculo. Curva arriba = colgado; tres rayas verticales = colgado escurriendo, sin "
        "exprimir; raya horizontal = extendido en plano; rayas diagonales en la esquina = a la sombra."},
    {"grupo": "planchado", "nombre": "Planchado", "como_leer":
        "La plancha. Un punto = baja (110 °C), dos = media (150 °C), tres = alta (200 °C). "
        "Tachada = no planchar."},
    {"grupo": "tintoreria", "nombre": "Tintorería", "como_leer":
        "El círculo es para el profesional. La letra le dice qué solvente usar (P, F, A) o W para "
        "limpieza húmeda. Tachado = no limpiar en seco. Si solo ves este símbolo, llévala a tintorería."},
]

# Telas: simbolos tipicos (conservadores) + consejos. "alias" sirve para reconocer lo que trae la etiqueta.
TELAS = [
    {"id": "algodon", "nombre": "Algodón", "alias": ["algodon", "cotton", "coton", "pima", "popelina", "oxford", "pique"],
     "descripcion": "Fibra natural, resistente y fresca. Encoge con calor alto.",
     "simbolos": ["lavado_40", "blanqueador_sin_cloro", "secadora_baja", "secar_colgado", "planchar_alta"],
     "consejos": ["Los blancos de algodón aguantan 60 °C; los de color, 30–40 °C para que no se destiñan.",
                  "La secadora alta lo encoge: usa calor bajo o sácalo un poco húmedo.",
                  "Se plancha mejor ligeramente húmedo."]},
    {"id": "mezclilla", "nombre": "Mezclilla", "alias": ["mezclilla", "denim", "jean", "jeans"],
     "descripcion": "Algodón grueso teñido con índigo. Suelta tinte, sobre todo las primeras lavadas.",
     "simbolos": ["lavado_30", "no_blanqueador", "secar_colgado", "planchar_media"],
     "consejos": ["Lávala al revés y en frío, con otras prendas oscuras.",
                  "No hace falta lavarla en cada uso: cada 4–6 usos basta.",
                  "Al aire conserva mejor el color y el tamaño que en secadora."]},
    {"id": "poliester", "nombre": "Poliéster", "alias": ["poliester", "polyester", "pes", "microfibra"],
     "descripcion": "Sintético, no se arruga ni encoge, seca rápido. Guarda olores.",
     "simbolos": ["lavado_40", "blanqueador_sin_cloro", "secadora_baja", "planchar_baja"],
     "consejos": ["El calor alto lo deja brilloso o lo derrite: plancha baja.",
                  "Para olores (ropa deportiva), un poco de vinagre blanco en el enjuague."]},
    {"id": "nylon", "nombre": "Nylon / poliamida", "alias": ["nylon", "nailon", "poliamida", "polyamide", "pa"],
     "descripcion": "Sintético resistente y ligero (chamarras, medias, ropa deportiva).",
     "simbolos": ["lavado_30", "no_blanqueador", "secadora_baja", "planchar_baja"],
     "consejos": ["Se amarillenta con blanqueador.", "Seca muy rápido al aire."]},
    {"id": "elastano", "nombre": "Elastano / licra", "alias": ["elastano", "elastane", "spandex", "licra", "lycra", "ea", "el"],
     "descripcion": "La fibra que estira. Suele venir mezclada (2–5 %) y el calor la arruina.",
     "simbolos": ["lavado_30", "no_blanqueador", "no_secadora", "secar_colgado", "planchar_baja"],
     "consejos": ["Aunque sea poco porcentaje, manda: sin secadora ni plancha caliente.",
                  "Sin suavizante, que deja la fibra floja."]},
    {"id": "lino", "nombre": "Lino", "alias": ["lino", "linen", "li"],
     "descripcion": "Natural, muy fresco y se arruga mucho. Se suaviza con cada lavada.",
     "simbolos": ["lavado_40_suave", "blanqueador_sin_cloro", "no_secadora", "secar_colgado", "planchar_alta"],
     "consejos": ["Plánchalo húmedo y por el revés.", "La secadora lo encoge y lo arruga más."]},
    {"id": "lana", "nombre": "Lana", "alias": ["lana", "wool", "merino", "wo", "wv"],
     "descripcion": "Natural, abriga y casi no necesita lavarse. Con agua caliente o fricción se encoge (fieltra).",
     "simbolos": ["lavado_mano", "no_blanqueador", "no_secadora", "secar_plano", "planchar_media", "tintoreria_p"],
     "consejos": ["Agua fría, jabón para lana y sin tallar.", "No la exprimas: enróllala en una toalla para quitar el agua.",
                  "Sécala extendida para que no se estire.", "Entre usos, aírela; no hace falta lavarla seguido."]},
    {"id": "cachemira", "nombre": "Cachemira", "alias": ["cachemira", "cashmere", "cachemir"],
     "descripcion": "Lana muy fina de cabra. Suave, delicada y se hace bolitas.",
     "simbolos": ["lavado_mano", "no_blanqueador", "no_secadora", "secar_plano", "planchar_baja", "tintoreria_p"],
     "consejos": ["Igual que la lana pero con más cuidado.", "Quita las bolitas con un peine para suéter."]},
    {"id": "seda", "nombre": "Seda", "alias": ["seda", "silk", "se"],
     "descripcion": "Natural, brillante y muy delicada. Se mancha con agua y pierde color al sol.",
     "simbolos": ["lavado_mano", "no_blanqueador", "no_secadora", "secar_sombra", "planchar_baja", "tintoreria_p"],
     "consejos": ["Agua fría con jabón neutro, sin remojar mucho tiempo.", "Si la etiqueta dice solo tintorería, hazle caso."]},
    {"id": "viscosa", "nombre": "Viscosa / rayón", "alias": ["viscosa", "viscose", "rayon", "cv", "vi"],
     "descripcion": "Semi-sintética (de celulosa). Cae bonito pero se debilita mojada y encoge.",
     "simbolos": ["lavado_30_suave", "no_blanqueador", "no_secadora", "secar_colgado", "planchar_baja"],
     "consejos": ["No la talles ni la exprimas mientras está mojada.", "Plancha por el revés, aún húmeda."]},
    {"id": "modal", "nombre": "Modal / lyocell", "alias": ["modal", "lyocell", "tencel", "md", "cly"],
     "descripcion": "Parientes de la viscosa, más resistentes. Muy suaves.",
     "simbolos": ["lavado_30_suave", "no_blanqueador", "secadora_baja", "secar_colgado", "planchar_baja"],
     "consejos": ["Ciclo suave y al revés para que no se hagan bolitas."]},
    {"id": "acrilico", "nombre": "Acrílico", "alias": ["acrilico", "acrylic", "pan"],
     "descripcion": "Sintético que imita la lana (suéteres, cobijas). Se deforma con calor.",
     "simbolos": ["lavado_30_suave", "no_blanqueador", "secadora_baja", "secar_plano", "planchar_baja"],
     "consejos": ["Los suéteres, secos en plano para que no se estiren."]},
    {"id": "plumon", "nombre": "Plumón / pluma", "alias": ["plumon", "pluma", "plumas", "down", "feather"],
     "descripcion": "Relleno de chamarras y edredones. El riesgo es que se apelmace o no seque bien.",
     "simbolos": ["lavado_30_suave", "no_blanqueador", "secadora_baja", "no_planchar"],
     "consejos": ["Detergente suave, poco y bien enjuagado.",
                  "Secadora a calor bajo con 2–3 pelotas de tenis para esponjar; tiene que quedar totalmente seco."]},
    {"id": "piel", "nombre": "Piel / cuero", "alias": ["piel", "cuero", "leather", "piel sintetica", "polipiel", "vinipiel"],
     "descripcion": "No se lava con agua. La sintética (polipiel) se limpia igual de fácil, pero se agrieta con calor.",
     "simbolos": ["no_lavar", "no_blanqueador", "no_secadora", "no_planchar"],
     "consejos": ["Limpia con un trapo apenas húmedo y sécala a la sombra.", "Hidrata la piel natural con crema 2–3 veces al año.",
                  "Manchas fuertes: con un especialista en piel, no tintorería común."]},
    {"id": "gamuza", "nombre": "Gamuza / ante", "alias": ["gamuza", "ante", "suede", "nobuck"],
     "descripcion": "Piel con textura aterciopelada. El agua la mancha.",
     "simbolos": ["no_lavar", "no_blanqueador", "no_secadora", "no_planchar"],
     "consejos": ["Cepillo de gamuza en seco, siempre en la misma dirección.", "Aplica impermeabilizante antes de usarla."]},
    {"id": "desconocida", "nombre": "No sé la tela", "alias": ["desconocida", "no se", "otra"],
     "descripcion": "Sin etiqueta ni idea de la fibra: trátala como delicada, es lo que no arruina nada.",
     "simbolos": ["lavado_30_suave", "no_blanqueador", "no_secadora", "secar_colgado", "planchar_baja"],
     "consejos": ["Primera lavada sola o con oscuros, por si destiñe: moja una esquina y presiónala con un trapo blanco.",
                  "Si se siente como lana o seda, mejor a mano.",
                  "Prueba la plancha en una parte que no se vea."]},
]

# Articulos de la casa: frecuencia + pasos. Los simbolos son los tipicos; si traen etiqueta, manda la etiqueta.
HOGAR = [
    {"id": "sabanas", "nombre": "Sábanas y fundas", "frecuencia": "Cada 1–2 semanas (fundas, cada semana)",
     "simbolos": ["lavado_60", "blanqueador_sin_cloro", "secadora_baja", "planchar_media"],
     "consejos": ["40–60 °C si son de algodón: el calor elimina ácaros. Microfibra o satín, 30–40 °C.",
                  "No llenes la lavadora: las sábanas necesitan espacio para enjuagarse bien.",
                  "Sácalas en cuanto termine la secadora y dóblalas: se arrugan menos."]},
    {"id": "toallas", "nombre": "Toallas", "frecuencia": "Cada 3–4 usos",
     "simbolos": ["lavado_60", "blanqueador_sin_cloro", "secadora_normal"],
     "consejos": ["Lávalas solas: sueltan pelusa sobre el resto de la ropa.",
                  "Sin suavizante, porque les quita absorción. Media taza de vinagre en el enjuague las deja suaves.",
                  "Que queden bien secas antes de guardarlas para que no huelan a humedad."]},
    {"id": "cortinas", "nombre": "Cortinas", "frecuencia": "2–3 veces al año; aspíralas cada mes",
     "simbolos": ["lavado_30_suave", "no_blanqueador", "no_secadora", "secar_colgado", "planchar_baja"],
     "consejos": ["Quita ganchos y argollas antes de lavar.", "Ciclo delicado en frío y centrifugado bajo.",
                  "Cuélgalas aún húmedas en su lugar: el peso las alisa y no hay que plancharlas.",
                  "Blackout, terciopelo o con forro: mejor tintorería o solo aspirar."]},
    {"id": "edredon", "nombre": "Edredón o cobertor", "frecuencia": "2–3 veces al año (el duvet, cada mes)",
     "simbolos": ["lavado_40_suave", "no_blanqueador", "secadora_baja", "no_planchar"],
     "consejos": ["Si no cabe holgado en tu lavadora, llévalo a una lavandería de autoservicio con máquina grande.",
                  "Secadora a calor bajo con pelotas de tenis, varias vueltas, hasta que quede totalmente seco por dentro.",
                  "Relleno de plumón: ver la tela Plumón."]},
    {"id": "almohadas", "nombre": "Almohadas", "frecuencia": "Cada 3–6 meses",
     "simbolos": ["lavado_40_suave", "no_blanqueador", "secadora_baja"],
     "consejos": ["Revisa su etiqueta: las de espuma viscoelástica (memory foam) no se lavan; solo su funda.",
                  "Lava dos a la vez para que la lavadora quede balanceada.",
                  "Sécalas por completo; si quedan húmedas por dentro salen hongos."]},
    {"id": "cobijas", "nombre": "Cobijas y frazadas", "frecuencia": "Cada 1–2 meses en temporada",
     "simbolos": ["lavado_30_suave", "no_blanqueador", "secadora_baja", "no_planchar"],
     "consejos": ["Polar y borrega: agua fría y sin suavizante para que no se apelmacen.",
                  "Lana: ver la tela Lana (a mano o tintorería)."]},
    {"id": "protector", "nombre": "Protector de colchón", "frecuencia": "Cada 1–2 meses",
     "simbolos": ["lavado_40", "no_blanqueador", "secadora_baja", "no_planchar"],
     "consejos": ["Los impermeables tienen una capa plástica: nada de calor alto ni plancha."]},
    {"id": "manteles", "nombre": "Manteles y servilletas", "frecuencia": "Después de cada uso con manchas",
     "simbolos": ["lavado_60", "blanqueador_sin_cloro", "secadora_baja", "planchar_alta"],
     "consejos": ["Pretrata las manchas antes de que sequen (grasa: jabón de trastes).",
                  "No metas a la secadora algo con mancha: el calor la fija."]},
    {"id": "trapos", "nombre": "Trapos de cocina", "frecuencia": "Cada 2–3 días",
     "simbolos": ["lavado_60", "blanqueador_cualquiera", "secadora_normal"],
     "consejos": ["Lávalos aparte y caliente: acumulan bacterias.", "Sin suavizante para que sigan absorbiendo."]},
    {"id": "tapetes", "nombre": "Tapetes de baño", "frecuencia": "Cada semana",
     "simbolos": ["lavado_40", "no_blanqueador", "secadora_baja"],
     "consejos": ["Si tienen base de hule, nada de calor alto: se agrieta. Mejor al aire."]},
    {"id": "cojines", "nombre": "Fundas de cojines y sillón", "frecuencia": "Cada 2–3 meses",
     "simbolos": ["lavado_30", "no_blanqueador", "no_secadora", "secar_colgado"],
     "consejos": ["Cierra los cierres antes de lavar.", "Vuelve a ponerlas un poco húmedas: entran más fácil y no encogen."]},
]

# Para combinar varias fibras: de mas permisivo a mas restrictivo dentro de cada grupo.
ORDEN = {
    "lavado": ["lavado_95", "lavado_70", "lavado_60", "lavado_60_suave", "lavado_50", "lavado_40", "lavado_40_suave",
               "lavado_40_muy_suave", "lavado_30", "lavado_30_suave", "lavado_30_muy_suave", "lavado_mano", "no_lavar"],
    "blanqueador": ["blanqueador_cualquiera", "blanqueador_sin_cloro", "no_blanqueador"],
    "secadora": ["secadora_normal", "secadora_baja", "secadora_sin_calor", "no_secadora"],
    "secado": ["secar_colgado", "secar_sombra", "secar_escurriendo", "secar_plano"],
    "planchado": ["planchar_alta", "planchar_media", "planchar_baja", "no_planchar"],
    "tintoreria": ["tintoreria_a", "tintoreria_p", "tintoreria_f", "limpieza_humeda_w", "no_tintoreria"],
}
SUELTOS = {"no_exprimir", "no_vapor"}  # notas: se suman, no compiten


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower().strip())
    return "".join(c for c in t if not unicodedata.combining(c))


_POR_ALIAS = {_norm(a): t for t in TELAS for a in [t["id"], t["nombre"], *t["alias"]]}


def tela(fibra: str) -> dict | None:
    """Reconoce una fibra escrita como venga en la etiqueta ('Poliéster', 'COTTON', 'viscose')."""
    f = _norm(fibra)
    if f in _POR_ALIAS:
        return _POR_ALIAS[f]
    palabras = f.replace("/", " ").replace("-", " ").split()
    for alias, t in _POR_ALIAS.items():  # 'algodon organico', 'lana merino', 'piel sintetica'
        if len(alias) > 3 and (alias in palabras or f.startswith(alias)):
            return t
    return None


def estimar(fibras: list[str]) -> dict | None:
    """Simbolos sugeridos para una mezcla de fibras: en cada grupo gana el mas restrictivo.
    None si no se reconoce ninguna fibra."""
    telas = [t for t in (tela(f) for f in fibras) if t]
    if not telas:
        return None
    elegidos: dict[str, str] = {}
    sueltos: set[str] = set()
    for t in telas:
        for c in t["simbolos"]:
            if c in SUELTOS:
                sueltos.add(c)
                continue
            g = SIMBOLOS[c][0]
            if g not in elegidos or ORDEN[g].index(c) > ORDEN[g].index(elegidos[g]):
                elegidos[g] = c
    vistas = list(dict.fromkeys(t["nombre"] for t in telas))
    return {"simbolos": [*elegidos.values(), *sorted(sueltos)], "telas": vistas,
            "no_reconocidas": [f for f in fibras if not tela(f)]}


def guia() -> dict:
    return {"grupos": GRUPOS, "telas": [{k: v for k, v in t.items() if k != "alias"} for t in TELAS], "hogar": HOGAR}
