"""
Configuración y modelos de la base de datos
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, text, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
import json
import pandas as pd
from .utils import normalizar_camara
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


# Crear las tablas al importar el módulo
init_db()


def obtener_servicio(id_servicio: int) -> Servicio | None:
    """Devuelve un servicio por su ID o ``None`` si no existe."""
    with SessionLocal() as session:
        return session.get(Servicio, id_servicio)


def crear_servicio(**datos) -> Servicio:
    """Crea un nuevo servicio con los datos recibidos."""
    with SessionLocal() as session:
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


def actualizar_tracking(
    id_servicio: int,
    ruta: str | None = None,
    camaras: list[str] | None = None,
    trackings_txt: list[str] | None = None,
) -> None:
    """Actualiza datos del servicio: tracking, cámaras y archivos asociados."""
    with SessionLocal() as session:
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


def buscar_servicios_por_camara(nombre_camara: str) -> list[Servicio]:
    """Devuelve los servicios que contienen la cámara indicada."""

    # Se utiliza un contexto ``with`` para asegurar el cierre de la sesión
    # sin necesidad de manejar excepciones de forma explícita.
    with SessionLocal() as session:
        fragmento = normalizar_camara(nombre_camara)

        # Consulta preliminar para evitar recorrer todos los registros
        candidatos = (
            session.query(Servicio)
            .filter(Servicio.camaras.ilike(f"%{fragmento}%"))
            .all()
        )

        resultados: list[Servicio] = []
        for servicio in candidatos:
            # Si el servicio no posee cámaras registradas se ignora
            if not servicio.camaras:
                continue
            try:
                camaras = json.loads(servicio.camaras)
            except json.JSONDecodeError:
                # Se descarta la fila si el JSON está malformado
                continue
            for c in camaras:
                c_norm = normalizar_camara(str(c))
                if fragmento in c_norm or c_norm in fragmento:
                    resultados.append(servicio)
                    break
        return resultados


def exportar_camaras_servicio(id_servicio: int, ruta_excel: str) -> bool:
    """Guarda en un Excel las cámaras asociadas al servicio indicado.

    :param id_servicio: Identificador del servicio en la base.
    :param ruta_excel: Ruta del archivo Excel a generar.
    :return: ``True`` si el archivo se creó correctamente.
    """
    servicio = obtener_servicio(id_servicio)
    if not servicio or not servicio.camaras:
        return False

    try:
        camaras = json.loads(servicio.camaras)
    except json.JSONDecodeError:
        return False

    # Se crea el DataFrame con una única columna
    df = pd.DataFrame(camaras, columns=["camara"])

    try:
        df.to_excel(ruta_excel, index=False)
        return True
    except Exception:
        return False


def registrar_servicio(id_servicio: int, id_carrier: str | None = None) -> Servicio:
    """Crea o actualiza un servicio con el ``id_servicio`` dado.

    Si el servicio existe, se actualiza el campo ``id_carrier`` si fue
    proporcionado. En caso contrario se genera un nuevo registro con los datos
    recibidos.
    """
    with SessionLocal() as session:
        servicio = session.get(Servicio, id_servicio)
        if servicio:
            if id_carrier is not None:
                servicio.id_carrier = str(id_carrier)
            session.commit()
            session.refresh(servicio)
            return servicio
        nuevo = Servicio(id=id_servicio)
        if id_carrier is not None:
            nuevo.id_carrier = str(id_carrier)
        session.add(nuevo)
        session.commit()
        session.refresh(nuevo)
        return nuevo

