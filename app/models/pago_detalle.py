from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class PagoDetalle(Base):
    __tablename__ = "pago_detalle"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    pago_id    = Column(Integer, ForeignKey("transacciones.id"), nullable=False)
    cargo_id   = Column(Integer, ForeignKey("transacciones.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    pago  = relationship("Transaccion", foreign_keys=[pago_id])
    cargo = relationship("Transaccion", foreign_keys=[cargo_id])