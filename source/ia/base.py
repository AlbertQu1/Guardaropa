"""Interfaz unica de IA. La app solo habla con esto; cambiar de Gemini a una IA
local es agregar otro provider y cambiar IA_PROVIDER en .env."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EtiquetasPrenda:
    categoria: str
    subcategoria: str | None = None
    colores: list[str] = field(default_factory=list)
    estampado: str | None = None
    material: str | None = None
    formalidad: int | None = None  # 1 (muy casual) a 5 (muy formal)
    temporada: list[str] = field(default_factory=list)
    ocasiones: list[str] = field(default_factory=list)
    descripcion: str = ""
    marca: str | None = None  # solo si se ve el logo


@dataclass
class Fibra:
    fibra: str
    porcentaje: int | None = None


@dataclass
class CuidadoPrenda:
    composicion: list[Fibra] = field(default_factory=list)
    simbolos: list[str] = field(default_factory=list)  # codigos de source/simbolos_cuidado.py
    lavado: str | None = None  # maquina | mano | no_lavar
    temperatura_max: int | None = None  # grados C
    blanqueador: str | None = None  # si | no | sin_cloro
    secadora: str | None = None  # no | sin_calor | baja | alta
    secado: str | None = None  # tendido | plano | sombra | escurrir | colgado
    planchado: str | None = None  # no | baja | media | alta
    tintoreria: str | None = None  # no | si | solo
    notas: str = ""
    marca: str | None = None  # la etiqueta interior suele traerlas
    talla: str | None = None


@dataclass
class PropuestaOutfit:
    prendas: list[int]  # ids de guardarropa.prendas
    nombre: str
    explicacion: str


class IAProvider(ABC):
    @abstractmethod
    def etiquetar_prenda(self, foto: bytes, mime: str) -> EtiquetasPrenda:
        """Analiza la foto de una prenda y devuelve sus etiquetas."""

    @abstractmethod
    def leer_etiqueta_cuidado(self, foto: bytes, mime: str) -> CuidadoPrenda:
        """Lee la etiqueta interior: composicion de la tela y simbolos de lavado."""

    @abstractmethod
    def proponer_outfits(self, pedido: str, candidatos: list[dict], n: int = 3) -> list[PropuestaOutfit]:
        """Arma outfits usando solo las prendas candidatas."""

    @abstractmethod
    def generar_tryon(self, foto_usuario: bytes, fotos_prendas: list[bytes]) -> bytes:
        """Devuelve una imagen (PNG/JPEG) del usuario vistiendo las prendas."""
