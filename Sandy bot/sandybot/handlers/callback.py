"""
Handler para callbacks de botones
"""
from telegram import Update
from telegram.ext import ContextTypes
from .estado import UserState
from .ingresos import iniciar_verificacion_ingresos
from .repetitividad import iniciar_repetitividad
from .comparador import iniciar_comparador

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones del menú"""
    query = update.callback_query
    await query.answer()

    if query.data == "comparar_fo":
        await iniciar_comparador(update, context)
        
    elif query.data == "verificar_ingresos":
        await iniciar_verificacion_ingresos(update, context)
        
    elif query.data == "informe_repetitividad":
        await iniciar_repetitividad(update, context)
        
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
        await query.edit_message_text(
            "📝 Función 'Nueva solicitud' aún no implementada."
        )
