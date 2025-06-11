from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    text,
    inspect,
    func,
    JSON,
    ForeignKey,
    Index,              # (+) Necesario para definir y recrear índices de forma explícita
    UniqueConstraint,    # (+) Mantiene la restricción única de tareas_servicio
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
import logging
from sqlalchemy.exc import SQLAlchemyError
import json

import pandas as pd
from .utils import normalizar_camara
from datetime import datetime
from .config import config

logger = logging.getLogger(__name__)


# Configuración de la base de datos
DATABASE_URL = (
    f"postgresql+psycopg2://{config.DB_USER}:{config.DB_PASSWORD}@"
    f"{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
)

# Crear engine con connection pooling
engine = create_engine(
    DATABASE_URL, pool_size=5, max_overflow=10, pool_timeout=30, pool_recycle=1800
)

# Selecciona el tipo JSON adecuado según la base de datos
if engine.dialect.name == "postgresql":
    from sqlalchemy.dialects.postgresql import JSONB as JSONType
else:  # pragma: no cover - para SQLite en tests
    JSONType = JSON

# Crear sessionmaker
# ``expire_on_commit=False`` evita que los objetos devueltos pierdan sus datos
# al cerrarse la sesión, algo útil cuando las funciones retornan instancias.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Base declarativa para los modelos
Base = declarative_base()


class Cliente(Base):
    """Clientes que pueden asociarse a un servicio."""

    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, index=True)
    destinatarios = Column(JSONType)


class Conversacion(Base):
    """Modelo para almacenar conversaciones del bot"""

    __tablename__ = "conversaciones"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    mensaje = Column(String)
    respuesta = Column(String)
    modo = Column(String)
    fecha = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return (
            f"<Conversacion(id={self.id}, user_id={self.user_id}, fecha={self.fecha})>"
        )


