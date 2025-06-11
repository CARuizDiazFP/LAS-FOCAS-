# + Nombre de archivo: registrador.py
# + Ubicación de archivo: Sandy bot/sandybot/registrador.py
# User-provided custom instructions
# sandybot/registrador.py
from datetime import datetime
from .database import SessionLocal, Conversacion
import logging
from telegram import Message

logger = logging.getLogger(__name__)

def registrar_conversacion(user_id: int, mensaje: str, respuesta: str, modo: str = "GPT") -> None:
    """
    Registra una conversación en la base de datos.

    :param user_id: ID del usuario.
    :param mensaje: Mensaje enviado por el usuario.
    :param respuesta: Respuesta enviada por el bot.
    :param modo: Modo de la conversación (ej. GPT, comando).
    """
    with SessionLocal() as session:
        try:
            nueva_conversacion = Conversacion(
                user_id=str(user_id),  # Asegurar que user_id sea string para el modelo
                mensaje=mensaje,
                respuesta=respuesta,
                modo=modo,
                fecha=datetime.utcnow()
            )
            session.add(nueva_conversacion)
            session.commit()
            logger.info(f"✅ Conversación guardada para user_id: {user_id}")
        except Exception as e:
            logger.error(f"❌ Error al guardar conversación para user_id {user_id}: {e}")
            session.rollback()  # Hacer rollback en caso de error


async def responder_registrando(
    mensaje_obj: Message,
    user_id: int,
    texto_usuario: str,
    texto_respuesta: str,
    modo: str,
    **kwargs,
) -> None:
    """Envía una respuesta y registra la interacción."""
    await mensaje_obj.reply_text(texto_respuesta, **kwargs)
    registrar_conversacion(user_id, texto_usuario, texto_respuesta, modo)


def registrar_envio_email(user_id: int, destinatarios: list[str], archivo: str) -> None:
    """Registra en la base que se envió un correo con un adjunto."""
    mensaje = f"Email a {', '.join(destinatarios)}"
    respuesta = f"Archivo {archivo} enviado por email"
    registrar_conversacion(user_id, mensaje, respuesta, "email")
