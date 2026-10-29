"""Arma tu outfit: dada una prenda base (y prendas fijadas), ordena candidatos por slot.
Sin IA: reglas de formalidad, color, ocasion, clima, estampado y rotacion."""

from datetime import date

import params

SLOTS = ["top", "bottom", "calzado", "chamarra", "accesorio"]
SLOTS_OPCIONALES = {"chamarra", "accesorio"}
# La rotacion es desempate: nunca debe ganarle a la coherencia del outfit
PESOS = {"formalidad": 0.32, "color": 0.24, "ocasion": 0.18, "clima": 0.08, "estampado": 0.08, "rotacion": 0.10}
DIAS_ROTACION_MAX = 60  # a partir de aqui la prenda ya cuenta como "olvidada"


def slots_para(base_categoria: str) -> list[str]:
    if base_categoria == "vestido_completo":
        return ["calzado", "chamarra", "accesorio"]
    return [s for s in SLOTS if s != base_categoria]


def _color_principal(p: dict) -> str | None:
    return p["colores"][0].lower().strip() if p.get("colores") else None


def _es_neutro(color: str | None) -> bool:
    return color is None or color in params.COLORES_NEUTROS


def _es_liso(p: dict) -> bool:
    return (p.get("estampado") or "liso").lower().strip() in ("liso", "", "sin estampado")


def _dias_sin_usar(p: dict, hoy: date) -> int:
    if p.get("ultimo_uso"):
        return (hoy - p["ultimo_uso"]).days
    return DIAS_ROTACION_MAX  # nunca usada: maxima prioridad de rotacion


def puntuar(cand: dict, elegidas: list[dict], hoy: date) -> tuple[float, list[str]]:
    razones: list[str] = []

    forms = [p["formalidad"] or 3 for p in elegidas]
    media = sum(forms) / len(forms)
    s_form = 1 - abs((cand["formalidad"] or 3) - media) / 4
    if s_form >= 0.85:
        razones.append("mismo nivel de formalidad")

    color = _color_principal(cand)
    fuertes = {c for c in (_color_principal(p) for p in elegidas) if not _es_neutro(c)}
    if _es_neutro(color):
        s_color = 1.0
        razones.append("color neutro, combina con todo")
    elif not fuertes:
        s_color = 1.0
        razones.append(f"el {color} resalta sobre neutros")
    elif color in fuertes:
        s_color = 0.8
    else:
        s_color = 0.4

    base = elegidas[0]
    # Ocasion comun a todo lo ya elegido (si no hay comun, la de la base)
    oc_elegidas = [set(p.get("ocasiones") or []) for p in elegidas if p.get("ocasiones")]
    oc_base = set.intersection(*oc_elegidas) if oc_elegidas else set()
    if not oc_base and oc_elegidas:
        oc_base = oc_elegidas[0]
    oc_cand = set(cand.get("ocasiones") or [])
    s_ocasion = 1.0 if not oc_base or not oc_cand or oc_base & oc_cand else 0.3
    if oc_base & oc_cand:
        razones.append("para " + ", ".join(sorted(oc_base & oc_cand)[:2]))

    t_base, t_cand = set(base.get("temporada") or []), set(cand.get("temporada") or [])
    s_clima = 1.0 if not t_base or not t_cand or t_base & t_cand else 0.4

    estampadas = sum(1 for p in elegidas if not _es_liso(p))
    s_estampado = 1.0 if _es_liso(cand) or estampadas == 0 else 0.5

    dias = _dias_sin_usar(cand, hoy)
    s_rot = min(dias, DIAS_ROTACION_MAX) / DIAS_ROTACION_MAX
    if not cand.get("ultimo_uso"):
        razones.append("aún no la estrenas")
    elif dias >= 21:
        razones.append(f"no la usas hace {dias} días")

    total = (
        PESOS["formalidad"] * s_form + PESOS["color"] * s_color + PESOS["ocasion"] * s_ocasion
        + PESOS["clima"] * s_clima + PESOS["estampado"] * s_estampado + PESOS["rotacion"] * s_rot
    )
    return round(total, 3), razones[:3]


def armar(base: dict, fijas: list[dict], prendas: list[dict], hoy: date | None = None,
          n: int = params.OPCIONES_POR_SLOT) -> dict:
    """prendas: todo el closet activo (dicts de v_prendas_uso). Devuelve opciones por slot."""
    hoy = hoy or date.today()
    elegidas = [base] + fijas
    usados = {p["id"] for p in elegidas}
    fijas_por_slot = {p["categoria"]: p for p in fijas}
    resultado = []
    for slot in slots_para(base["categoria"]):
        if slot in fijas_por_slot:
            resultado.append({"slot": slot, "opcional": slot in SLOTS_OPCIONALES,
                              "fija": fijas_por_slot[slot]["id"], "opciones": []})
            continue
        candidatos = [p for p in prendas if p["categoria"] == slot and p["id"] not in usados]
        puntuados = []
        for c in candidatos:
            score, razones = puntuar(c, elegidas, hoy)
            puntuados.append({"prenda": c, "score": score, "razones": razones})
        puntuados.sort(key=lambda x: x["score"], reverse=True)
        resultado.append({"slot": slot, "opcional": slot in SLOTS_OPCIONALES, "fija": None,
                          "opciones": puntuados[:n]})
    return {"base": base, "slots": resultado}
