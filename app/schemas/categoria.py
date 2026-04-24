from pydantic import BaseModel, field_validator
from typing import Optional

class CategoriaBase(BaseModel):
    nombre:      str
    modulos:     float
    descripcion: Optional[str] = None
    estado:      str = "activo"

    @field_validator("modulos")
    @classmethod
    def modulos_positivos(cls, v):
        if v <= 0:
            raise ValueError("Los módulos deben ser mayor a cero")
        return v

    @field_validator("estado")
    @classmethod
    def estado_valido(cls, v):
        if v not in ("activo", "baja"):
            raise ValueError("Estado debe ser 'activo' o 'baja'")
        return v

class CategoriaCreate(CategoriaBase):
    codigo: str

    @field_validator("codigo")
    @classmethod
    def codigo_mayusculas(cls, v):
        return v.strip().upper()

class CategoriaUpdate(CategoriaBase):
    nombre:      Optional[str]   = None
    modulos:     Optional[float] = None
    estado:      Optional[str]   = None

class CategoriaOut(CategoriaBase):
    id:     int
    codigo: str
    model_config = {"from_attributes": True}