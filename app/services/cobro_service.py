from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Abastecedor, Transaccion, Parametro
from app.models.pago_detalle import PagoDetalle

def get_parametro_vigente(db: Session, fecha: date) -> Parametro:
    parametro = db.query(Parametro).filter(
        Parametro.vigencia_desde <= fecha,
        (Parametro.vigencia_hasta == None) | (Parametro.vigencia_hasta >= fecha)
    ).first()
    if not parametro:
        raise ValueError("No hay un valor de módulo configurado para la fecha indicada")
    return parametro

def generar_cargos_mensuales(db: Session, periodo: str, usuario: str = "sistema") -> dict:
    from app.models.abastecedor_categoria import AbastecedorCategoria

    existentes = db.query(Transaccion).filter_by(tipo='cargo', periodo=periodo).count()
    if existentes > 0:
        raise ValueError(f"Ya existen {existentes} cargos generados para el período {periodo}")

    parametro     = get_parametro_vigente(db, date.today())
    abastecedores = db.query(Abastecedor).filter_by(estado='activo').all()

    cargos_generados = 0
    total_facturado  = 0.0

    for ab in abastecedores:
        # Sumar módulos de TODAS las categorías asignadas
        relaciones = db.query(AbastecedorCategoria).filter_by(abastecedor_id=ab.id).all()
        if not relaciones:
            continue

        modulos  = sum(float(r.categoria.modulos) for r in relaciones)
        codigos  = "+".join(sorted(r.categoria.codigo for r in relaciones))
        snapshot = float(parametro.valor_modulo)
        importe  = modulos * snapshot

        cargo = Transaccion(
            abastecedor_id        = ab.id,
            parametro_id          = parametro.id,
            tipo                  = 'cargo',
            periodo               = periodo,
            modulos_aplicados     = modulos,
            valor_modulo_snapshot = snapshot,
            importe               = importe,
            fecha                 = date.today(),
            descripcion           = f"Cuota mensual {periodo} (Cat. {codigos})",
            usuario               = usuario,
        )
        db.add(cargo)
        cargos_generados += 1
        total_facturado  += importe

    db.commit()
    return {
        "cargos_generados": cargos_generados,
        "total_facturado":  total_facturado,
        "periodo":          periodo,
    }

def get_cargos_pendientes(db: Session, abastecedor_id: int) -> list:
    from app.models.pago_detalle import PagoDetalle
    from sqlalchemy import select

    pagados_ids = select(PagoDetalle.cargo_id)
    cargos = db.query(Transaccion).filter(
        Transaccion.abastecedor_id == abastecedor_id,
        Transaccion.tipo           == 'cargo',
        ~Transaccion.id.in_(pagados_ids)
    ).order_by(Transaccion.periodo).all()
    return cargos

def registrar_pago_selectivo(
    db:             Session,
    abastecedor_id: int,
    cargo_ids:      list[int],
    fecha:          date,
    comprobante:    str  = None,
    usuario:        str  = "sistema"
) -> dict:
    """
    Registra un único pago que cancela los cargos seleccionados.
    Devuelve el pago creado y el detalle de períodos cancelados.
    """
    # Verificar que todos los cargos pertenecen al abastecedor
    cargos = db.query(Transaccion).filter(
        Transaccion.id.in_(cargo_ids),
        Transaccion.abastecedor_id == abastecedor_id,
        Transaccion.tipo           == 'cargo',
    ).all()

    if len(cargos) != len(cargo_ids):
        raise ValueError("Uno o más cargos no corresponden a este abastecedor")

    # Verificar que ninguno ya esté pagado
    ya_pagados = db.query(PagoDetalle.cargo_id).filter(
        PagoDetalle.cargo_id.in_(cargo_ids)
    ).all()
    if ya_pagados:
        raise ValueError("Uno o más períodos seleccionados ya fueron pagados")

    parametro    = get_parametro_vigente(db, fecha)
    total_importe = sum(float(c.importe) for c in cargos)
    periodos     = sorted([c.periodo for c in cargos])

    # Crear la transacción de pago
    pago = Transaccion(
        abastecedor_id        = abastecedor_id,
        parametro_id          = parametro.id,
        tipo                  = 'pago',
        periodo               = fecha.strftime("%Y-%m"),
        modulos_aplicados     = None,
        valor_modulo_snapshot = float(parametro.valor_modulo),
        importe               = total_importe,
        fecha                 = fecha,
        comprobante           = comprobante,
        descripcion           = "Pago períodos: " + ", ".join(periodos),
        usuario               = usuario,
    )
    db.add(pago)
    db.flush()  # Para obtener pago.id sin commitear aún

    # Crear el detalle — un registro por cada cargo cancelado
    for cargo in cargos:
        detalle = PagoDetalle(pago_id=pago.id, cargo_id=cargo.id)
        db.add(detalle)

    db.commit()
    db.refresh(pago)

    return {
        "pago_id":    pago.id,
        "importe":    total_importe,
        "periodos":   periodos,
        "comprobante": comprobante,
        "fecha":      fecha.isoformat(),
    }

def get_saldo_abastecedor(db: Session, abastecedor_id: int) -> dict:
    """Calcula saldo basándose en cargos sin pago_detalle asociado."""
    cargos_pendientes = get_cargos_pendientes(db, abastecedor_id)
    saldo       = sum(float(c.importe) for c in cargos_pendientes)
    periodos_deudores = sorted([c.periodo for c in cargos_pendientes if c.periodo])

    todos_cargos = db.query(Transaccion).filter_by(
        abastecedor_id=abastecedor_id, tipo='cargo'
    ).all()
    todos_pagos = db.query(Transaccion).filter_by(
        abastecedor_id=abastecedor_id, tipo='pago'
    ).all()

    return {
        "saldo":             saldo,
        "total_debe":        sum(float(c.importe) for c in todos_cargos),
        "total_haber":       sum(float(p.importe) for p in todos_pagos),
        "meses_adeudados":   len(periodos_deudores),
        "periodos_deudores": periodos_deudores,
    }

def registrar_pago(db, abastecedor_id, importe, fecha, comprobante=None, descripcion=None, usuario="sistema"):
    """Mantener compatibilidad — pago libre sin selección de períodos."""
    parametro = get_parametro_vigente(db, fecha)
    pago = Transaccion(
        abastecedor_id        = abastecedor_id,
        parametro_id          = parametro.id,
        tipo                  = 'pago',
        periodo               = fecha.strftime("%Y-%m"),
        modulos_aplicados     = None,
        valor_modulo_snapshot = float(parametro.valor_modulo),
        importe               = importe,
        fecha                 = fecha,
        comprobante           = comprobante,
        descripcion           = descripcion or "Pago recibido",
        usuario               = usuario,
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago