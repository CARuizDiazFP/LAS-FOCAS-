# + Nombre de archivo: email_utils.py
# + Ubicación de archivo: Sandy bot/sandybot/email_utils.py
# User-provided custom instructions
"""Funciones utilitarias para el manejo de correos."""

from pathlib import Path
import logging
import smtplib
import os
import re
import tempfile
from datetime import datetime
from email.message import EmailMessage

# Para exportar mensajes .msg en Windows se usan estos módulos opcionales
try:
    import win32com.client as win32  # pragma: no cover - solo disponible en Windows
    import pythoncom  # pragma: no cover - solo disponible en Windows
except Exception:  # pragma: no cover - entornos sin win32
    win32 = None
    pythoncom = None

from .config import config
from .gpt_handler import gpt

SIGNATURE_PATH = Path(config.SIGNATURE_PATH) if config.SIGNATURE_PATH else None
from .database import (
    SessionLocal,
    Cliente,
    Servicio,
    TareaProgramada,
    Carrier,
    obtener_cliente_por_nombre,
    crear_tarea_programada,    # (+) Necesario en procesar_correo_a_tarea
)
from .utils import (
    cargar_json,
    guardar_json,
    incrementar_contador,
)

logger = logging.getLogger(__name__)


def _limpiar_correo(texto: str) -> str:
    """Elimina firmas y bloques innecesarios del texto del correo.

    Se detiene cuando encuentra frases típicas de aviso legal o
    confidencialidad, por ejemplo «confidentiality notice» o
    «este correo es privado».
    """
    lineas: list[str] = []
    for linea in texto.splitlines():
        l = linea.strip()
        if not l:
            continue
        if re.search(
            r"disclaimer|confidencial|aviso legal|confidentiality notice|"
            r"correo(?:\s+electronico)?\s*(?:es\s+)?privado",
            l,
            re.I,
        ):
            break
        lineas.append(l)
    return "\n".join(lineas)


def cargar_destinatarios(cliente_id: int, carrier: str | None = None) -> list[str]:
    """Obtiene la lista de correos para el cliente indicado."""

    with SessionLocal() as session:
        cli = session.get(Cliente, cliente_id)
        if not cli:
            return []
        if carrier:
            if cli.destinatarios_carrier:
                lista = cli.destinatarios_carrier.get(carrier)
                if lista is not None:
                    return lista
            return []
        return cli.destinatarios if cli.destinatarios else []


def guardar_destinatarios(
    destinatarios: list[str], cliente_id: int, carrier: str | None = None
) -> bool:
    """Actualiza los correos de un cliente."""

    with SessionLocal() as session:
        cli = session.get(Cliente, cliente_id)
        if not cli:
            return False
        if carrier:
            mapa = dict(cli.destinatarios_carrier or {})
            if destinatarios:
                mapa[carrier] = destinatarios
            else:
                mapa.pop(carrier, None)
            cli.destinatarios_carrier = mapa
        else:
            cli.destinatarios = destinatarios
        session.commit()
        return True


def agregar_destinatario(
    correo: str, cliente_id: int, carrier: str | None = None
) -> bool:
    """Agrega ``correo`` al listado del cliente si no existe."""

    lista = cargar_destinatarios(cliente_id, carrier)
    if correo not in lista:
        lista.append(correo)
    return guardar_destinatarios(lista, cliente_id, carrier)


def eliminar_destinatario(
    correo: str, cliente_id: int, carrier: str | None = None
) -> bool:
    """Elimina ``correo`` del listado si existe."""

    lista = cargar_destinatarios(cliente_id, carrier)
    if correo not in lista:
        return False
    lista.remove(correo)
    return guardar_destinatarios(lista, cliente_id, carrier)


