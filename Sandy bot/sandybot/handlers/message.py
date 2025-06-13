# + Nombre de archivo: message.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/message.py
# User-provided custom instructions
"""
Handler para mensajes de texto
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..gpt_handler import gpt
from ..database import obtener_servicio, crear_servicio
from ..registrador import responder_registrando
import os
from .estado import UserState
from .notion import registrar_accion_pendiente
from .ingresos import verificar_camara, iniciar_verificacion_ingresos
from .comparador import iniciar_comparador
from .cargar_tracking import (
    guardar_tracking_servicio,
    iniciar_carga_tracking,
)
from .repetitividad import iniciar_repetitividad
from .id_carrier import iniciar_identificador_carrier
from ..utils import normalizar_texto
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Diccionario para mostrar nombres amigables en la confirmación de flujos
NOMBRES_FLUJO = {
    "comparar_fo": "Comparar trazados FO",
    "verificar_ingresos": "Verificar ingresos",
    "cargar_tracking": "Cargar tracking",
    "descargar_tracking": "Descargar tracking",
    "descargar_camaras": "Descargar cámaras",
    "enviar_camaras_mail": "Enviar cámaras por mail",
    "id_carrier": "Identificar carrier",
    "informe_repetitividad": "Informe de repetitividad",
    "informe_sla": "Informe de SLA",
    "analizar_incidencias": "Analizar incidencias",
    "nueva_solicitud": "Nueva solicitud",
    "start": "Menú de funciones",
    "otro": "Otro flujo",
}

def _nombre_flujo(clave: str) -> str:
    """Devuelve el nombre legible del flujo indicado."""
    return NOMBRES_FLUJO.get(clave, clave)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto del usuario"""
    user_id = update.effective_user.id
    # Si ``voice_handler`` guardó una transcripción en ``context.user_data``
    # la utilizamos como texto original sin modificar el ``Update``.
    mensaje_usuario = context.user_data.pop("voice_text", None) or update.message.text

    try:
        # Si hay un flujo pendiente de confirmación procesamos primero esa respuesta
        flujo_pendiente = context.user_data.get("confirmar_flujo")
        if flujo_pendiente:
            resp = normalizar_texto(mensaje_usuario)
            if resp in ("si", "sí", "s", "ok", "dale", "yes"):
                context.user_data.pop("confirmar_flujo", None)
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje_usuario,
                    f"Iniciando { _nombre_flujo(flujo_pendiente) }...",
                    "sandy",
                )
                await _ejecutar_accion_natural(
                    flujo_pendiente, update, context, mensaje_usuario
                )
            elif resp in ("no", "n", "cancelar"):
                context.user_data.pop("confirmar_flujo", None)
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje_usuario,
                    "Operación cancelada.",
                    "sandy",
                )
            else:
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Sí", callback_data="confirmar_flujo_si"
                            ),
                            InlineKeyboardButton(
                                "No", callback_data="confirmar_flujo_no"
                            ),
                        ]
                    ]
                )
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje_usuario,
                    "Decí 'sí' o 'no' para confirmar.",
                    "sandy",
                    reply_markup=keyboard,
                )
            return

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
                    await responder_registrando(
                        update.message,
                        user_id,
                        mensaje_usuario,
                        "Respuesta no válida. Escribí 'sí' o el ID correcto.",
                        "cargar_tracking",
                    )
                    return
                context.user_data.pop("confirmar_id", None)
                await guardar_tracking_servicio(update, context)
            else:
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje_usuario,
                    "Enviá el archivo .txt del tracking.",
                    "cargar_tracking",
                )
            return

        # Descarga de tracking
        if UserState.get_mode(user_id) == "descargar_tracking":
            from .descargar_tracking import enviar_tracking_servicio
            await enviar_tracking_servicio(update, context)
            return

        # Descarga de cámaras
        if UserState.get_mode(user_id) == "descargar_camaras":
            from .descargar_camaras import enviar_camaras_servicio
            await enviar_camaras_servicio(update, context)
            return

        # Enviar cámaras por mail
        if UserState.get_mode(user_id) == "enviar_camaras_mail":
            from .enviar_camaras_mail import procesar_envio_camaras_mail
            await procesar_envio_camaras_mail(update, context)
            return

        # Manejo de estado de usuario
        if UserState.is_waiting_detail(user_id):
            await _manejar_detalle_pendiente(update, context, user_id, mensaje_usuario)
            return

        mode = UserState.get_mode(user_id)

        if mode in ("", "sandy"):
            accion = _detectar_accion_natural(mensaje_usuario)
            if not accion:
                accion = await gpt.clasificar_flujo(mensaje_usuario)
                if accion == "desconocido":
                    pregunta = await gpt.generar_pregunta_intencion(mensaje_usuario)
                    await responder_registrando(
                        update.message,
                        user_id,
                        mensaje_usuario,
                        pregunta,
                        "sandy",
                    )
                    return
            if accion:
                context.user_data["confirmar_flujo"] = accion
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Sí", callback_data="confirmar_flujo_si"
                            ),
                            InlineKeyboardButton(
                                "No", callback_data="confirmar_flujo_no"
                            ),
                        ]
                    ]
                )
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje_usuario,
                    f"¿Deseás iniciar { _nombre_flujo(accion) }? (sí/no)",
                    "sandy",
                    reply_markup=keyboard,
                )
                return

        if mode == "comparador":
            await _manejar_comparador(update, context, mensaje_usuario)
            return

        if mode == "informe_sla":
            from .informe_sla import procesar_informe_sla
            await procesar_informe_sla(update, context)
            return

        if mode == "ingresos":
            if context.user_data.get("esperando_opcion"):
                await _manejar_opcion_ingresos(update, context, mensaje_usuario)
                return
            if context.user_data.get("opcion_ingresos") == "nombre":
                await verificar_camara(update, context)
                return
            if context.user_data.get("opcion_ingresos") == "excel":
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje_usuario,
                    "Adjuntá el Excel con las cámaras en la columna A.",
                    "ingresos",
                )
                return

        if mode == "registro_ingresos":
            from .registro_ingresos import guardar_registro
            await guardar_registro(update, context)
            return

        # Activar modo Sandy si no está activo
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

        # Actualizar contador de interacciones
        puntaje = UserState.increment_interaction(user_id)

        # Procesar respuesta con GPT ajustando el tono según el puntaje
        prompt_con_tono = _generar_prompt_por_animo(mensaje_usuario, puntaje)
        respuesta = await gpt.consultar_gpt(prompt_con_tono)

        await responder_registrando(
            update.message,
            user_id,
            mensaje_usuario,
            respuesta,
            intencion,
        )

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
        await responder_registrando(
            update.message,
            user_id,
            mensaje,
            "✅ Detalles recibidos. La solicitud fue registrada correctamente para revisión.",
            "nueva_solicitud",
        )
    except Exception as e:
        logger.error("Error al manejar detalle pendiente: %s", str(e))
        await responder_registrando(
            update.message,
            user_id,
            mensaje,
            "❌ Hubo un error al registrar tu solicitud. Intentalo de nuevo más tarde.",
            "nueva_solicitud",
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
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Siguiente ➡️", callback_data="comparador_siguiente")]]
                )
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje,
                    f"El servicio {servicio} ya tiene tracking. Enviá 'siguiente' para mantenerlo o adjuntá un .txt para actualizar.",
                    "comparador",
                    reply_markup=keyboard,
                )
            else:
                if not existente:
                    crear_servicio(id=servicio)
                context.user_data["esperando_archivo"] = True
                context.user_data["esperando_servicio"] = False
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje,
                    f"El servicio {servicio} no posee tracking. Adjuntá el archivo .txt.",
                    "comparador",
                )
        else:
            await responder_registrando(
                update.message,
                user_id,
                mensaje,
                "Ingresá un número de servicio válido.",
                "comparador",
            )
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
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Procesar 🚀", callback_data="comparador_procesar")]]
                )
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje,
                    "Servicio agregado. Indicá otro número o ejecutá /procesar.",
                    "comparador",
                    reply_markup=keyboard,
                )
            else:
                await responder_registrando(
                    update.message,
                    user_id,
                    mensaje,
                    "Ese servicio no posee tracking. Debés enviar el archivo .txt.",
                    "comparador",
                )
                context.user_data["esperando_archivo"] = True
                context.user_data.pop("esperando_respuesta_actualizacion", None)
        else:
            await responder_registrando(
                update.message,
                user_id,
                mensaje,
                "Opción inválida. Escribí 'siguiente' o adjuntá el archivo .txt.",
                "comparador",
            )
        return


