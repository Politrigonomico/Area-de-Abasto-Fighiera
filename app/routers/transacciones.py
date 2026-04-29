from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models import Abastecedor, Transaccion
from app.schemas.transaccion import PagoCreate, TransaccionOut
from app.services.cobro_service import (
    generar_cargos_mensuales,
    registrar_pago,
    registrar_pago_selectivo,
    get_saldo_abastecedor,
    get_cargos_pendientes,
)

router = APIRouter(prefix="/transacciones", tags=["Transacciones"])

class PagoSelectivo(BaseModel):
    abastecedor_id: int
    cargo_ids:      List[int]
    fecha:          date
    comprobante:    Optional[str] = None

class CargoManual(BaseModel):
    abastecedor_id: int
    periodo:        str
    descripcion:    Optional[str] = None

class CargoRango(BaseModel):
    abastecedor_id: int
    periodo_desde:  str
    periodo_hasta:  str
    descripcion:    Optional[str] = None

class PagoManual(BaseModel):
    abastecedor_id: int
    periodos:       List[str]
    importe:        float
    fecha:          date
    comprobante:    Optional[str] = None
    descripcion:    Optional[str] = None

# ── Rutas fijas primero, luego las con {parámetros} ──────────────────

@router.post("/generar-cargos/{periodo}")
def generar_cargos(periodo: str, usuario: str = "admin", db: Session = Depends(get_db)):
    try:
        return generar_cargos_mensuales(db, periodo, usuario)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/pago-selectivo")
