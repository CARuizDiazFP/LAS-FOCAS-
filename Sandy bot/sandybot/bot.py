"""
Módulo principal del bot Sandy
"""

import logging
import asyncio
from typing import Dict, Any
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from .config import config
from .gpt_handler import gpt
from .handlers import (
    start_handler,
    callback_handler,
    message_handler,
    document_handler,
    voice_handler,
    iniciar_comparador,
    procesar_comparacion,
    iniciar_carga_tracking,
    iniciar_descarga_tracking,
    iniciar_envio_camaras_mail,
)
from .handlers import (
    agregar_destinatario,
    eliminar_destinatario,
    listar_destinatarios,
    listar_carriers,
    agregar_carrier,
    registrar_tarea_programada,
    listar_tareas,
    detectar_tarea_mail,
    procesar_correos,
)

logger = logging.getLogger(__name__)


class SandyBot:
    """Clase principal del bot"""

    def __init__(self):
        """Inicializa el bot y sus handlers"""
        self.app = Application.builder().token(config.TELEGRAM_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Configura los handlers del bot"""
        # Comandos básicos
        self.app.add_handler(CommandHandler("start", start_handler))
        self.app.add_handler(CommandHandler("comparar_fo", iniciar_comparador))
        self.app.add_handler(CommandHandler("procesar", procesar_comparacion))
        self.app.add_handler(CommandHandler("cargar_tracking", iniciar_carga_tracking))
        self.app.add_handler(
            CommandHandler("descargar_tracking", iniciar_descarga_tracking)
        )

        self.app.add_handler(
            CommandHandler("agregar_destinatario", agregar_destinatario)
        )
        self.app.add_handler(
            CommandHandler("eliminar_destinatario", eliminar_destinatario)
        )
        self.app.add_handler(
            CommandHandler("listar_destinatarios", listar_destinatarios)
        )
        self.app.add_handler(
            CommandHandler("registrar_tarea", registrar_tarea_programada)
        )
        self.app.add_handler(CommandHandler("listar_carriers", listar_carriers))
        self.app.add_handler(CommandHandler("agregar_carrier", agregar_carrier))
        self.app.add_handler(CommandHandler("listar_tareas", listar_tareas))
        self.app.add_handler(CommandHandler("detectar_tarea", detectar_tarea_mail))
        self.app.add_handler(CommandHandler("procesar_correos", procesar_correos))

        # Callbacks de botones
        self.app.add_handler(CallbackQueryHandler(callback_handler))

        # Mensajes de texto
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
        )

        # Documentos
        self.app.add_handler(MessageHandler(filters.Document.ALL, document_handler))

        # Mensajes de voz
        self.app.add_handler(MessageHandler(filters.VOICE, voice_handler))

        # Error handler
        self.app.add_error_handler(self._error_handler)

    async def _error_handler(self, update: Update, context: Any):
        """Maneja errores globales del bot"""
        logger.error("Error procesando update: %s", context.error)
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "😤 Ocurrió un error inesperado. "
                "¿Por qué no intentás más tarde? #NoMeMolestes"
            )

    def run(self):
        """Inicia el bot en modo polling"""
        logger.info("🤖 Iniciando SandyBot...")
        self.app.run_polling()
