from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Abastecedor, Categoria
from app.models.abastecedor_categoria import AbastecedorCategoria
from app.schemas.abastecedor import AbastecedorCreate, AbastecedorUpdate, AbastecedorOut, AbastecedorConSaldo
from app.services.cobro_service import get_saldo_abastecedor

router = APIRouter(prefix="/abastecedores", tags=["Abastecedores"])

def abastecedor_to_dict(ab: Abastecedor, db: Session) -> dict:
    relaciones = db.query(AbastecedorCategoria).filter_by(abastecedor_id=ab.id).all()
    d = {c.name: getattr(ab, c.name) for c in ab.__table__.columns}
    d['categoria_ids'] = [r.categoria_id for r in relaciones]
    return d

@router.get("/", response_model=list[AbastecedorOut])
def listar(
    estado:       str = Query(None),
    categoria_id: int = Query(None),
    buscar:       str = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(Abastecedor)
    if estado:
        q = q.filter_by(estado=estado)
    if categoria_id:
        q = q.join(AbastecedorCategoria).filter(
            AbastecedorCategoria.categoria_id == categoria_id
        )
    if buscar:
        q = q.filter(
            Abastecedor.razon_social.ilike(f"%{buscar}%") |
            Abastecedor.titular.ilike(f"%{buscar}%") |
            Abastecedor.patente.ilike(f"%{buscar}%")
        )
    abs_ = q.order_by(Abastecedor.razon_social).all()
    return [AbastecedorOut(**abastecedor_to_dict(ab, db)) for ab in abs_]

@router.get("/{id}", response_model=AbastecedorConSaldo)
def obtener(id: int, db: Session = Depends(get_db)):
    ab = db.get(Abastecedor, id)
    if not ab:
        raise HTTPException(404, "Abastecedor no encontrado")
    saldo  = get_saldo_abastecedor(db, id)
    d      = abastecedor_to_dict(ab, db)
    result = AbastecedorConSaldo(**d)
    result.saldo             = saldo["saldo"]
    result.meses_adeudados   = saldo["meses_adeudados"]
    result.periodos_deudores = saldo["periodos_deudores"]
    return result

@router.post("/", response_model=AbastecedorOut, status_code=201)
def crear(data: AbastecedorCreate, db: Session = Depends(get_db)):
    if not data.categoria_ids:
        raise HTTPException(400, "Asigná al menos una categoría")
    for cid in data.categoria_ids:
        if not db.get(Categoria, cid):
            raise HTTPException(400, f"Categoría {cid} no encontrada")
    if data.cuit and db.query(Abastecedor).filter_by(cuit=data.cuit).first():
        raise HTTPException(400, "Ya existe un abastecedor con ese CUIT")

    datos = data.model_dump(exclude={"categoria_ids"})
    datos["categoria_id"] = data.categoria_ids[0]  # legacy: guardar la primera
    ab = Abastecedor(**datos)
    db.add(ab)
    db.flush()

    for cid in data.categoria_ids:
        db.add(AbastecedorCategoria(abastecedor_id=ab.id, categoria_id=cid))

    db.commit()
    db.refresh(ab)
    return AbastecedorOut(**abastecedor_to_dict(ab, db))

@router.put("/{id}", response_model=AbastecedorOut)
def editar(id: int, data: AbastecedorUpdate, db: Session = Depends(get_db)):
    ab = db.get(Abastecedor, id)
    if not ab:
        raise HTTPException(404, "Abastecedor no encontrado")

    datos = data.model_dump(exclude_unset=True, exclude={"categoria_ids"})
    for campo, valor in datos.items():
        setattr(ab, campo, valor)

    if data.categoria_ids is not None:
        if not data.categoria_ids:
            raise HTTPException(400, "Asigná al menos una categoría")
        for cid in data.categoria_ids:
            if not db.get(Categoria, cid):
                raise HTTPException(400, f"Categoría {cid} no encontrada")
        # Reemplazar relaciones
        db.query(AbastecedorCategoria).filter_by(abastecedor_id=id).delete()
        for cid in data.categoria_ids:
            db.add(AbastecedorCategoria(abastecedor_id=id, categoria_id=cid))
        ab.categoria_id = data.categoria_ids[0]  # legacy

    db.commit()
    db.refresh(ab)
    return AbastecedorOut(**abastecedor_to_dict(ab, db))

@router.delete("/{id}", status_code=204)
def eliminar(id: int, db: Session = Depends(get_db)):
    ab = db.get(Abastecedor, id)
    if not ab:
        raise HTTPException(404, "Abastecedor no encontrado")
    db.delete(ab)
    db.commit()