def pago_selectivo(data: PagoSelectivo, db: Session = Depends(get_db)):
    if not db.get(Abastecedor, data.abastecedor_id):
        raise HTTPException(404, "Abastecedor no encontrado")
    if not data.cargo_ids:
        raise HTTPException(400, "Seleccioná al menos un período")
    try:
        return registrar_pago_selectivo(
            db             = db,
            abastecedor_id = data.abastecedor_id,
            cargo_ids      = data.cargo_ids,
            fecha          = data.fecha,
            comprobante    = data.comprobante,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/pago-manual")
def pago_manual(data: PagoManual, db: Session = Depends(get_db)):
    from app.services.cobro_service import get_parametro_vigente
    from app.models.numero_recibo import NumeroRecibo

    ab = db.get(Abastecedor, data.abastecedor_id)
    if not ab:
        raise HTTPException(404, "Abastecedor no encontrado")
    if not data.periodos:
        raise HTTPException(400, "Ingresá al menos un período")
    if data.importe <= 0:
        raise HTTPException(400, "El importe debe ser mayor a cero")

    # ================= LÓGICA DE AUTONUMERACIÓN =================
    if not data.comprobante:
        contador = db.query(NumeroRecibo).filter(NumeroRecibo.id == 1).first()
        if not contador:
            contador = NumeroRecibo(id=1, ultimo=1499)
            db.add(contador)
            db.flush()
        
        contador.ultimo += 1
        numero_final = str(contador.ultimo).zfill(6)
    else:
        numero_final = data.comprobante
    # ============================================================

    parametro    = get_parametro_vigente(db, data.fecha)
    periodos_str = ", ".join(sorted(data.periodos))
    desc         = data.descripcion or f"Pago histórico períodos: {periodos_str}"

    pago = Transaccion(
        abastecedor_id        = ab.id,
        parametro_id          = parametro.id,
        tipo                  = 'pago',
        periodo               = data.fecha.strftime("%Y-%m"),
        modulos_aplicados     = None,
        valor_modulo_snapshot = float(parametro.valor_modulo),
        importe               = data.importe,
        fecha                 = data.fecha,
        comprobante           = numero_final,
        descripcion           = desc,
        usuario               = "historico",
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return {
        "id":          pago.id,
        "importe":     float(pago.importe),
        "periodos":    data.periodos,
        "comprobante": pago.comprobante,
        "fecha":       pago.fecha.isoformat(),
    }

@router.post("/pago", response_model=TransaccionOut, status_code=201)
def registrar_pago_endpoint(data: PagoCreate, db: Session = Depends(get_db)):
    if not db.get(Abastecedor, data.abastecedor_id):
        raise HTTPException(404, "Abastecedor no encontrado")
    return registrar_pago(
        db=db, abastecedor_id=data.abastecedor_id,
        importe=data.importe, fecha=data.fecha,
        comprobante=data.comprobante, descripcion=data.descripcion,
    )

@router.post("/cargo-manual")
def cargo_manual(data: CargoManual, db: Session = Depends(get_db)):
    from app.models.abastecedor_categoria import AbastecedorCategoria
    ab = db.get(Abastecedor, data.abastecedor_id)
    if not ab:
        raise HTTPException(404, "Abastecedor no encontrado")
    existente = db.query(Transaccion).filter_by(
        abastecedor_id=data.abastecedor_id, tipo='cargo', periodo=data.periodo
    ).first()
    if existente:
        raise HTTPException(400, f"Ya existe un cargo para el período {data.periodo}")
    from app.services.cobro_service import get_parametro_vigente
    from datetime import date as date_type
    relaciones = db.query(AbastecedorCategoria).filter_by(abastecedor_id=ab.id).all()
    if not relaciones:
        raise HTTPException(400, "El abastecedor no tiene categorías asignadas")
    parametro = get_parametro_vigente(db, date_type.today())
    modulos   = sum(float(r.categoria.modulos) for r in relaciones)
    codigos   = "+".join(sorted(r.categoria.codigo for r in relaciones))
    snapshot  = float(parametro.valor_modulo)
    importe   = modulos * snapshot
    cargo = Transaccion(
        abastecedor_id        = ab.id,
        parametro_id          = parametro.id,
        tipo                  = 'cargo',
        periodo               = data.periodo,
        modulos_aplicados     = modulos,
        valor_modulo_snapshot = snapshot,
        importe               = importe,
        fecha                 = date_type.today(),
        descripcion           = data.descripcion or f"Cuota mensual {data.periodo} (Cat. {codigos})",
        usuario               = "manual",
    )
    db.add(cargo)
    db.commit()
    db.refresh(cargo)
    return {"id": cargo.id, "periodo": cargo.periodo, "importe": float(cargo.importe)}

@router.post("/cargo-rango")
def cargo_rango(data: CargoRango, db: Session = Depends(get_db)):
    from app.models.abastecedor_categoria import AbastecedorCategoria
    from app.services.cobro_service import get_parametro_vigente
    from datetime import date as date_type
    import re
    ab = db.get(Abastecedor, data.abastecedor_id)
    if not ab:
        raise HTTPException(404, "Abastecedor no encontrado")
    if not re.match(r'^\d{4}-\d{2}$', data.periodo_desde) or \
       not re.match(r'^\d{4}-\d{2}$', data.periodo_hasta):
        raise HTTPException(400, "Formato de período incorrecto. Usá YYYY-MM")
    if data.periodo_desde > data.periodo_hasta:
        raise HTTPException(400, "El período 'desde' no puede ser mayor al 'hasta'")
    def periodos_entre(desde, hasta):
        resultado = []
        anio, mes = int(desde[:4]), int(desde[5:])
        anio_h, mes_h = int(hasta[:4]), int(hasta[5:])
        while (anio, mes) <= (anio_h, mes_h):
            resultado.append(f"{anio:04d}-{mes:02d}")
            mes += 1
            if mes > 12: mes = 1; anio += 1
        return resultado
    periodos = periodos_entre(data.periodo_desde, data.periodo_hasta)
    if len(periodos) > 60:
        raise HTTPException(400, "El rango no puede superar 60 períodos")
    relaciones = db.query(AbastecedorCategoria).filter_by(abastecedor_id=data.abastecedor_id).all()
    if not relaciones:
        raise HTTPException(400, "El abastecedor no tiene categorías asignadas")
    parametro = get_parametro_vigente(db, date_type.today())
    modulos   = sum(float(r.categoria.modulos) for r in relaciones)
    codigos   = "+".join(sorted(r.categoria.codigo for r in relaciones))
    snapshot  = float(parametro.valor_modulo)
    importe   = modulos * snapshot
    generados, omitidos = [], []
    for periodo in periodos:
        existente = db.query(Transaccion).filter_by(
            abastecedor_id=data.abastecedor_id, tipo='cargo', periodo=periodo
        ).first()
        if existente:
            omitidos.append(periodo)
            continue
        db.add(Transaccion(
            abastecedor_id=ab.id, parametro_id=parametro.id, tipo='cargo',
            periodo=periodo, modulos_aplicados=modulos, valor_modulo_snapshot=snapshot,
            importe=importe, fecha=date_type.today(),
            descripcion=data.descripcion or f"Cuota mensual {periodo} (Cat. {codigos})",
            usuario="manual",
        ))
        generados.append(periodo)
    db.commit()
    return {"generados": generados, "omitidos": omitidos,
            "total_generados": len(generados), "importe_por_periodo": importe,
            "total_importe": importe * len(generados)}

@router.get("/cargos-pendientes/{abastecedor_id}")
def cargos_pendientes(abastecedor_id: int, db: Session = Depends(get_db)):
    cargos = get_cargos_pendientes(db, abastecedor_id)
    return [{"id": c.id, "periodo": c.periodo, "importe": float(c.importe),
             "descripcion": c.descripcion} for c in cargos]


@router.get("/proximo-recibo")
def proximo_recibo(db: Session = Depends(get_db)):
    from app.models.numero_recibo import NumeroRecibo
    contador = db.query(NumeroRecibo).filter(NumeroRecibo.id == 1).first()
    
    # Si la base de datos está totalmente vacía (instalación nueva)
    if not contador:
        # Iniciamos el contador en 1499 (o el número que decidan usar menos 1)
        contador = NumeroRecibo(id=1, ultimo=1499)
        db.add(contador)
        db.commit()
        db.refresh(contador)
        
    return {"proximo": str(contador.ultimo + 1).zfill(6)}

@router.get("/abastecedor/{id}")
def movimientos_abastecedor(id: int, db: Session = Depends(get_db)):
    ab = db.get(Abastecedor, id)
    if not ab:
        raise HTTPException(404, "Abastecedor no encontrado")
    from app.models.pago_detalle import PagoDetalle
    movimientos = db.query(Transaccion).filter_by(
        abastecedor_id=id
    ).order_by(Transaccion.periodo.desc(), Transaccion.created_at.desc()).all()
    pagados_ids = {pd.cargo_id for pd in db.query(PagoDetalle).all()}
    saldo = get_saldo_abastecedor(db, id)
    return {
        "abastecedor": ab.razon_social,
        "saldo":       saldo,
        "movimientos": [
            {
                "id": t.id, "tipo": t.tipo, "periodo": t.periodo,
                "importe": float(t.importe), "fecha": t.fecha,
                "descripcion": t.descripcion, "comprobante": t.comprobante,
                "pagado": (t.id in pagados_ids) if t.tipo == "cargo" else None,
            }
            for t in movimientos
        ]
    }

@router.delete("/cargo/{cargo_id}")
def eliminar_cargo(cargo_id: int, db: Session = Depends(get_db)):
    from app.models.pago_detalle import PagoDetalle
    cargo = db.get(Transaccion, cargo_id)
    if not cargo:
        raise HTTPException(404, "Cargo no encontrado")
    if cargo.tipo != 'cargo':
        raise HTTPException(400, "Solo se pueden eliminar cargos, no pagos")
    for d in db.query(PagoDetalle).filter_by(cargo_id=cargo_id).all():
        db.delete(d)
    periodo = cargo.periodo
    db.delete(cargo)
    db.commit()
    return {"mensaje": f"Cargo del período {periodo} eliminado correctamente"}

@router.delete("/pago/{pago_id}")
def eliminar_pago(pago_id: int, db: Session = Depends(get_db)):
    from app.models.pago_detalle import PagoDetalle
    from app.models.numero_recibo import NumeroRecibo

    pago = db.get(Transaccion, pago_id)
    if not pago:
        raise HTTPException(404, "Pago no encontrado")
    if pago.tipo != 'pago':
        raise HTTPException(400, "Este registro no es un pago")

    # ================= LÓGICA DE DEVOLUCIÓN DEL NÚMERO DE RECIBO =================
    if pago.comprobante and pago.comprobante.isdigit():
        num_pago = int(pago.comprobante)
        contador = db.query(NumeroRecibo).filter(NumeroRecibo.id == 1).first()
        if contador and contador.ultimo == num_pago:
            contador.ultimo -= 1
    # =============================================================================

    detalles = db.query(PagoDetalle).filter_by(pago_id=pago_id).all()

    if detalles:
        # Pago selectivo nuevo — revertir cargos asociados
        periodos = []
        for d in detalles:
            cargo = db.get(Transaccion, d.cargo_id)
            if cargo:
                periodos.append(cargo.periodo)
            db.delete(d)
        db.delete(pago)
        db.commit()
        return {"mensaje": f"Pago eliminado. Períodos revertidos a pendiente: {', '.join(sorted(periodos))}"}
    else:
        # Pago histórico o legacy — eliminar directamente sin revertir nada
        db.delete(pago)
        db.commit()
        return {"mensaje": "Pago histórico eliminado correctamente."}

@router.get("/recibo/{pago_id}")
def datos_recibo(pago_id: int, db: Session = Depends(get_db)):
    from app.models.pago_detalle import PagoDetalle
    pago = db.get(Transaccion, pago_id)
    if not pago or pago.tipo != 'pago':
        raise HTTPException(404, "Recibo no encontrado")
    ab  = db.get(Abastecedor, pago.abastecedor_id)
    cat = ab.categoria
    detalles = db.query(PagoDetalle).filter_by(pago_id=pago_id).all()
    cargos   = [db.get(Transaccion, d.cargo_id) for d in detalles]
    return {
        "pago_id": pago.id, "comprobante": pago.comprobante,
        "razon_social": ab.razon_social, "titular": ab.titular,
        "cuit": ab.cuit, "categoria": f"{cat.codigo} — {cat.nombre}",
        "fecha": pago.fecha.isoformat(), "total": float(pago.importe),
        "periodos": [
            {"periodo": c.periodo, "descripcion": c.descripcion,
             "modulos": float(c.modulos_aplicados),
             "valor_modulo": float(c.valor_modulo_snapshot),
             "importe": float(c.importe)}
            for c in cargos
        ]
    }