async def _manejar_opcion_ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE, mensaje: str) -> None:
    """Interpreta la elección de validación de ingresos."""
    user_id = update.effective_user.id
    texto = normalizar_texto(mensaje)
    if "nombre" in texto:
        from .ingresos import opcion_por_nombre
        await opcion_por_nombre(update, context)
    elif "excel" in texto:
        from .ingresos import opcion_por_excel
        await opcion_por_excel(update, context)
    else:
        await responder_registrando(
            update.message,
            user_id,
            mensaje,
            "Opción no válida. Escribí 'nombre' o 'excel'.",
            "ingresos",
        )
    return


def _detectar_accion_natural(mensaje: str) -> str | None:
    """Intenta mapear el mensaje a una acción disponible."""
    texto = normalizar_texto(mensaje)
    claves = {
        "comparar_fo": [
            "comparar trazados",
            "comparacion fo",
            "comparar fo",
            "comparemos trazados",
            "comparemos fo",
            "cmp fo",
            "cmp trazados",
        ],
        "verificar_ingresos": [
            "verificar ingresos",
            "validar ingresos",
            "verifiquemos ingresos",
            "ver ing",
            "verif ing",
            "valid ing",
        ],
        "cargar_tracking": [
            "cargar tracking",
            "carguemos un tracking",
            "carguemos el tracking",
            "subir tracking",
            "adjuntar tracking",
            "cargar trk",
            "subir trk",
            "adjuntar trk",
        ],
        "descargar_tracking": [
            "descargar tracking",
            "obtener tracking",
            "bajar tracking",
            "desc trk",
            "bajar trk",
            "obt trk",
        ],
        "descargar_camaras": [
            "descargar camaras",
            "descargar cámaras",
            "obtener camaras",
            "bajar camaras",
            "desc cams",
            "bajar cams",
            "obt cams",
        ],
        "enviar_camaras_mail": [
            "enviar camaras por mail",
            "enviar cámaras por mail",
            "camaras por correo",
            "env cams mail",
            "cam x mail",
        ],
        "id_carrier": [
            "identificador de servicio carrier",
            "id carrier",
            "identificar carrier",
            "id carr",
            "ident carr",
        ],
        "informe_repetitividad": [
            "informe de repetitividad",
            "reporte de repetitividad",
            "inf repet",
            "rep repet",
        ],
        "informe_sla": ["informe de sla", "reporte de sla", "inf sla", "rep sla"],
        "analizar_incidencias": [
            "analizar incidencias",
            "incidencias",
            "anal inc",
            "incid.",
        ],
        "start": [
            "start",
            "/start",
            "menu",
            "ayuda",
            "funciones",
            "opciones",
        ],
        "otro": ["otro"],
        "nueva_solicitud": [
            "nueva solicitud",
            "registrar solicitud",
            "nva solicitud",
            "nuevo req",
        ],
    }

    for accion, palabras in claves.items():
        for palabra in palabras:
            if palabra in texto:
                return accion
            if SequenceMatcher(None, palabra, texto).ratio() > 0.8:
                return accion

    # Heurísticos para variaciones en lenguaje natural
    if "compar" in texto and ("fo" in texto or "trazad" in texto):
        return "comparar_fo"
    if "ingres" in texto and ("verific" in texto or "valid" in texto):
        return "verificar_ingresos"
    if "tracking" in texto and (
        "cargar" in texto
        or "cargu" in texto
        or "subir" in texto
        or "adjuntar" in texto
    ):
        return "cargar_tracking"
    if "tracking" in texto and (
        "descarg" in texto
        or "bajar" in texto
        or "obten" in texto
    ):
        return "descargar_tracking"
    if "camar" in texto and (
        "descarg" in texto
        or "bajar" in texto
        or "obten" in texto
    ):
        return "descargar_camaras"
    if "camar" in texto and "mail" in texto:
        return "enviar_camaras_mail"
    if "carrier" in texto and ("ident" in texto or "id" in texto):
        return "id_carrier"
    if "repetit" in texto and "inform" in texto:
        return "informe_repetitividad"
    if "sla" in texto and "inform" in texto:
        return "informe_sla"
    if "incidenc" in texto and ("analiz" in texto or "docx" in texto):
        return "analizar_incidencias"
    if "nueva" in texto and "solicitud" in texto:
        return "nueva_solicitud"
    if (
        "funcion" in texto
        or "opcion" in texto
        or "menu" in texto
        or "ayuda" in texto
        or "que podes" in texto
        or "que sabes" in texto
    ):
        return "start"
    return None


