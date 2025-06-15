# Nombre de archivo: __init__.py
# Ubicación de archivo: Sandy bot/sandybot/handlers/__init__.py
# User-provided custom instructions
"""
Handlers del bot Sandy
"""

from .callback import callback_handler
from .cargar_tracking import guardar_tracking_servicio, iniciar_carga_tracking
from .carriers import (
    actualizar_carrier,
    agregar_carrier,
    eliminar_carrier,
    listar_carriers,
)
from .comparador import iniciar_comparador, procesar_comparacion, recibir_tracking
from .descargar_camaras import enviar_camaras_servicio, iniciar_descarga_camaras
from .descargar_tracking import enviar_tracking_servicio, iniciar_descarga_tracking
from .destinatarios import (
    agregar_destinatario,
    eliminar_destinatario,
    listar_destinatarios,
    listar_destinatarios_por_carrier,
)
from .detectar_tarea_mail import detectar_tarea_mail
from .document import document_handler
from .enviar_camaras_mail import iniciar_envio_camaras_mail, procesar_envio_camaras_mail
from .id_carrier import iniciar_identificador_carrier, procesar_identificador_carrier
from .identificador_tarea import (
    iniciar_identificador_tarea,
    procesar_identificador_tarea,
)
from .incidencias import iniciar_incidencias, procesar_incidencias
from .informe_sla import (
    actualizar_plantilla_sla,
    iniciar_informe_sla,
    procesar_informe_sla,
)
from .ingresar_tarea import ingresar_tarea
from .ingresos import iniciar_verificacion_ingresos, procesar_ingresos
from .listar_tareas import listar_tareas
from .message import message_handler
from .procesar_correos import procesar_correos
from .reenviar_aviso import reenviar_aviso
from .registro_ingresos import guardar_registro, iniciar_registro_ingresos
from .repetitividad import procesar_repetitividad
from .start import start_handler
from .supermenu import depurar_duplicados, listar_camaras
from .supermenu import listar_carriers as listar_carriers_cdb
from .supermenu import (
    listar_clientes,
    listar_conversaciones,
    listar_ingresos,
    listar_reclamos,
    listar_servicios,
    listar_tareas_programadas,
    listar_tareas_servicio,
    supermenu,
)
from .tarea_programada import registrar_tarea_programada
from .voice import voice_handler

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
    "ingresar_tarea",
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