def enviar_correo(
    asunto: str,
    cuerpo: str,
    cliente_id: int,
    carrier: str | None = None,
    *,
    host: str | None = None,
    port: int | None = None,
    debug: bool | None = None,
) -> bool:
    """Envía un correo simple a los destinatarios almacenados."""
    correos = cargar_destinatarios(cliente_id, carrier)
    if not correos:
        return False

    host = host or config.SMTP_HOST
    port = port or config.SMTP_PORT

    msg = f"Subject: {asunto}\n\n{cuerpo}"
    try:
        usar_ssl = port == 465
        smtp_cls = smtplib.SMTP_SSL if usar_ssl else smtplib.SMTP
        with smtp_cls(host, port) as smtp:
            activar_debug = (
                debug
                if debug is not None
                else os.getenv("SMTP_DEBUG", "0").lower() in {"1", "true", "yes"}
            )
            if activar_debug:
                smtp.set_debuglevel(1)
            if not usar_ssl and config.SMTP_USE_TLS:
                smtp.starttls()
            if config.SMTP_USER and config.SMTP_PASSWORD:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.sendmail(config.EMAIL_FROM or config.SMTP_USER, correos, msg)
        return True
    except Exception as e:  # pragma: no cover - depende del entorno
        logger.error("Error enviando correo: %s", e)
        return False


def enviar_excel_por_correo(
    destinatario: str,
    ruta_excel: str,
    *,
    asunto: str = "Reporte SandyBot",
    cuerpo: str = "Adjunto el archivo Excel.",
) -> bool:
    """Envía un archivo Excel por correo usando la configuración SMTP.

    Parameters
    ----------
    destinatario: str
        Dirección de correo del destinatario.
    ruta_excel: str
        Ruta al archivo Excel a adjuntar.
    asunto: str, optional
        Asunto del mensaje.
    cuerpo: str, optional
        Texto del cuerpo del correo.

    Returns
    -------
    bool
        ``True`` si el envío fue exitoso, ``False`` en caso de error.
    """
    try:
        ruta = Path(ruta_excel)
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {ruta}")

        msg = EmailMessage()

        smtp_user = config.SMTP_USER
        smtp_host = config.SMTP_HOST
        smtp_port = config.SMTP_PORT
        smtp_pwd = config.SMTP_PASSWORD
        use_tls = config.SMTP_USE_TLS

        msg["From"] = config.EMAIL_FROM or smtp_user or ""

        msg["To"] = destinatario
        msg["Subject"] = asunto
        msg.set_content(cuerpo)

        with open(ruta, "rb") as f:
            datos = f.read()
        msg.add_attachment(
            datos,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=ruta.name,
        )

        usar_ssl = smtp_port == 465
        smtp_cls = smtplib.SMTP_SSL if usar_ssl else smtplib.SMTP
        server = smtp_cls(smtp_host, smtp_port)
        if not usar_ssl and use_tls:
            server.starttls()
        if smtp_user and smtp_pwd:
            server.login(smtp_user, smtp_pwd)

        server.send_message(msg)
        server.quit()
        return True

    except Exception as e:  # pragma: no cover - errores dependen del entorno
        logger.error("Error enviando correo: %s", e)
        return False


def generar_nombre_camaras(id_servicio: int) -> str:
    """Genera el nombre base para un Excel de cámaras."""
    nro = incrementar_contador("camaras")
    fecha = datetime.now().strftime("%d%m%Y")
    return f"Camaras_{id_servicio}_{fecha}_{nro:02d}"


def generar_nombre_tracking(id_servicio: int) -> str:
    """Genera el nombre base para un archivo de tracking."""
    nro = incrementar_contador("tracking")
    fecha = datetime.now().strftime("%d%m%Y")
    return f"Tracking_{id_servicio}_{fecha}_{nro:02d}"


def obtener_tracking_reciente(id_servicio: int) -> str | None:
    """Devuelve la ruta del tracking más reciente del histórico."""
    patron = re.compile(rf"tracking_{id_servicio}_(\d{{8}}_\d{{6}})\.txt")
    archivos = []
    for archivo in config.HISTORICO_DIR.glob(f"tracking_{id_servicio}_*.txt"):
        m = patron.match(archivo.name)
        if m:
            archivos.append((m.group(1), archivo))
    if archivos:
        archivos.sort(key=lambda x: x[0], reverse=True)
        return str(archivos[0][1])
    from .database import obtener_servicio

    servicio = obtener_servicio(id_servicio)
    if servicio and servicio.ruta_tracking and os.path.exists(servicio.ruta_tracking):
        return servicio.ruta_tracking
    return None


