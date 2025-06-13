# + Nombre de archivo: callback.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/callback.py
# User-provided custom instructions
"""
Handler para callbacks de botones
"""
from __future__ import annotations

import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .estado import UserState
from .ingresos import iniciar_verificacion_ingresos
from .repetitividad import iniciar_repetitividad
from .comparador import iniciar_comparador, procesar_comparacion
from .cargar_tracking import iniciar_carga_tracking, guardar_tracking_servicio
from ..database import obtener_servicio
from ..registrador import registrar_conversacion
from ..utils import obtener_mensaje  # Si se necesitara en el futuro
from .message import _ejecutar_accion_natural, _nombre_flujo

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones del menú"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # ────────────────────────── CONFIRMAR SÍ/NO ───────────────────────────
    if data == "confirmar_flujo_si":
        flujo = context.user_data.pop("confirmar_flujo", None)
        registrar_conversacion(user_id, "confirmar_flujo_si", "Confirmar", "callback")
        if flujo:
            await query.edit_message_text(
                f"Iniciando { _nombre_flujo(flujo) }..."
            )
            await _ejecutar_accion_natural(flujo, update, context, "")
        else:
            await query.edit_message_text("Operación no válida.")
        return
    elif data == "confirmar_flujo_no":
        context.user_data.pop("confirmar_flujo", None)
        registrar_conversacion(user_id, "confirmar_flujo_no", "Cancelar", "callback")
        await query.edit_message_text("Operación cancelada.")
        return

    # ───────────────────────────── COMPARADOR FO ────────────────────────────
    if data == "comparar_fo":
        UserState.set_mode(user_id, "comparador")
        context.user_data.clear()
        registrar_conversacion(user_id, "boton_comparar_fo", "Inicio comparador", "callback")
        await iniciar_comparador(update, context)

    # ─────────────────────────── VERIFICACIÓN INGRESOS ──────────────────────
    elif data == "verificar_ingresos":
        registrar_conversacion(user_id, "boton_verificar_ingresos", "Inicio ingresos", "callback")
        await iniciar_verificacion_ingresos(update, context)

    elif data == "registro_ingresos":
        from .registro_ingresos import iniciar_registro_ingresos
        registrar_conversacion(user_id, "registro_ingresos", "Inicio registro", "callback")
        await iniciar_registro_ingresos(update, context)

    elif data == "ingresos_nombre":
        from .ingresos import opcion_por_nombre
        registrar_conversacion(user_id, "ingresos_nombre", "Elegir por nombre", "callback")
        await opcion_por_nombre(update, context)

    elif data == "ingresos_excel":
        from .ingresos import opcion_por_excel
        registrar_conversacion(user_id, "ingresos_excel", "Elegir por excel", "callback")
        await opcion_por_excel(update, context)

    # ─────────────────────── INFORME DE REPETITIVIDAD ──────────────────────
    elif data == "informe_repetitividad":
        UserState.set_mode(user_id, "repetitividad")
        registrar_conversacion(user_id, "boton_informe_repetitividad", "Inicio repetitividad", "callback")
        await iniciar_repetitividad(update, context)

    # ─────────────────────────── TRACKINGS SERVICIO ─────────────────────────
    elif data == "cargar_tracking":
        registrar_conversacion(user_id, "boton_cargar_tracking", "Inicio carga tracking", "callback")
        await iniciar_carga_tracking(update, context)

    elif data == "descargar_tracking":
        from .descargar_tracking import iniciar_descarga_tracking
        registrar_conversacion(user_id, "boton_descargar_tracking", "Inicio descarga tracking", "callback")
        await iniciar_descarga_tracking(update, context)

    elif data == "descargar_camaras":
        from .descargar_camaras import iniciar_descarga_camaras
        registrar_conversacion(user_id, "boton_descargar_camaras", "Inicio descarga camaras", "callback")
        await iniciar_descarga_camaras(update, context)

    elif data == "enviar_camaras_mail":
        from .enviar_camaras_mail import iniciar_envio_camaras_mail
        registrar_conversacion(user_id, "boton_enviar_camaras_mail", "Inicio envio camaras", "callback")
        await iniciar_envio_camaras_mail(update, context)

    elif data == "id_carrier":
        from .id_carrier import iniciar_identificador_carrier
        registrar_conversacion(user_id, "boton_id_carrier", "Inicio id carrier", "callback")
        await iniciar_identificador_carrier(update, context)

    elif data == "identificador_tarea":
        from .identificador_tarea import iniciar_identificador_tarea
        registrar_conversacion(
            user_id,
            "boton_identificador_tarea",
            "Inicio identificador tarea",
            "callback",
        )
        await iniciar_identificador_tarea(update, context)

    elif data == "analizar_incidencias":
        from .incidencias import iniciar_incidencias
        registrar_conversacion(user_id, "analizar_incidencias", "Inicio incidencias", "callback")
        await iniciar_incidencias(update, context)

    # ────────────────────────── CARGA DE TRACKING MANUAL ────────────────────
    elif data == "confirmar_tracking":
        context.user_data["id_servicio"] = context.user_data.get("id_servicio_detected")
        context.user_data.pop("confirmar_id", None)
        registrar_conversacion(user_id, "confirmar_tracking", "Confirmar ID", "callback")
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Principal", callback_data="tracking_principal"),
                    InlineKeyboardButton("Complementario", callback_data="tracking_complementario"),
                ]
            ]
        )
        await query.edit_message_text(
            "¿El tracking es principal o complementario?",
            reply_markup=keyboard,
        )

    elif data == "cambiar_id_tracking":
        context.user_data["confirmar_id"] = True
        registrar_conversacion(user_id, "cambiar_id_tracking", "Solicitar ID", "callback")
        await query.edit_message_text("Escribí el ID correcto.")

    elif data in ("tracking_principal", "tracking_complementario"):
        context.user_data["tipo_tracking"] = (
            "principal" if data == "tracking_principal" else "complementario"
        )
        registrar_conversacion(user_id, data, "Elegir tipo", "callback")
        await guardar_tracking_servicio(update, context)

    # ─────────────────────────── INFORME DE SLA ────────────────────────────
    elif data == "informe_sla":
        from .informe_sla import iniciar_informe_sla
        registrar_conversacion(user_id, "boton_informe_sla", "Inicio informe SLA", "callback")
        await iniciar_informe_sla(update, context)

    elif data == "sla_procesar":
        from .informe_sla import procesar_informe_sla
        registrar_conversacion(user_id, "sla_procesar", "Procesar informe", "callback")
        await procesar_informe_sla(update, context)

    elif data == "sla_cambiar_plantilla":
        context.user_data["cambiar_plantilla"] = True
        registrar_conversacion(user_id, "sla_cambiar_plantilla", "Solicitar plantilla", "callback")
        await query.edit_message_text("Adjuntá la nueva plantilla .docx")

    # ─────────────────────────────── OTROS ─────────────────────────────────
    elif data == "otro":
        UserState.set_mode(user_id, "sandy")
        registrar_conversacion(user_id, "otro", "Solicitar detalle", "callback")
        await query.edit_message_text(
            "¿Para qué me jodés? Indique su pregunta o solicitud. "
            "Si no puedo hacerla, se enviará como solicitud de implementación."
        )

    elif data == "nueva_solicitud":
        # Flujo para registrar una nueva solicitud manual
        UserState.set_mode(user_id, "sandy")
        UserState.set_waiting_detail(user_id, True)
        context.user_data["nueva_solicitud"] = True
        registrar_conversacion(user_id, "nueva_solicitud", "Solicitar detalle", "callback")
        await query.edit_message_text("✍️ Escribí el detalle de la solicitud y la registraré para revisión.")

    # ─────────────────────────── COMPARADOR SIGUIENTE / PROCESAR ───────────
    elif data == "comparador_siguiente":
        servicio = context.user_data.get("servicio_actual")
        existente = obtener_servicio(servicio)
        if existente and existente.ruta_tracking:
            context.user_data.setdefault("servicios", []).append(servicio)
            context.user_data.setdefault("trackings", []).append(
                (existente.ruta_tracking, os.path.basename(existente.ruta_tracking))
            )
            context.user_data["esperando_servicio"] = True
            context.user_data.pop("esperando_respuesta_actualizacion", None)
            context.user_data.pop("servicio_actual", None)
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Procesar 🚀", callback_data="comparador_procesar")]]
            )
            registrar_conversacion(user_id, "siguiente", "Servicio agregado", "comparador")
            await query.edit_message_text(
                "Servicio agregado. Indicá otro número o ejecutá /procesar.",
                reply_markup=keyboard,
            )
        else:
            context.user_data["esperando_archivo"] = True
            context.user_data.pop("esperando_respuesta_actualizacion", None)
            registrar_conversacion(user_id, "siguiente", "Tracking faltante", "comparador")
            await query.edit_message_text("Ese servicio no posee tracking. Debés enviar el archivo .txt.")

    elif data == "comparador_procesar":
        registrar_conversacion(user_id, "comparador_procesar", "Procesar", "callback")
        await procesar_comparacion(update, context)

    elif query.data == "sla_procesar":
        from .informe_sla import procesar_informe_sla
        registrar_conversacion(query.from_user.id, "sla_procesar", "Procesar", "callback")
        await procesar_informe_sla(update, context)
