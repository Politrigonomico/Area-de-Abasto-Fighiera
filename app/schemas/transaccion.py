from pydantic import BaseModel
from typing import Optional
from datetime import date

class TransaccionBase(BaseModel):
    abastecedor_id: int
    tipo:           str        # 'cargo' | 'pago'
    periodo:        Optional[str]   = None   # 'YYYY-MM'
    importe:        float
    fecha:          date
    comprobante:    Optional[str]   = None
    descripcion:    Optional[str]   = None

class PagoCreate(BaseModel):
    abastecedor_id: int
    importe:        float
    fecha:          date
    comprobante:    Optional[str] = None
    descripcion:    Optional[str] = None

class TransaccionOut(TransaccionBase):
    id:                    int
    modulos_aplicados:     Optional[float] = None
    valor_modulo_snapshot: float
    parametro_id:          int
    model_config = {"from_attributes": True}