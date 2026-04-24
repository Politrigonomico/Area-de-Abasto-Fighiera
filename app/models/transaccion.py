from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Transaccion(Base):
    __tablename__ = "transacciones"

    id                    = Column(Integer,      primary_key=True, autoincrement=True)
    abastecedor_id        = Column(Integer,      ForeignKey("abastecedores.id"), nullable=False)
    parametro_id          = Column(Integer,      ForeignKey("parametros.id"),    nullable=False)
    tipo                  = Column(String(10),   nullable=False)
    periodo               = Column(String(7))
    modulos_aplicados     = Column(Numeric(4,2))
    valor_modulo_snapshot = Column(Numeric(12,2),nullable=False)
    importe               = Column(Numeric(12,2),nullable=False)
    fecha                 = Column(Date,         nullable=False)
    comprobante           = Column(String(50))
    descripcion           = Column(Text)
    usuario               = Column(String(100))
    created_at            = Column(DateTime,     server_default=func.now())

    abastecedor = relationship("Abastecedor", back_populates="transacciones")
    parametro   = relationship("Parametro",   back_populates="transacciones")