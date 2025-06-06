"""
Handler para callbacks de botones
"""
from telegram import Update
from telegram.ext import ContextTypes
from .estado import UserState
from .ingresos import iniciar_verificacion_ingresos
from .repetitividad import iniciar_repetitividad
from .comparador import iniciar_comparador
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

    elif query.data == "id_carrier":
        from .id_carrier import iniciar_identificador_carrier
        registrar_conversacion(query.from_user.id, "boton_id_carrier", "Inicio id carrier", "callback")
        await iniciar_identificador_carrier(update, context)

    elif query.data == "confirmar_tracking":
        user_id = query.from_user.id
        context.user_data["id_servicio"] = context.user_data.get("id_servicio_detected")
        context.user_data.pop("confirmar_id", None)
        registrar_conversacion(user_id, "confirmar_tracking", "Confirmar ID", "callback")
        await guardar_tracking_servicio(update, context)

    elif query.data == "cambiar_id_tracking":
        context.user_data["confirmar_id"] = True
        registrar_conversacion(query.from_user.id, "cambiar_id_tracking", "Solicitar ID", "callback")
        await query.edit_message_text("Escribí el ID correcto.")

    elif query.data == "informe_sla":
        registrar_conversacion(query.from_user.id, "informe_sla", "No implementado", "callback")
        await query.edit_message_text(
            "🔧 Función 'Informe de SLA' aún no implementada."
        )
        
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