class Servicio(Base):
    """Modelo que almacena datos de un servicio y su seguimiento"""

    __tablename__ = "servicios"

    id = Column(Integer, primary_key=True)
    nombre = Column(String, index=True)
    cliente = Column(String, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), index=True)
    ruta_tracking = Column(String)

    trackings = Column(JSONType)
    camaras = Column(JSONType)

    carrier = Column(String)
    id_carrier = Column(String, index=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Servicio(id={self.id}, nombre={self.nombre}, cliente={self.cliente})>"


class Camara(Base):
    """Registro de cámaras asociadas a los servicios."""

    __tablename__ = "camaras"

    id = Column(Integer, primary_key=True)
    nombre = Column(String, index=True)
    id_servicio = Column(Integer, index=True)

    def __repr__(self) -> str:
        return (
            f"<Camara(id={self.id}, nombre={self.nombre}, servicio={self.id_servicio})>"
        )


class Ingreso(Base):
    """Almacena cada ingreso a una cámara con fecha y usuario."""

    __tablename__ = "ingresos"

    id = Column(Integer, primary_key=True)
    id_servicio = Column(Integer, index=True)
    id_camara = Column(Integer, index=True, nullable=True)
    camara = Column(String, index=True)
    fecha = Column(DateTime, default=datetime.utcnow, index=True)
    usuario = Column(String)

    def __repr__(self) -> str:
        return f"<Ingreso(id={self.id}, camara={self.camara}, fecha={self.fecha})>"


class TareaProgramada(Base):
    """Tareas programadas que informan los carriers."""

    __tablename__ = "tareas_programadas"

    id = Column(Integer, primary_key=True)
    fecha_inicio = Column(DateTime, index=True)
    fecha_fin = Column(DateTime, index=True)
    tipo_tarea = Column(String)
    tiempo_afectacion = Column(String)
    descripcion = Column(String)


Index(
    "ix_tareas_programadas_fecha_inicio_fecha_fin",
    TareaProgramada.fecha_inicio,
    TareaProgramada.fecha_fin,
)


class TareaServicio(Base):
    """Servicios afectados por cada :class:`TareaProgramada`."""

    __tablename__ = "tareas_servicio"

    id = Column(Integer, primary_key=True)
    tarea_id = Column(Integer, ForeignKey("tareas_programadas.id"), index=True)
    servicio_id = Column(Integer, ForeignKey("servicios.id"), index=True)

    __table_args__ = (
        UniqueConstraint(
            "tarea_id", "servicio_id", name="uix_tarea_servicio"
        ),
    )


def ensure_servicio_columns() -> None:
    """Comprueba que la tabla ``servicios`` posea todas las columnas del modelo.

    Si falta alguna, la agrega mediante ``ALTER TABLE`` para mantener la base
    sincronizada con la definición de :class:`Servicio`.
    """
    inspector = inspect(engine)

    # Crear la tabla de clientes si no existe
    if "clientes" not in inspector.get_table_names():
        Cliente.__table__.create(bind=engine)

    actuales = {col["name"] for col in inspector.get_columns("servicios")}
    definidas = {c.name for c in Servicio.__table__.columns}


    faltantes = definidas - actuales
    for columna in faltantes:
        tipo = Servicio.__table__.columns[columna].type.compile(engine.dialect)
        extra = ""
        if columna == "cliente_id":
            extra = " REFERENCES clientes(id)"
        with engine.begin() as conn:
            conn.execute(
                text(f"ALTER TABLE servicios ADD COLUMN {columna} {tipo}{extra}")
            )

    indices = {idx["name"] for idx in inspector.get_indexes("servicios")}
    if "ix_servicios_id_carrier" not in indices:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX ix_servicios_id_carrier"
                    " ON servicios (id_carrier)"
                )
            )
    if "ix_servicios_cliente_id" not in indices:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX ix_servicios_cliente_id"
                    " ON servicios (cliente_id)"
                )
            )

    indices_tareas = {
        idx["name"]
        for idx in inspector.get_indexes("tareas_programadas")
    }
    if "ix_tareas_programadas_fecha_inicio_fecha_fin" not in indices_tareas:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX ix_tareas_programadas_fecha_inicio_fecha_fin "
                    "ON tareas_programadas (fecha_inicio, fecha_fin)"
                )
            )

    # 2️⃣ Restricción única (tarea_id, servicio_id) en tareas_servicio
    if "tareas_servicio" in inspector.get_table_names():
        uniques = {
            u["name"] for u in inspector.get_unique_constraints("tareas_servicio")
        }
        if "uix_tarea_servicio" not in uniques:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE tareas_servicio "
                        "ADD CONSTRAINT uix_tarea_servicio "
                        "UNIQUE (tarea_id, servicio_id)"
                    )
                )


def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    # ``bind=engine`` deja explícito que las tablas se crearán usando
    # la conexión configurada en ``engine``. Esto permite que el bot
    # genere la estructura necesaria de forma automática la primera vez.
    Base.metadata.create_all(bind=engine)
    ensure_servicio_columns()
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            except SQLAlchemyError as e:
                logger.warning(
                    "No se pudieron crear las extensiones unaccent/pg_trgm: %s",
                    e,
                )

            try:
                conn.execute(
                    text(
                        "CREATE OR REPLACE FUNCTION immutable_unaccent(text)\n"
                        # Se invoca "public.unaccent" porque el esquema
                        # "public" puede no estar en el ``search_path`` al
                        # crear la función.
                        "RETURNS text AS $$ SELECT public.unaccent($1) $$\n"
                        "LANGUAGE SQL IMMUTABLE"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_servicios_camaras_unaccent "
                        "ON servicios USING gin ("
                        "immutable_unaccent(lower(camaras::text)) gin_trgm_ops)"
                    )
                )
            except SQLAlchemyError as e:
                logger.warning(
                    "No se pudo crear el índice para las cámaras: %s",
                    e,
                )



# La inicialización se realiza desde ``main.py`` para evitar errores al
# importar el módulo cuando la base de datos no está disponible.


