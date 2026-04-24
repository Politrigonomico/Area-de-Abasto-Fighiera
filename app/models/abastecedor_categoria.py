from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class AbastecedorCategoria(Base):
    __tablename__ = "abastecedor_categorias"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    abastecedor_id = Column(Integer, ForeignKey("abastecedores.id"), nullable=False)
    categoria_id   = Column(Integer, ForeignKey("categorias.id"),    nullable=False)

    abastecedor = relationship("Abastecedor", back_populates="abastecedor_categorias")
    categoria   = relationship("Categoria",   back_populates="abastecedor_categorias")