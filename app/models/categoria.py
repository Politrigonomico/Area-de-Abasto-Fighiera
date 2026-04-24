from sqlalchemy import Column, Integer, String, Numeric, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Categoria(Base):
    __tablename__ = "categorias"

    id          = Column(Integer,     primary_key=True, autoincrement=True)
    codigo      = Column(String(4),   nullable=False, unique=True)
    nombre      = Column(String(100), nullable=False)
    modulos     = Column(Numeric(4,2),nullable=False)
    descripcion = Column(Text)
    estado      = Column(String(10),  nullable=False, default="activo")

    abastecedores          = relationship("Abastecedor",          back_populates="categoria")
    abastecedor_categorias = relationship("AbastecedorCategoria", back_populates="categoria")