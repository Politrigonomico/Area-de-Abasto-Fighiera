from sqlalchemy import Column, Integer, Numeric, Date, Text, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Parametro(Base):
    __tablename__ = "parametros"

    id              = Column(Integer,     primary_key=True, autoincrement=True)
    valor_modulo    = Column(Numeric(12,2),nullable=False)
    vigencia_desde  = Column(Date,        nullable=False)
    vigencia_hasta  = Column(Date,        nullable=True)   # NULL = vigente hoy
    usuario         = Column(String(100))
    motivo          = Column(Text)
    created_at      = Column(DateTime,    server_default=func.now())

    transacciones = relationship("Transaccion", back_populates="parametro")