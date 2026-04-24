from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from app.database import Base

class NumeroRecibo(Base):
    """
    Tabla con un único registro que almacena el último número de recibo emitido.
    Cuando el sistema esté habilitado para imprimir recibos oficiales,
    se actualizará el valor inicial con la numeración correspondiente.
    Por ahora siempre devuelve 0.
    """
    __tablename__ = "numero_recibo"

    id         = Column(Integer, primary_key=True, default=1)
    ultimo     = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())