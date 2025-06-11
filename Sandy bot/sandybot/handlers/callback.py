"""
Handler para callbacks de botones
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import os
from .estado import UserState
from .ingresos import iniciar_verificacion_ingresos
from .repetitividad import iniciar_repetitividad
from .comparador import iniciar_comparador, procesar_comparacion
from ..database import obtener_servicio
from .cargar_tracking import iniciar_carga_tracking, guardar_tracking_servicio
from ..registrador import registrar_conversacion

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones del menú"""
    query = update.callback_query
    await query.answer()

    if query.data == "comparar_fo":
        user_id = query.from_user.id
        UserState.set_mode(user_id, "comparador")
        context.user_data.clear()
        registrar_conversacion(user_id, "boton_comparar_fo", "Inicio comparador", "callback")
        await iniciar_comparador(update, context)
        
    elif query.data == "verificar_ingresos":
        registrar_conversacion(query.from_user.id, "boton_verificar_ingresos", "Inicio ingresos", "callback")
        await iniciar_verificacion_ingresos(update, context)

    elif query.data == "registro_ingresos":
        from .registro_ingresos import iniciar_registro_ingresos
        registrar_conversacion(query.from_user.id, "registro_ingresos", "Inicio registro", "callback")
        await iniciar_registro_ingresos(update, context)

    elif query.data == "ingresos_nombre":
        registrar_conversacion(query.from_user.id, "ingresos_nombre", "Elegir por nombre", "callback")
        from .ingresos import opcion_por_nombre
        await opcion_por_nombre(update, context)

    elif query.data == "ingresos_excel":
        registrar_conversacion(query.from_user.id, "ingresos_excel", "Elegir por excel", "callback")
        from .ingresos import opcion_por_excel
        await opcion_por_excel(update, context)

    elif query.data == "informe_repetitividad":
        user_id = query.from_user.id
        UserState.set_mode(user_id, "repetitividad")
        registrar_conversacion(user_id, "boton_informe_repetitividad", "Inicio repetitividad", "callback")
        await iniciar_repetitividad(update, context)

    elif query.data == "cargar_tracking":
        registrar_conversacion(query.from_user.id, "boton_cargar_tracking", "Inicio carga tracking", "callback")
        await iniciar_carga_tracking(update, context)

    elif query.data == "descargar_tracking":
        from .descargar_tracking import iniciar_descarga_tracking
        registrar_conversacion(query.from_user.id, "boton_descargar_tracking", "Inicio descarga tracking", "callback")
        await iniciar_descarga_tracking(update, context)

    elif query.data == "descargar_camaras":
        from .descargar_camaras import iniciar_descarga_camaras
        registrar_conversacion(query.from_user.id, "boton_descargar_camaras", "Inicio descarga camaras", "callback")
        await iniciar_descarga_camaras(update, context)

    elif query.data == "enviar_camaras_mail":
        from .enviar_camaras_mail import iniciar_envio_camaras_mail
        registrar_conversacion(query.from_user.id, "boton_enviar_camaras_mail", "Inicio envio camaras", "callback")
        await iniciar_envio_camaras_mail(update, context)

    elif query.data == "id_carrier":
        from .id_carrier import iniciar_identificador_carrier
        registrar_conversacion(query.from_user.id, "boton_id_carrier", "Inicio id carrier", "callback")
        await iniciar_identificador_carrier(update, context)

    elif query.data == "analizar_incidencias":
        from .incidencias import iniciar_incidencias
        registrar_conversacion(query.from_user.id, "analizar_incidencias", "Inicio incidencias", "callback")
        await iniciar_incidencias(update, context)

    elif query.data == "confirmar_tracking":
        user_id = query.from_user.id
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

    elif query.data == "cambiar_id_tracking":
        context.user_data["confirmar_id"] = True
        registrar_conversacion(query.from_user.id, "cambiar_id_tracking", "Solicitar ID", "callback")
        await query.edit_message_text("Escribí el ID correcto.")

    elif query.data in ("tracking_principal", "tracking_complementario"):
        context.user_data["tipo_tracking"] = (
            "principal" if query.data == "tracking_principal" else "complementario"
        )
        registrar_conversacion(query.from_user.id, query.data, "Elegir tipo", "callback")
        await guardar_tracking_servicio(update, context)

    elif query.data == "informe_sla":
        from .informe_sla import iniciar_informe_sla
        registrar_conversacion(query.from_user.id, "boton_informe_sla", "Inicio informe SLA", "callback")
        await iniciar_informe_sla(update, context)
        
    elif query.data == "otro":
        user_id = query.from_user.id
        UserState.set_mode(user_id, "sandy")
        registrar_conversacion(user_id, "otro", "Solicitar detalle", "callback")
        await query.edit_message_text(
            "¿Para qué me jodés? Indique su pregunta o solicitud. "
            "Si no puedo hacerla, se enviará como solicitud de implementación."
        )
        
    elif query.data == "nueva_solicitud":
        user_id = query.from_user.id
        # Se inicia el mismo flujo de solicitud manual que cuando la intención
        # es detectada en un mensaje.
        UserState.set_mode(user_id, "sandy")
        UserState.set_waiting_detail(user_id, True)
        context.user_data["nueva_solicitud"] = True
        registrar_conversacion(user_id, "nueva_solicitud", "Solicitar detalle", "callback")
        await query.edit_message_text(
            "✍️ Escribí el detalle de la solicitud y la registraré para revisión."
        )

    elif query.data == "comparador_siguiente":
        user_id = query.from_user.id
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
            await query.edit_message_text(
                "Ese servicio no posee tracking. Debés enviar el archivo .txt.",
            )

    elif query.data == "comparador_procesar":
        registrar_conversacion(query.from_user.id, "comparador_procesar", "Procesar", "callback")
        await procesar_comparacion(update, context)

    elif query.data == "sla_procesar":
        from .informe_sla import procesar_informe_sla
        registrar_conversacion(query.from_user.id, "sla_procesar", "Procesar", "callback")
        await procesar_informe_sla(update, context)
