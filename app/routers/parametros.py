from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from pydantic import BaseModel
from app.database import get_db
from app.models.parametro import Parametro

router = APIRouter(prefix="/parametros", tags=["Parámetros"])

class ParametroCreate(BaseModel):
    valor_modulo: float
    motivo:       str = ""

@router.get("/")
def listar(db: Session = Depends(get_db)):
    return db.query(Parametro).order_by(Parametro.vigencia_desde.desc()).all()

@router.post("/")
def actualizar(data: ParametroCreate, db: Session = Depends(get_db)):
    if data.valor_modulo <= 0:
        raise HTTPException(400, "El valor del módulo debe ser mayor a cero")

    # Cerrar el parámetro vigente
    actual = db.query(Parametro).filter(Parametro.vigencia_hasta == None).first()
    if actual:
        actual.vigencia_hasta = date.today()

    # Crear el nuevo
    nuevo = Parametro(
        valor_modulo   = data.valor_modulo,
        vigencia_desde = date.today(),
        vigencia_hasta = None,
        motivo         = data.motivo,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.delete("/{id}")
def eliminar_parametro(id: int, db: Session = Depends(get_db)):
    param = db.get(Parametro, id)
    if not param:
        raise HTTPException(404, "Parámetro no encontrado")
    if param.vigencia_hasta is None:
        raise HTTPException(400, "No podés eliminar el valor del módulo vigente")
    db.delete(param)
    db.commit()
    return {"mensaje": "Registro eliminado correctamente"}    