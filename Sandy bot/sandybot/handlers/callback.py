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

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones del menú"""
    query = update.callback_query
    await query.answer()

    if query.data == "comparar_fo":
        user_id = query.from_user.id
        UserState.set_mode(user_id, "comparador")
        context.user_data.clear()
        await iniciar_comparador(update, context)
        
    elif query.data == "verificar_ingresos":
        await iniciar_verificacion_ingresos(update, context)

    elif query.data == "informe_repetitividad":
        user_id = query.from_user.id
        UserState.set_mode(user_id, "repetitividad")
        await iniciar_repetitividad(update, context)

    elif query.data == "cargar_tracking":
        await iniciar_carga_tracking(update, context)

    elif query.data == "confirmar_tracking":
        user_id = query.from_user.id
        context.user_data["id_servicio"] = context.user_data.get("id_servicio_detected")
        context.user_data.pop("confirmar_id", None)
        await guardar_tracking_servicio(update, context)

    elif query.data == "cambiar_id_tracking":
        context.user_data["confirmar_id"] = True
        await query.edit_message_text("Escribí el ID correcto.")

    elif query.data == "informe_sla":
        await query.edit_message_text(
            "🔧 Función 'Informe de SLA' aún no implementada."
        )
        
    elif query.data == "otro":
        user_id = query.from_user.id
        UserState.set_mode(user_id, "sandy")
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
        await query.edit_message_text(
            "✍️ Escribí el detalle de la solicitud y la registraré para revisión."
        )
