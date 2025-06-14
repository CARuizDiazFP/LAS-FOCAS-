# Nombre de archivo: listar_tareas.py
# Ubicación de archivo: Sandy bot/sandybot/handlers/listar_tareas.py
# User-provided custom instructions
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from ..utils import obtener_mensaje
from ..registrador import responder_registrando
from ..database import (
    TareaProgramada,
    TareaServicio,
    Servicio,
    Carrier,
    SessionLocal,
)
from sqlalchemy import func, cast, String


async def listar_tareas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra las tareas programadas aplicando filtros opcionales."""
    mensaje = obtener_mensaje(update)
    if not mensaje:
        return

    user_id = update.effective_user.id

    cliente = None
    servicio_id = None
    fecha_inicio = None
    fecha_fin = None
    carrier_nombre = None

    for arg in context.args:
        if arg.isdigit():
            servicio_id = int(arg)
            continue
        try:
            fecha = datetime.fromisoformat(arg)
            if not fecha_inicio:
                fecha_inicio = fecha
            else:
                fecha_fin = fecha
            continue
        except ValueError:
            if arg.startswith("carrier="):
                carrier_nombre = arg.split("=", 1)[1]
            elif not cliente:
                cliente = arg

    with SessionLocal() as session:
        dialect = session.bind.dialect.name
        if dialect == "sqlite":
            agg = func.group_concat(TareaServicio.servicio_id, ",")
        else:
            agg = func.string_agg(cast(TareaServicio.servicio_id, String), ",")

        consulta = session.query(
            TareaProgramada.id,
            TareaProgramada.fecha_inicio,
            TareaProgramada.fecha_fin,
            TareaProgramada.tipo_tarea,
            agg.label("servicios"),
        ).join(TareaServicio)

        if servicio_id is not None:
            consulta = consulta.filter(TareaServicio.servicio_id == servicio_id)
        if cliente:
            consulta = consulta.join(Servicio).filter(Servicio.cliente == cliente)
        if fecha_inicio:
            consulta = consulta.filter(TareaProgramada.fecha_inicio >= fecha_inicio)
        if fecha_fin:
            consulta = consulta.filter(TareaProgramada.fecha_fin <= fecha_fin)
        if carrier_nombre:
            consulta = consulta.join(
                Carrier, TareaProgramada.carrier_id == Carrier.id
            ).filter(Carrier.nombre == carrier_nombre)

        # Agrupamos + ordenamos en un solo paso
        filas = (
            consulta.group_by(
                TareaProgramada.id,
                TareaProgramada.fecha_inicio,
                TareaProgramada.fecha_fin,
                TareaProgramada.tipo_tarea,
            )
            .order_by(TareaProgramada.fecha_inicio)
            .all()
        )

        if not filas:
            texto = "No se encontraron tareas."
        else:
            tareas_map: dict[int, list[int]] = {}
            info_map: dict[int, tuple] = {}
            for tid, ini, fin, tipo, ids in filas:
                lista = [int(x) for x in ids.split(",") if x]
                tareas_map[tid] = lista
                info_map[tid] = (ini, fin, tipo)

            lineas = []
            for tid in sorted(info_map, key=lambda i: info_map[i][0]):
                ini, fin, tipo = info_map[tid]
                ids_txt = ", ".join(str(i) for i in tareas_map[tid])
                lineas.append(
                    f"{ini:%Y-%m-%d %H:%M} - {fin:%Y-%m-%d %H:%M} {tipo} (servicios: {ids_txt})"
                )
            texto = "\n".join(lineas)

    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "listar_tareas",
        texto,
        "tareas",
    )
