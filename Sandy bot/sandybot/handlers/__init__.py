# Nombre de archivo: __init__.py
# Ubicación de archivo: Sandy bot/sandybot/handlers/__init__.py
# User-provided custom instructions
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
from .informe_sla import (
    iniciar_informe_sla,
    procesar_informe_sla,
    actualizar_plantilla_sla,
)
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
    listar_destinatarios_por_carrier,
)
from .carriers import (
    listar_carriers,
    agregar_carrier,
    eliminar_carrier,
    actualizar_carrier,
)
from .tarea_programada import registrar_tarea_programada
from .detectar_tarea_mail import detectar_tarea_mail
from .procesar_correos import procesar_correos
from .identificador_tarea import (
    iniciar_identificador_tarea,
    procesar_identificador_tarea,
)
from .reenviar_aviso import reenviar_aviso
from .listar_tareas import listar_tareas
from .supermenu import (
    supermenu,
    listar_servicios,
    listar_reclamos,
    listar_camaras,
    depurar_duplicados,
    listar_clientes,
    listar_carriers as listar_carriers_cdb,
    listar_conversaciones,
    listar_ingresos,
    listar_tareas_programadas,
    listar_tareas_servicio,
)

__all__ = [
    "start_handler",
    "callback_handler",
    "message_handler",
    "document_handler",
    "voice_handler",
    "iniciar_verificacion_ingresos",
    "procesar_ingresos",
    "iniciar_registro_ingresos",
    "guardar_registro",
    "procesar_repetitividad",
    "iniciar_comparador",
    "recibir_tracking",
    "procesar_comparacion",
    "iniciar_carga_tracking",
    "guardar_tracking_servicio",
    "iniciar_descarga_tracking",
    "enviar_tracking_servicio",
    "iniciar_descarga_camaras",
    "enviar_camaras_servicio",
    "iniciar_envio_camaras_mail",
    "procesar_envio_camaras_mail",
    "iniciar_identificador_carrier",
    "procesar_identificador_carrier",
    "iniciar_identificador_tarea",
    "procesar_identificador_tarea",
    "iniciar_incidencias",
    "procesar_incidencias",
    "iniciar_informe_sla",
    "procesar_informe_sla",
    "actualizar_plantilla_sla",
    "agregar_destinatario",
    "eliminar_destinatario",
    "listar_destinatarios",
    "listar_destinatarios_por_carrier",
    "agregar_carrier",
    "eliminar_carrier",
    "listar_carriers",
    "actualizar_carrier",
    "registrar_tarea_programada",
    "listar_tareas",
    "detectar_tarea_mail",
    "procesar_correos",
    "reenviar_aviso",
    "supermenu",
    "listar_servicios",
    "listar_reclamos",
    "listar_camaras",
    "depurar_duplicados",
    "listar_clientes",
    "listar_carriers_cdb",
    "listar_conversaciones",
    "listar_ingresos",
    "listar_tareas_programadas",
    "listar_tareas_servicio",
]
