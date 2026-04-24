import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# En el .exe usa la ruta del entorno, en desarrollo usa el archivo local
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///./abasto.db')

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app.models import Categoria, Parametro, Abastecedor, Transaccion
    from app.models.pago_detalle import PagoDetalle
    from app.models.abastecedor_categoria import AbastecedorCategoria

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # ── Seed categorías ──────────────────────────────────────
    if db.query(Categoria).count() == 0:
        categorias = [
            Categoria(codigo="A", nombre="Cadena de frío / Alto riesgo sanitario",
                      modulos=4, descripcion="Carnes rojas y blancas, pescados, lácteos, fiambres, pastas frescas"),
            Categoria(codigo="B", nombre="Frescos y bebidas",
                      modulos=3, descripcion="Frutas, verduras, panificados, bebidas no alcohólicas, agua, hielo"),
            Categoria(codigo="C", nombre="Almacén general",
                      modulos=2, descripcion="Productos envasados, limpieza, perfumería, almacén seco"),
            Categoria(codigo="D", nombre="Golosinas y snacks",
                      modulos=1, descripcion="Golosinas, galletitas, snacks"),
        ]
        db.add_all(categorias)
        db.commit()

    # ── Seed parámetro inicial ───────────────────────────────
    if db.query(Parametro).count() == 0:
        from datetime import date
        db.add(Parametro(
            valor_modulo   = 1000.00,
            vigencia_desde = date(2024, 1, 1),
            motivo         = "Valor inicial del sistema"
        ))
        db.commit()

    # ── Migración automática: categoria_id → abastecedor_categorias ──
    # Se ejecuta una sola vez cuando la tabla nueva está vacía
    # pero ya existen abastecedores con categoria_id
    total_ab  = db.query(Abastecedor).count()
    total_rel = db.query(AbastecedorCategoria).count()

    if total_ab > 0 and total_rel == 0:
        print("Migrando categorías de abastecedores...")
        abastecedores = db.query(Abastecedor).all()
        migrados = 0
        for ab in abastecedores:
            if ab.categoria_id:
                rel = AbastecedorCategoria(
                    abastecedor_id = ab.id,
                    categoria_id   = ab.categoria_id,
                )
                db.add(rel)
                migrados += 1
        db.commit()
        print(f"Migración completa: {migrados} abastecedores migrados")




    db.close()