def obtener_servicio(id_servicio: int) -> Servicio | None:
    """Devuelve un servicio por su ID o ``None`` si no existe."""
    with SessionLocal() as session:
        return session.get(Servicio, id_servicio)


def obtener_cliente_por_nombre(nombre: str) -> Cliente | None:
    """Devuelve un cliente por su nombre."""
    with SessionLocal() as session:
        return session.query(Cliente).filter(Cliente.nombre == nombre).first()


def obtener_destinatarios_servicio(id_servicio: int) -> list[str]:
    """Recupera los correos asociados al cliente de un servicio."""
    with SessionLocal() as session:
        servicio = session.get(Servicio, id_servicio)
        if not servicio:
            return []
        cliente = None
        if servicio.cliente_id:
            cliente = session.get(Cliente, servicio.cliente_id)
        elif servicio.cliente:
            cliente = (
                session.query(Cliente)
                .filter(Cliente.nombre == servicio.cliente)
                .first()
            )
        return cliente.destinatarios if cliente and cliente.destinatarios else []


def crear_servicio(**datos) -> Servicio:
    """Crea un nuevo servicio con los datos recibidos."""
    with SessionLocal() as session:
        permitidas = {c.name for c in Servicio.__table__.columns}
        datos_validos = {k: v for k, v in datos.items() if k in permitidas}
        # Las columnas ``camaras`` y ``trackings`` almacenan datos en formato
        # JSON o JSONB según la base de datos, por lo que se aceptan listas o
        # diccionarios directamente.
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
    tipo: str = "principal",
) -> None:
    """Actualiza datos del servicio: tracking, cámaras y archivos asociados."""
    with SessionLocal() as session:
        servicio = session.get(Servicio, id_servicio)
        if not servicio:
            return
        if ruta is not None:
            servicio.ruta_tracking = ruta
        if camaras is not None:
            # Si las cámaras llegan como cadena (caso de registros antiguos),
            # se intenta convertir desde JSON para guardar siempre una lista.
            if isinstance(camaras, str):
                try:
                    camaras = json.loads(camaras)
                except json.JSONDecodeError:
                    camaras = []
            cam_anterior = servicio.camaras or []
            servicio.camaras = camaras
        if trackings_txt:
            existentes = servicio.trackings or []
            # Compatibilidad con registros del esquema antiguo. Si ``existentes``
            # es una cadena (antes se almacenaba como texto) intentamos
            # convertirlo desde JSON. Si falla o está vacío, se utiliza una
            # lista vacía.
            if isinstance(existentes, str):
                try:
                    existentes = json.loads(existentes) if existentes else []
                except json.JSONDecodeError:
                    existentes = []

            nuevos = []
            for t in trackings_txt:
                if isinstance(t, dict):
                    entrada = t
                else:
                    entrada = {
                        "ruta": t,
                        "tipo": tipo,
                        "fecha": datetime.utcnow().isoformat(),
                    }
                if camaras is not None:
                    nuevas = {normalizar_camara(c) for c in camaras}
                    anteriores = {normalizar_camara(c) for c in cam_anterior}
                    dif_agregadas = nuevas - anteriores
                    dif_quitadas = anteriores - nuevas
                    entrada["nuevas"] = [c for c in camaras if normalizar_camara(c) in dif_agregadas]
                    entrada["quitadas"] = [c for c in cam_anterior if normalizar_camara(c) in dif_quitadas]
                nuevos.append(entrada)
            existentes.extend(nuevos)
            servicio.trackings = existentes
        session.commit()


