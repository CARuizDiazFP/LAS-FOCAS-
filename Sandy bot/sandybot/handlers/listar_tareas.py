from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from ..utils import obtener_mensaje
from ..registrador import responder_registrando
from ..database import (
    TareaProgramada,
    TareaServicio,
    Servicio,
    SessionLocal,
)


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
            if not cliente:
                cliente = arg

    with SessionLocal() as session:
        consulta = session.query(TareaProgramada).join(TareaServicio)
        if servicio_id is not None:
            consulta = consulta.filter(TareaServicio.servicio_id == servicio_id)
        if cliente:
            consulta = consulta.join(Servicio).filter(Servicio.cliente == cliente)
        if fecha_inicio:
            consulta = consulta.filter(TareaProgramada.fecha_inicio >= fecha_inicio)
        if fecha_fin:
            consulta = consulta.filter(TareaProgramada.fecha_fin <= fecha_fin)
        consulta = consulta.order_by(TareaProgramada.fecha_inicio)
        tareas = consulta.all()

        if not tareas:
            texto = "No se encontraron tareas."
        else:
            lineas = []
            for t in tareas:
                servicios = (
                    session.query(TareaServicio.servicio_id)
                    .filter(TareaServicio.tarea_id == t.id)
                    .all()
                )
                ids = ", ".join(str(s[0]) for s in servicios)
                lineas.append(
                    f"{t.fecha_inicio:%Y-%m-%d %H:%M} - {t.fecha_fin:%Y-%m-%d %H:%M}"
                    f" {t.tipo_tarea} (servicios: {ids})"
                )
            texto = "\n".join(lineas)

    await responder_registrando(
        mensaje,
        user_id,
        mensaje.text or "listar_tareas",
        texto,
        "tareas",
    )