def enviar_tracking_reciente_por_correo(
    destinatario: str,
    id_servicio: int,
    *,
    asunto: str = "Tracking reciente",
    cuerpo: str = "Adjunto el tracking solicitado.",
) -> bool:
    """Envía por correo el tracking más reciente registrado."""
    ruta = obtener_tracking_reciente(id_servicio)
    if not ruta:
        return False
    nombre = generar_nombre_tracking(id_servicio) + ".txt"
    from .correo import enviar_email

    return enviar_email([destinatario], asunto, cuerpo, ruta, nombre)


def generar_archivo_msg(
    tarea: TareaProgramada,
    cliente: Cliente,
    servicios: list[Servicio],
    ruta: str,
) -> tuple[str, str]:
    """Genera un archivo *.msg* (Outlook) o texto plano con la tarea programada.

    Returns
    -------
    tuple[str, str]
        Ruta del archivo generado y el texto completo del aviso.

    - Con ``win32`` + ``pythoncom`` disponibles → se crea un verdadero **MSG**,
      se establece asunto, cuerpo y se agrega firma (si existe).
    - Sin estas librerías → se genera un **.txt** de respaldo.
    """

    # 📨 Contenido base
    carrier_nombre = None
    if tarea.carrier_id:
        with SessionLocal() as s:
            car = s.get(Carrier, tarea.carrier_id)
            carrier_nombre = car.nombre if car else None
    if not carrier_nombre:
        ids = {s.carrier_id for s in servicios if s.carrier_id}
        if len(ids) == 1:
            with SessionLocal() as s:
                car = s.get(Carrier, ids.pop())
                carrier_nombre = car.nombre if car else None

    lineas = [
        "Estimado Cliente, nuestro partner nos da aviso de la siguiente tarea programada:",
    ]
    if carrier_nombre:
        lineas.append(f"Carrier: {carrier_nombre}")
    lineas.extend(
        [
            f"Inicio: {tarea.fecha_inicio}",
            f"Fin: {tarea.fecha_fin}",
            f"Tipo de tarea: {tarea.tipo_tarea}",
        ]
    )
    if tarea.tiempo_afectacion:
        lineas.append(f"Tiempo de afectación: {tarea.tiempo_afectacion}")
    if tarea.descripcion:
        lineas.append(f"Descripción: {tarea.descripcion}")

    lista_servicios = ", ".join(str(s.id) for s in servicios)
    lineas.append(f"Servicios afectados: {lista_servicios}")
    contenido = "\n".join(lineas)

    # 🪟 Intento de generar MSG con Outlook
    if win32 is not None:
        try:
            # Inicialización COM explícita si pythoncom está presente
            if pythoncom is not None:
                pythoncom.CoInitialize()

            outlook = win32.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.Subject = f"Aviso de tarea programada - {cliente.nombre}"

            # Firma opcional
            firma = ""
            if SIGNATURE_PATH and SIGNATURE_PATH.exists():
                try:
                    firma = SIGNATURE_PATH.read_text(encoding="utf-8")
                except Exception as e:  # pragma: no cover
                    logger.warning("No se pudo leer la firma: %s", e)

            mail.Body = contenido + ("\n\n" + firma if firma else "")
            mail.SaveAs(ruta, 3)  # 3 = olMSGUnicode
            # Copia temporal de texto para algunas pruebas
            temp_txt = f"{ruta}.txt"
            try:
                with open(temp_txt, "w", encoding="utf-8") as txt:
                    txt.write(mail.Body)
            except Exception as e:  # pragma: no cover - depende del entorno
                logger.error("No se pudo escribir el texto: %s", e)
            finally:
                # Eliminar el archivo auxiliar para no dejar residuos
                try:
                    os.remove(temp_txt)
                except OSError:
                    pass
            return ruta, mail.Body
        except Exception as e:  # pragma: no cover
            logger.error("Error generando archivo MSG: %s", e)
        finally:
            # Cerramos el entorno COM si corresponde
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    # 📝 Fallback a texto plano
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)

    return ruta, contenido


