
"""
modelos.py
Define las estructuras de datos principales del sistema ganadero
usando dataclasses: Cow (vaca), MilkRecord (registro de producción)
y User (usuario). Incluye validaciones básicas.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Tuple
from configuracion import AppConfig, QualityLevel


# -------------------------------------------------------------------------
# MODELO: VACA
# -------------------------------------------------------------------------
@dataclass
class Cow:
    id: Optional[int]
    tag: str
    name: str
    breed: Optional[str] = None
    dob: Optional[str] = None
    notes: Optional[str] = None

    def validate(self) -> Tuple[bool, str]:
        """Valida los datos de la vaca antes de insertarla en la base de datos."""
        if not self.tag or len(self.tag.strip()) == 0:
            return False, "TAG es obligatorio"
        if not self.name or len(self.name.strip()) == 0:
            return False, "Nombre es obligatorio"
        if len(self.tag) > 50:
            return False, "TAG no puede exceder 50 caracteres"
        if len(self.name) > 200:
            return False, "Nombre no puede exceder 200 caracteres"

        if self.dob:
            try:
                dob_date = datetime.strptime(self.dob, AppConfig.DATE_FORMAT).date()
                if dob_date > date.today():
                    return False, "Fecha de nacimiento no puede ser futura"
            except ValueError:
                return False, "Formato de fecha inválido (YYYY-MM-DD)"
        return True, ""


# -------------------------------------------------------------------------
# MODELO: REGISTRO DE LECHE
# -------------------------------------------------------------------------
@dataclass
class MilkRecord:
    id: Optional[int]
    cow_id: int
    fecha: str
    litros: float
    calidad: Optional[str] = None
    observaciones: Optional[str] = None

    def validate(self) -> Tuple[bool, str]:
        """Valida el registro de producción antes de guardarlo."""
        if self.cow_id is None or self.cow_id <= 0:
            return False, "ID de vaca inválido"

        try:
            fecha_date = datetime.strptime(self.fecha, AppConfig.DATE_FORMAT).date()
            if fecha_date > date.today():
                return False, "Fecha no puede ser futura"
        except ValueError:
            return False, "Formato de fecha inválido (YYYY-MM-DD)"

        if not (AppConfig.MIN_LITERS <= self.litros <= AppConfig.MAX_LITERS):
            return False, f"Litros debe estar entre {AppConfig.MIN_LITERS} y {AppConfig.MAX_LITERS}"

        allowed = [q.value for q in QualityLevel]
        if self.calidad and self.calidad not in allowed:
            return False, f"Calidad debe ser una de: {allowed}"

        return True, ""


# -------------------------------------------------------------------------
# MODELO: USUARIO
# -------------------------------------------------------------------------
@dataclass
class User:
    id: Optional[int]
    username: str
    role: str = "user"
    active: int = 1
    created_at: Optional[str] = None
