"""
Handler para mensajes de texto
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from ..gpt_handler import gpt
from ..database import SessionLocal, Conversacion, obtener_servicio, crear_servicio
import os
from .estado import UserState
from .notion import registrar_accion_pendiente
from .cargar_tracking import guardar_tracking_servicio
from .ingresos import verificar_camara
from ..utils import normalizar_texto

logger = logging.getLogger(__name__)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto del usuario"""
    user_id = update.effective_user.id
    mensaje_usuario = update.message.text

    try:
        # Manejo de carga de tracking
        if UserState.get_mode(user_id) == "cargar_tracking":
            if context.user_data.get("confirmar_id"):
                respuesta = mensaje_usuario.strip()
                respuesta_normalizada = normalizar_texto(respuesta)
                if (
                    respuesta_normalizada == "si"
                    and "id_servicio_detected" in context.user_data
                ):
                    context.user_data["id_servicio"] = context.user_data[
                        "id_servicio_detected"
                    ]
                elif respuesta.isdigit():
                    context.user_data["id_servicio"] = int(respuesta)
                else:
                    await update.message.reply_text(
                        "Respuesta no válida. Escribí 'sí' o el ID correcto."
                    )
                    return
                context.user_data.pop("confirmar_id", None)
                await guardar_tracking_servicio(update, context)
            else:
                await update.message.reply_text("Enviá el archivo .txt del tracking.")
            return

        # Manejo de estado de usuario
        if UserState.is_waiting_detail(user_id):
            await _manejar_detalle_pendiente(update, context, user_id, mensaje_usuario)
            return

        mode = UserState.get_mode(user_id)
        if mode == "comparador":
            await _manejar_comparador(update, context, mensaje_usuario)
            return

        if mode == "ingresos":
            await verificar_camara(update, context)
            return

        # Activar modo Sandy si no está activo␊
        if not mode:
            UserState.set_mode(user_id, "sandy")

        # Detectar intención antes de procesar
        intencion = await gpt.detectar_intencion(mensaje_usuario)
        
        if intencion == "acción":
            # Guardamos el mensaje que originó la solicitud para registrarlo
            # junto al detalle posterior
            context.user_data["mensaje_inicial"] = mensaje_usuario
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

async def _manejar_detalle_pendiente(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, mensaje: str):
    """Maneja el estado de espera de detalles"""
    try:
        # Si existe un mensaje inicial guardado, lo incluimos en el registro
        mensajes = []
        inicial = context.user_data.pop("mensaje_inicial", None)
        if inicial:
            mensajes.append(inicial)
        mensajes.append(mensaje)
        # Limpiar bandera de flujo manual si existe
        context.user_data.pop("nueva_solicitud", None)

        await registrar_accion_pendiente(mensajes, user_id)
        UserState.set_waiting_detail(user_id, False)
        await update.message.reply_text(
            "✅ Detalles recibidos. La solicitud fue registrada correctamente para revisión."
        )
    except Exception as e:
        logger.error("Error al manejar detalle pendiente: %s", str(e))
        await update.message.reply_text(
            "❌ Hubo un error al registrar tu solicitud. Intentalo de nuevo más tarde."
        )


async def _manejar_comparador(update: Update, context: ContextTypes.DEFAULT_TYPE, mensaje: str) -> None:
    """Gestiona la carga de servicios y trackings para el comparador"""
    user_id = update.effective_user.id
    if context.user_data.get("esperando_servicio"):
        if mensaje.isdigit():
            servicio = int(mensaje)
            context.user_data["servicio_actual"] = servicio
            existente = obtener_servicio(servicio)
            if existente and existente.ruta_tracking:
                context.user_data["esperando_respuesta_actualizacion"] = True
                context.user_data["esperando_servicio"] = False
                await update.message.reply_text(
                    f"El servicio {servicio} ya tiene tracking. Enviá 'siguiente' para mantenerlo o adjuntá un .txt para actualizar."
                )
            else:
                if not existente:
                    crear_servicio(id=servicio)
                context.user_data["esperando_archivo"] = True
                context.user_data["esperando_servicio"] = False
                await update.message.reply_text(
                    f"El servicio {servicio} no posee tracking. Adjuntá el archivo .txt."
                )
        else:
            await update.message.reply_text("Ingresá un número de servicio válido.")
        return

    if context.user_data.get("esperando_respuesta_actualizacion"):
        if mensaje.lower() == "siguiente":
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
                await update.message.reply_text(
                    "Servicio agregado. Indicá otro número o ejecutá /procesar."
                )
            else:
                await update.message.reply_text(
                    "Ese servicio no posee tracking. Debés enviar el archivo .txt."
                )
                context.user_data["esperando_archivo"] = True
                context.user_data.pop("esperando_respuesta_actualizacion", None)
        else:
            await update.message.reply_text(
                "Opción inválida. Escribí 'siguiente' o adjuntá el archivo .txt."
            )
        return

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
