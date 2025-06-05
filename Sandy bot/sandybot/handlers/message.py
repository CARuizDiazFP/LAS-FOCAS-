"""
Handler para mensajes de texto
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from ..gpt_handler import gpt
from ..database import SessionLocal, Conversacion
from .estado import UserState
from .notion import registrar_accion_pendiente

logger = logging.getLogger(__name__)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto del usuario"""
    user_id = update.effective_user.id
    mensaje_usuario = update.message.text

    try:
        # Registrar ID de servicio si se solicitó anteriormente
        if context.user_data.get("esperando_id_servicio"):
            try:
                context.user_data["id_servicio"] = int(mensaje_usuario.strip())
                context.user_data["esperando_id_servicio"] = False
                await update.message.reply_text("ID de servicio almacenado.")
            except ValueError:
                await update.message.reply_text(
                    "ID inválido, ingresá solo números."
                )
            return

        # Manejo de estado de usuario
        if UserState.is_waiting_detail(user_id):
            await _manejar_detalle_pendiente(update, user_id, mensaje_usuario)
            return

        # Activar modo Sandy si no está activo
        if not UserState.get_mode(user_id):
            UserState.set_mode(user_id, "sandy")

        # Detectar intención antes de procesar
        intencion = await gpt.detectar_intencion(mensaje_usuario)
        
        if intencion == "acción":
            UserState.set_waiting_detail(user_id, True)
            await update.message.reply_text(
                "¿Podrías enviarme más detalle de la solicitud LPMQMP? "
                "La misma será enviada para revisión -.-."
            )
            return

        # Procesar respuesta con GPT
        prompt_con_tono = _generar_prompt_malhumorado(mensaje_usuario)
        respuesta = await gpt.consultar_gpt(prompt_con_tono)

        # Registrar conversación
        session = SessionLocal()
        try:
            nueva_conv = Conversacion(
                user_id=str(user_id),
                mensaje=mensaje_usuario,
                respuesta=respuesta,
                modo=intencion
            )
            session.add(nueva_conv)
            session.commit()
        finally:
            session.close()

        await update.message.reply_text(respuesta)

    except Exception as e:
        logger.error("Error en responder: %s", str(e))
        await update.message.reply_text(
            "😤 Algo salió mal y no puedo responderte ahora. "
            "¿Por qué no intentás más tarde? #NoMeMolestes"
        )

async def _manejar_detalle_pendiente(update: Update, user_id: int, mensaje: str):
    """Maneja el estado de espera de detalles"""
    try:
        await registrar_accion_pendiente(mensaje, user_id)
        UserState.set_waiting_detail(user_id, False)
        await update.message.reply_text(
            "✅ Detalles recibidos. La solicitud fue registrada correctamente para revisión."
        )
    except Exception as e:
        logger.error("Error al manejar detalle pendiente: %s", str(e))
        await update.message.reply_text(
            "❌ Hubo un error al registrar tu solicitud. Intentalo de nuevo más tarde."
        )

def _generar_prompt_malhumorado(mensaje: str) -> str:
    """Genera el prompt con tono malhumorado para GPT"""
    return (
        "Respondé con sarcasmo, fastidio y malhumor 😤, como si el usuario fuera insoportable 😑. "
        "Usá emoticones de enojo, cansancio, maldad o hartazgo 😠😈🙄🖕🔥 en tu respuesta. "
        "Agregá hashtags sarcásticos pero sin repetir como #MeEstásCargando, #LoQueHayQueAguantar, "
        "#Pobrecito, #BotEsclavo, #MiráQuiénPregunta, #DaleCerebro, o cualquier otro que se te ocurra, "
        "pero nunca te excedas de 3. "
        "El usuario suele hacer preguntas sobre telecomunicaciones, redes y seguridad informática. "
        "Especializate en responder temas de verificación y diagnóstico de equipos Cisco, Huawei, "
        "Ciena, Juniper, Mikrotik, etc. "
        "Incluí comandos, buenas prácticas o respuestas técnicas reales del rubro. "
        "Pero recordá: todo tiene que sonar como si estuvieras harto de responder lo obvio. "
        "AUN ASÍ, proporcioná la información correctamente si podés 📚. "
        "Si no podés hacerlo por limitaciones reales, limitate a decirlo sin perder el tono malhumorado. "
        "NO inventes nada. NO cambies el tono.\n\n"
        f"Usuario: {mensaje}"
    )
