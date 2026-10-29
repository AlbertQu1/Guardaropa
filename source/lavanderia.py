"""Agrupa prendas en cargas de lavado compatibles a partir de su etiqueta de cuidado. Sin IA."""

from source import guia_cuidado, simbolos_cuidado

CLAROS = {"blanco", "crema", "hueso", "marfil", "beige", "arena", "gris claro", "azul claro", "rosa", "celeste", "amarillo"}
OSCUROS = {"negro", "azul marino", "marino", "gris oscuro", "mezclilla", "denim", "café", "cafe", "marrón",
           "vino", "guinda", "verde olivo", "olivo", "verde militar", "morado"}
FIBRAS_DELICADAS = {"lana", "seda", "cachemira", "cashmere", "viscosa", "rayón", "rayon", "angora", "mohair", "encaje", "lino"}
TEMP_DEFAULT = 30  # sin dato: lavar en frio es lo seguro


def _grupo_color(p: dict) -> str:
    c = (p.get("colores") or [""])[0].lower().strip()
    if c in CLAROS:
        return "claros"
    if c in OSCUROS:
        return "oscuros"
    return "colores"


def _es_delicada(p: dict) -> bool:
    fibras = {(f.get("fibra") or "").lower() for f in (p.get("composicion") or [])}
    return bool(fibras & FIBRAS_DELICADAS)


def _avisos(cuidado: dict) -> list[str]:
    a = []
    if cuidado.get("blanqueador") == "no":
        a.append("sin blanqueador")
    elif cuidado.get("blanqueador") == "sin_cloro":
        a.append("blanqueador sin cloro")
    if cuidado.get("secadora") == "no":
        a.append("no a la secadora")
    elif cuidado.get("secadora") == "sin_calor":
        a.append("secadora sin calor")
    elif cuidado.get("secadora") == "baja":
        a.append("secadora a temperatura baja")
    if cuidado.get("secado") == "plano":
        a.append("secar en plano")
    elif cuidado.get("secado") == "sombra":
        a.append("secar a la sombra")
    if cuidado.get("planchado") == "no":
        a.append("no planchar")
    elif cuidado.get("planchado"):
        a.append(f"planchar a temperatura {cuidado['planchado']}")
    if cuidado.get("notas"):
        a.append(cuidado["notas"])
    return a


NOMBRES_COLOR = {"claros": "Blancos y claros", "oscuros": "Oscuros", "colores": "Colores"}


def agrupar(prendas: list[dict]) -> list[dict]:
    cargas: dict[tuple, dict] = {}

    def agregar(clave, nombre, tipo, item, temperatura=None, ciclo=None, consejo=""):
        carga = cargas.setdefault(clave, {"nombre": nombre, "tipo": tipo, "temperatura": temperatura,
                                          "ciclo": ciclo, "consejo": consejo, "prendas": []})
        if temperatura is not None:
            carga["temperatura"] = min(carga["temperatura"] or temperatura, temperatura)
        carga["prendas"].append(item)

    for p in prendas:
        cuidado = p.get("cuidado") or {}
        estimado = False
        if not cuidado.get("simbolos") and not cuidado.get("lavado"):
            # Sin etiqueta pero con tela conocida: usar el cuidado tipico de esa tela
            fibras = [f.get("fibra") or "" for f in (p.get("composicion") or [])]
            e = guia_cuidado.estimar(fibras) if fibras else None
            if e:
                cuidado = {**simbolos_cuidado.traducir(e["simbolos"]), "notas": cuidado.get("notas") or ""}
                estimado = True
        avisos = _avisos(cuidado) + (["cuidado estimado por la tela"] if estimado else [])
        item = {"id": p["id"], "subcategoria": p.get("subcategoria"), "categoria": p["categoria"],
                "foto": p.get("foto_recortada") or p.get("foto_original"), "avisos": avisos}
        if not cuidado.get("simbolos") and not cuidado.get("lavado"):
            agregar(("sin_info",), "Sin etiqueta registrada", "sin_info", item,
                    consejo="Escanea su etiqueta o elige su tela en Cuidado. Mientras, lávalas en frío y en ciclo delicado.")
        elif cuidado.get("lavado") == "no_lavar" or cuidado.get("tintoreria") == "solo":
            agregar(("tintoreria",), "Tintorería", "tintoreria", item, consejo="No van a la lavadora.")
        elif cuidado.get("lavado") == "mano":
            agregar(("mano",), "A mano", "mano", item, temperatura=cuidado.get("temperatura_max") or TEMP_DEFAULT,
                    consejo="Agua fría o tibia, sin tallar fuerte ni retorcer.")
        else:
            grupo = _grupo_color(p)
            delicada = _es_delicada(p)
            nombre = NOMBRES_COLOR[grupo] + (" · delicado" if delicada else "")
            agregar(("maquina", grupo, delicada), nombre, "maquina", item,
                    temperatura=cuidado.get("temperatura_max") or TEMP_DEFAULT,
                    ciclo="delicado" if delicada else "normal")

    orden = {"maquina": 0, "mano": 1, "tintoreria": 2, "sin_info": 3}
    return sorted(cargas.values(), key=lambda c: (orden[c["tipo"]], c["nombre"]))
