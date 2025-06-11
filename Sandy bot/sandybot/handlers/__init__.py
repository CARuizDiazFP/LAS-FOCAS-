"""
Handlers del bot Sandy
"""
from .start import start_handler
from .callback import callback_handler
from .message import message_handler
from .document import document_handler
from .voice import voice_handler
from .ingresos import iniciar_verificacion_ingresos, procesar_ingresos
from .registro_ingresos import iniciar_registro_ingresos, guardar_registro
from .repetitividad import procesar_repetitividad
from .comparador import iniciar_comparador, recibir_tracking, procesar_comparacion
from .cargar_tracking import iniciar_carga_tracking, guardar_tracking_servicio
from .descargar_tracking import iniciar_descarga_tracking, enviar_tracking_servicio
from .descargar_camaras import iniciar_descarga_camaras, enviar_camaras_servicio
from .enviar_camaras_mail import (
    iniciar_envio_camaras_mail,
    procesar_envio_camaras_mail,
)
from .id_carrier import iniciar_identificador_carrier, procesar_identificador_carrier
from .incidencias import iniciar_incidencias, procesar_incidencias
from .destinatarios import (
    agregar_destinatario,
    eliminar_destinatario,
    listar_destinatarios,
)
from .tarea_programada import registrar_tarea_programada
from .detectar_tarea_mail import detectar_tarea_mail

__all__ = [
    'start_handler',
    'callback_handler',
    'message_handler',
    'document_handler',
    'voice_handler',
    'iniciar_verificacion_ingresos',
    'procesar_ingresos',
    'iniciar_registro_ingresos',
    'guardar_registro',
    'procesar_repetitividad',
    'iniciar_comparador',
    'recibir_tracking',
    'procesar_comparacion',
    'iniciar_carga_tracking',
    'guardar_tracking_servicio',
    'iniciar_descarga_tracking',
    'enviar_tracking_servicio',
    'iniciar_descarga_camaras',
    'enviar_camaras_servicio',
    'iniciar_envio_camaras_mail',
    'procesar_envio_camaras_mail',
    'iniciar_identificador_carrier',
    'procesar_identificador_carrier',
    'iniciar_incidencias',
    'procesar_incidencias',
    'agregar_destinatario',
    'eliminar_destinatario',
    'listar_destinatarios'
    , 'registrar_tarea_programada'
    , 'detectar_tarea_mail'
]
