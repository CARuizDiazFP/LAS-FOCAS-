"""
Configuración y modelos de la base de datos
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, text, inspect
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
    carrier = Column(String)
    id_carrier = Column(String)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Servicio(id={self.id}, nombre={self.nombre}, cliente={self.cliente})>"


def ensure_servicio_columns() -> None:
    """Comprueba que la tabla ``servicios`` posea todas las columnas del modelo.

    Si falta alguna, la agrega mediante ``ALTER TABLE`` para mantener la base
    sincronizada con la definición de :class:`Servicio`.
    """
    inspector = inspect(engine)
    actuales = {col["name"] for col in inspector.get_columns("servicios")}
    definidas = {c.name for c in Servicio.__table__.columns}

    faltantes = definidas - actuales
    for columna in faltantes:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE servicios ADD COLUMN {columna} VARCHAR"))

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    # ``bind=engine`` deja explícito que las tablas se crearán usando
    # la conexión configurada en ``engine``. Esto permite que el bot
    # genere la estructura necesaria de forma automática la primera vez.
    Base.metadata.create_all(bind=engine)
    ensure_servicio_columns()


def ensure_servicio_columns() -> None:
    """Verifica la presencia de columnas opcionales en ``servicios``."""
    insp = inspect(engine)
    existing = {col["name"] for col in insp.get_columns("servicios")}
    with engine.begin() as conn:
        if "carrier" not in existing:
            conn.execute(text("ALTER TABLE servicios ADD COLUMN carrier VARCHAR"))
        if "id_carrier" not in existing:
            conn.execute(text("ALTER TABLE servicios ADD COLUMN id_carrier VARCHAR"))


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
        permitidas = {c.name for c in Servicio.__table__.columns}
        datos_validos = {k: v for k, v in datos.items() if k in permitidas}
        if "camaras" in datos_validos and isinstance(datos_validos["camaras"], list):
            datos_validos["camaras"] = json.dumps(datos_validos["camaras"])
        if "trackings" in datos_validos and isinstance(datos_validos["trackings"], list):
            datos_validos["trackings"] = json.dumps(datos_validos["trackings"])
        servicio = Servicio(**datos_validos)
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

