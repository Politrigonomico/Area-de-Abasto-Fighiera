from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Categoria, Abastecedor
from app.schemas.categoria import CategoriaCreate, CategoriaUpdate, CategoriaOut

router = APIRouter(prefix="/categorias", tags=["Categorías"])

@router.get("/", response_model=list[CategoriaOut])
def listar(db: Session = Depends(get_db)):
    return db.query(Categoria).order_by(Categoria.codigo).all()

@router.get("/{id}", response_model=CategoriaOut)
def obtener(id: int, db: Session = Depends(get_db)):
    cat = db.get(Categoria, id)
    if not cat:
        raise HTTPException(404, "Categoría no encontrada")
    return cat

@router.post("/", response_model=CategoriaOut, status_code=201)
def crear(data: CategoriaCreate, db: Session = Depends(get_db)):
    if db.query(Categoria).filter_by(codigo=data.codigo).first():
        raise HTTPException(400, "Ya existe una categoría con ese código")
    cat = Categoria(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

@router.put("/{id}", response_model=CategoriaOut)
def editar(id: int, data: CategoriaUpdate, db: Session = Depends(get_db)):
    cat = db.get(Categoria, id)
    if not cat:
        raise HTTPException(404, "Categoría no encontrada")
    if data.estado == "baja":
        activos = db.query(Abastecedor).filter_by(
            categoria_id=id, estado="activo"
        ).count()
        if activos > 0:
            raise HTTPException(
                409, f"No podés dar de baja: hay {activos} abastecedores activos asignados"
            )
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(cat, campo, valor)
    db.commit()
    db.refresh(cat)
    return cat

@router.delete("/{id}", status_code=204)
def eliminar(id: int, db: Session = Depends(get_db)):
    cat = db.get(Categoria, id)
    if not cat:
        raise HTTPException(404, "Categoría no encontrada")
    asignados = db.query(Abastecedor).filter_by(categoria_id=id).count()
    if asignados > 0:
        raise HTTPException(
            409, f"No podés eliminar: hay {asignados} abastecedores asignados"
        )
    db.delete(cat)
    db.commit()