async def procesar_correo_a_tarea(
    texto: str, cliente_nombre: str, carrier_nombre: str | None = None
) -> tuple[TareaProgramada, Cliente, Path, str]:

    """Analiza el correo y registra la tarea programada."""

    texto_limpio = _limpiar_correo(texto)

    ejemplo = (
        "Ejemplo correo:\n"
        "Inicio: 02/01/2024 08:00\n"
        "Fin: 02/01/2024 10:00\n"
        "Trabajo: Actualización de equipos\n"
        "Servicios: 76208, 78333\n"
        "\nRespuesta esperada:\n"
        '{"inicio": "2024-01-02 08:00", "fin": "2024-01-02 10:00", '
        '"tipo": "Actualización de equipos", "afectacion": null, '
        '"descripcion": null, "ids": ["76208", "78333"]}'
    )

    prompt = (
        "Sos un analista que extrae datos de mantenimientos programados. "
        "Devolvé únicamente un JSON con las claves inicio, fin, tipo, "
        "afectacion, descripcion e ids (lista de servicios).\n\n"
        f"{ejemplo}\n\nCorreo:\n{texto_limpio}"
    )

    esquema = {
        "type": "object",
        "properties": {
            "inicio": {"type": "string"},
            "fin": {"type": "string"},
            "tipo": {"type": "string"},
            "afectacion": {"type": "string"},
            "descripcion": {"type": "string"},
            "ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["inicio", "fin", "tipo", "ids"],
    }

    try:
        respuesta = await gpt.consultar_gpt(prompt)
        datos = await gpt.procesar_json_response(respuesta, esquema)
        if not datos:
            raise ValueError("JSON inválido")
        if os.getenv("SANDY_ENV") == "dev":
            logger.debug("GPT JSON: %s", datos)
    except Exception as exc:  # pragma: no cover - fallo externo
        raise ValueError("No se pudo extraer la tarea del correo") from exc

    def _parse_fecha(valor: str) -> datetime:
        formatos = (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
        )
        for fmt in formatos:
            try:
                return datetime.strptime(valor.replace("T", " "), fmt)
            except ValueError:
                continue
        return datetime.fromisoformat(valor.replace("T", " "))

    try:
        inicio = _parse_fecha(str(datos["inicio"]))
        fin = _parse_fecha(str(datos["fin"]))
    except Exception as exc:
        raise ValueError("Fechas con formato inválido") from exc
    if inicio >= fin:
        raise ValueError("La fecha de inicio debe ser anterior al fin")

    tipo = datos["tipo"]
    ids_brutos = [str(i) for i in datos.get("ids", [])]
    afectacion = datos.get("afectacion")
    descripcion = datos.get("descripcion")

    with SessionLocal() as session:
        cliente = obtener_cliente_por_nombre(cliente_nombre)
        if not cliente:
            cliente = Cliente(nombre=cliente_nombre)
            session.add(cliente)
            session.commit()
            session.refresh(cliente)

        carrier = None
        if carrier_nombre:
            carrier = (
                session.query(Carrier)
                .filter(Carrier.nombre == carrier_nombre)
                .first()
            )
            if not carrier:
                carrier = Carrier(nombre=carrier_nombre)
                session.add(carrier)
                session.commit()
                session.refresh(carrier)

        servicios: list[Servicio] = []
        for ident in ids_brutos:
            srv = None
            if ident.isdigit():
                srv = session.get(Servicio, int(ident))
            if not srv:
                srv = (
                    session.query(Servicio)
                    .filter(Servicio.id_carrier == ident)
                    .first()
                )
            if srv:
                servicios.append(srv)
            else:
                logger.warning("Servicio %s no encontrado", ident)

        tarea = crear_tarea_programada(
            inicio,
            fin,
            tipo,
            [s.id for s in servicios],
            carrier_id=carrier.id if carrier else None,
            tiempo_afectacion=afectacion,
            descripcion=descripcion,
        )
        if carrier:
            for srv in servicios:
                if srv:
                    srv.carrier_id = carrier.id
                    srv.carrier = carrier.nombre
            session.commit()

        nombre_arch = f"tarea_{tarea.id}.msg"
        ruta = Path(tempfile.gettempdir()) / nombre_arch

        ruta_str, cuerpo = generar_archivo_msg(
            tarea,
            cliente,
            [s for s in servicios if s],
            str(ruta),
        )
        ruta_msg = Path(ruta_str)

        return tarea, cliente, ruta_msg, cuerpo
