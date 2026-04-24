from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date

class AbastecedorBase(BaseModel):
    razon_social:          str
    titular:               str
    cuit:                  Optional[str] = None
    telefono_principal:    Optional[str] = None
    telefono_alternativo:  Optional[str] = None
    email:                 Optional[str] = None
    domicilio:             Optional[str] = None
    localidad:             Optional[str] = None
    provincia:             str = "Santa Fe"
    patente:               Optional[str] = None
    descripcion_vehiculo:  Optional[str] = None
    observaciones:         Optional[str] = None
    categoria_ids:         list[int] = []   # reemplaza categoria_id
    estado:                str = "activo"

    @field_validator("patente")
    @classmethod
    def patente_mayusculas(cls, v):
        if v:
            return v.strip().upper()
        return v

class AbastecedorCreate(AbastecedorBase):
    pass

class AbastecedorUpdate(AbastecedorBase):
    razon_social:  Optional[str]   = None
    titular:       Optional[str]   = None
    categoria_ids: Optional[list[int]] = None
    estado:        Optional[str]   = None

class AbastecedorOut(AbastecedorBase):
    id:             int
    fecha_alta:     Optional[date] = None
    categoria_ids:  list[int]      = []
    model_config = {"from_attributes": True}

class AbastecedorConSaldo(AbastecedorOut):
    saldo:             float = 0
    meses_adeudados:   int   = 0
    periodos_deudores: list  = []