async def _ejecutar_accion_natural(
    accion: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    mensaje: str,
) -> bool:
    """Ejecuta la acción asociada al texto ingresado.

    Devuelve ``True`` si se manejó la acción, ``False`` si debe
    continuar con el flujo de conversación por defecto.
    """
    if accion == "comparar_fo":
        await iniciar_comparador(update, context)
        return True
    elif accion == "verificar_ingresos":
        await iniciar_verificacion_ingresos(update, context)
        return True
    elif accion == "cargar_tracking":
        await iniciar_carga_tracking(update, context)
        return True
    elif accion == "descargar_tracking":
        from .descargar_tracking import iniciar_descarga_tracking
        await iniciar_descarga_tracking(update, context)
        return True
    elif accion == "descargar_camaras":
        from .descargar_camaras import iniciar_descarga_camaras
        await iniciar_descarga_camaras(update, context)
        return True
    elif accion == "enviar_camaras_mail":
        from .enviar_camaras_mail import iniciar_envio_camaras_mail
        await iniciar_envio_camaras_mail(update, context)
        return True
    elif accion == "id_carrier":
        await iniciar_identificador_carrier(update, context)
        return True
    elif accion == "informe_repetitividad":
        await iniciar_repetitividad(update, context)
        return True
    elif accion == "analizar_incidencias":
        from .incidencias import iniciar_incidencias
        await iniciar_incidencias(update, context)
        return True
    elif accion == "informe_sla":
        from .informe_sla import iniciar_informe_sla
        await iniciar_informe_sla(update, context)
        return True
    elif accion == "start":
        from .start import start_handler
        await start_handler(update, context)
        return True
    elif accion == "otro":
        texto = normalizar_texto(mensaje or "")
        if "otro" in texto:
            UserState.set_mode(update.effective_user.id, "sandy")
            await responder_registrando(
                update.message,
                update.effective_user.id,
                mensaje,
                "¿Para qué me jodés? Indique su pregunta o solicitud. Si no puedo hacerla, se enviará como solicitud de implementación.",
                "otro",
            )
            return True
        return False
    elif accion == "nueva_solicitud":
        UserState.set_mode(update.effective_user.id, "sandy")
        UserState.set_waiting_detail(update.effective_user.id, True)
        context.user_data["nueva_solicitud"] = True
        await responder_registrando(
            update.message,
            update.effective_user.id,
            accion,
            "✍️ Escribí el detalle de la solicitud y la registraré para revisión.",
            "nueva_solicitud",
        )
        return True
    else:
        return True
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


def _generar_prompt_por_animo(mensaje: str, puntaje: int) -> str:
    """Devuelve un prompt según el contador de interacciones"""
    if puntaje <= 15:
        return (
            "Respondé de forma muy amable y cordial. Mantené un tono positivo y "
            f"amigable.\n\nUsuario: {mensaje}"
        )
    if puntaje <= 30:
        return (
            "Respondé de manera cordial, educada y simple sin extenderte demasiado."
            f"\n\nUsuario: {mensaje}"
        )
    if puntaje <= 60:
        return (
            "Respondé con todo el detalle posible y con intención de enseñar y ayudar."
            f"\n\nUsuario: {mensaje}"
        )
    if puntaje <= 80:
        return _generar_prompt_malhumorado(mensaje) + " Explicá con mucho detalle."
    return _generar_prompt_malhumorado(mensaje) + " Sé muy directo y fastidioso."
