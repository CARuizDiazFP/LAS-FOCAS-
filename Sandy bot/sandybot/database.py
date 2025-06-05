"""
Configuración y modelos de la base de datos
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import json
from datetime import datetime
from .config import config

# Configuración de la base de datos
DATABASE_URL = (
    f"postgresql+psycopg2://{config.DB_USER}:{config.DB_PASSWORD}@"
    f"{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
)

# Crear engine con connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)

# Crear sessionmaker
SessionLocal = sessionmaker(bind=engine)

# Base declarativa para los modelos
Base = declarative_base()

class Conversacion(Base):
    """Modelo para almacenar conversaciones del bot"""
    __tablename__ = 'conversaciones'

    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    mensaje = Column(String)
    respuesta = Column(String)
    modo = Column(String)
    fecha = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Conversacion(id={self.id}, user_id={self.user_id}, fecha={self.fecha})>"


class Servicio(Base):
    """Modelo que almacena datos de un servicio y su seguimiento"""
    __tablename__ = 'servicios'

    id = Column(Integer, primary_key=True)
    nombre = Column(String, index=True)
    cliente = Column(String, index=True)
    ruta_tracking = Column(String)
    trackings = Column(String)
    camaras = Column(String)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Servicio(id={self.id}, nombre={self.nombre}, cliente={self.cliente})>"

def init_db():
    """Inicializa la base de datos y crea todas las tablas definidas"""
    Base.metadata.create_all(engine)

# Crear las tablas al importar el módulo
init_db()


def obtener_servicio(id_servicio: int) -> Servicio | None:
    """Devuelve un servicio por su ID o ``None`` si no existe."""
    session = SessionLocal()
    try:
        return session.get(Servicio, id_servicio)
    finally:
        session.close()


def crear_servicio(**datos) -> Servicio:
    """Crea un nuevo servicio con los datos recibidos."""
    session = SessionLocal()
    try:
        if "camaras" in datos and isinstance(datos["camaras"], list):
            datos["camaras"] = json.dumps(datos["camaras"])
        if "trackings" in datos and isinstance(datos["trackings"], list):
            datos["trackings"] = json.dumps(datos["trackings"])
        servicio = Servicio(**datos)
        session.add(servicio)
        session.commit()
        session.refresh(servicio)
        return servicio
    finally:
        session.close()


def actualizar_tracking(
    id_servicio: int,
    ruta: str | None = None,
    camaras: list[str] | None = None,
    trackings_txt: list[str] | None = None,
) -> None:
    """Actualiza datos del servicio: tracking, cámaras y archivos asociados."""
    session = SessionLocal()
    try:
        servicio = session.get(Servicio, id_servicio)
        if not servicio:
            return
        if ruta is not None:
            servicio.ruta_tracking = ruta
        if camaras is not None:
            servicio.camaras = json.dumps(camaras)
        if trackings_txt:
            existentes = json.loads(servicio.trackings) if servicio.trackings else []
            existentes.extend(trackings_txt)
            servicio.trackings = json.dumps(existentes)
        session.commit()
    finally:
        session.close()