def buscar_servicios_por_camara(nombre_camara: str) -> list[Servicio]:
    """Devuelve los servicios que contienen la cámara indicada."""


    # Se utiliza un contexto ``with`` para asegurar el cierre de la sesión
    # sin necesidad de manejar excepciones de forma explícita.
    with SessionLocal() as session:
        fragmento = normalizar_camara(nombre_camara)


        # Primer intento de filtrado. Se castea ``Servicio.camaras`` a ``String``
        # para evitar problemas cuando se guarda como JSON o JSONB.
        camaras_str = Servicio.camaras.cast(String)

        # Algunas bases de datos como SQLite no cuentan con la función
        # ``unaccent``. Se verifica el dialecto para aplicarla solo cuando
        # está disponible (PostgreSQL).
        if session.bind.dialect.name == "postgresql":
            columna_normalizada = func.unaccent(func.lower(camaras_str))
        else:
            columna_normalizada = func.lower(camaras_str)

        filtro = columna_normalizada.ilike(
            f"%{normalizar_camara(nombre_camara)}%"
        )
        candidatos = session.query(Servicio).filter(filtro).all()


        # Si no se encontraron coincidencias con la cadena tal cual se recibió,
        # se recuperan todos los servicios para comparar en memoria utilizando
        # la versión normalizada y así evitar falsos negativos.
        if not candidatos:
            candidatos = session.query(Servicio).all()

        resultados: list[Servicio] = []
        for servicio in candidatos:
            # Si el servicio no posee cámaras registradas se ignora

            if not servicio.camaras:
                continue
            camaras = servicio.camaras

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

    camaras = servicio.camaras
    # Compatibilidad con campos almacenados como texto JSON. Si es una cadena,
    # se intenta decodificar para obtener la lista de cámaras.
    if isinstance(camaras, str):
        try:
            camaras = json.loads(camaras)
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
    """Inserta o actualiza un servicio utilizando ``session.merge``.

    Se crea un objeto :class:`Servicio` con el ID indicado y, si se
    proporciona ``id_carrier``, también se asigna. ``merge`` evita duplicados
    al combinarlo con la fila existente cuando corresponde.
    """
    with SessionLocal() as session:
        datos = {"id": id_servicio}
        if id_carrier is not None:
            datos["id_carrier"] = str(id_carrier)

        servicio = Servicio(**datos)
        servicio = session.merge(servicio)
        session.commit()
        session.refresh(servicio)
        return servicio


def crear_camara(nombre: str, id_servicio: int) -> Camara:
    """Crea una cámara asociada a un servicio."""
    with SessionLocal() as session:
        camara = Camara(nombre=nombre, id_servicio=id_servicio)
        session.add(camara)
        session.commit()
        session.refresh(camara)
        return camara


def crear_ingreso(
    id_servicio: int,
    camara: str,
    fecha: datetime | None = None,
    usuario: str | None = None,
    id_camara: int | None = None,
) -> Ingreso:
    """Registra un ingreso a una cámara."""
    with SessionLocal() as session:
        ingreso = Ingreso(
            id_servicio=id_servicio,
            camara=camara,
            fecha=fecha or datetime.utcnow(),
            usuario=usuario,
            id_camara=id_camara,
        )
        session.add(ingreso)
        session.commit()
        session.refresh(ingreso)
        return ingreso


def crear_tarea_programada(
    fecha_inicio: datetime,
    fecha_fin: datetime,
    tipo_tarea: str,
    servicios: list[int],
    tiempo_afectacion: str | None = None,
    descripcion: str | None = None,
) -> TareaProgramada:
    """Registra una tarea programada y la vincula a los servicios indicados."""

    with SessionLocal() as session:
        tarea = TareaProgramada(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo_tarea=tipo_tarea,
            tiempo_afectacion=tiempo_afectacion,
            descripcion=descripcion,
        )
        session.add(tarea)
        session.commit()
        session.refresh(tarea)

        for sid in servicios:
            session.add(TareaServicio(tarea_id=tarea.id, servicio_id=sid))

        session.commit()
        return tarea


def obtener_tareas_servicio(servicio_id: int) -> list[TareaProgramada]:
    """Devuelve las tareas programadas que afectan al servicio indicado."""

    with SessionLocal() as session:
        return (
            session.query(TareaProgramada)
            .join(TareaServicio, TareaProgramada.id == TareaServicio.tarea_id)
            .filter(TareaServicio.servicio_id == servicio_id)
            .all()
        )



