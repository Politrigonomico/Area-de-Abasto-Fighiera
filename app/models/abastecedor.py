from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Abastecedor(Base):
    __tablename__ = "abastecedores"

    id                   = Column(Integer,      primary_key=True, autoincrement=True)
    razon_social         = Column(String(200),  nullable=False)
    titular              = Column(String(200),  nullable=False)
    cuit                 = Column(String(13),   nullable=True, unique=True)
    telefono_principal   = Column(String(30))
    telefono_alternativo = Column(String(30))
    email                = Column(String(150))
    domicilio            = Column(String(300))
    localidad            = Column(String(100))
    provincia            = Column(String(100),  default="Santa Fe")
    patente              = Column(String(15))
    descripcion_vehiculo = Column(String(200))
    observaciones        = Column(Text)
    categoria_id         = Column(Integer, ForeignKey("categorias.id"), nullable=True)  # legacy
    estado               = Column(String(10), nullable=False, default="activo")
    fecha_alta           = Column(Date,     default=func.current_date())
    created_at           = Column(DateTime, server_default=func.now())
    updated_at           = Column(DateTime, server_default=func.now(), onupdate=func.now())

    categoria              = relationship("Categoria",            back_populates="abastecedores")
    abastecedor_categorias = relationship("AbastecedorCategoria", back_populates="abastecedor",
                                          cascade="all, delete-orphan")
    transacciones          = relationship("Transaccion",          back_populates="abastecedor")