# + Nombre de archivo: estado.py
# + Ubicación de archivo: Sandy bot/sandybot/handlers/estado.py
# User-provided custom instructions
"""
Manejo del estado de usuarios del bot
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from sandybot.config import config
from ..utils import cargar_json, guardar_json

@dataclass
class UserData:
    """Datos de estado de un usuario"""
    mode: str = ""
    tracking_file: Optional[str] = None
    ingresos_file: Optional[str] = None
    waiting_for_detail: bool = False
    last_interaction: datetime = field(default_factory=datetime.now)
    interactions: int = 0

class UserState:
    """Gestiona el estado de los usuarios del bot"""
    _users: Dict[int, UserData] = {}
    _contador: Dict[str, int] = cargar_json(config.ARCHIVO_INTERACCIONES)

    @classmethod
    def get_user(cls, user_id: int) -> UserData:
        """Obtiene o crea datos de usuario"""
        if user_id not in cls._users:
            count = cls._contador.get(str(user_id), 0)
            cls._users[user_id] = UserData(interactions=count)
        return cls._users[user_id]

    @classmethod
    def set_mode(cls, user_id: int, mode: str) -> None:
        """Establece el modo de un usuario"""
        user = cls.get_user(user_id)
        user.mode = mode
        user.last_interaction = datetime.now()

    @classmethod
    def get_mode(cls, user_id: int) -> str:
        """Obtiene el modo actual de un usuario"""
        return cls.get_user(user_id).mode

    @classmethod
    def set_tracking(cls, user_id: int, filepath: str) -> None:
        """Guarda la ruta del archivo de tracking"""
        user = cls.get_user(user_id)
        user.tracking_file = filepath
        user.last_interaction = datetime.now()

    @classmethod
    def set_ingresos(cls, user_id: int, filepath: str) -> None:
        """Guarda la ruta del archivo de ingresos"""
        user = cls.get_user(user_id)
        user.ingresos_file = filepath
        user.last_interaction = datetime.now()

    @classmethod
    def set_waiting_detail(cls, user_id: int, waiting: bool) -> None:
        """Establece si el usuario está esperando detalles"""
        user = cls.get_user(user_id)
        user.waiting_for_detail = waiting
        user.last_interaction = datetime.now()

    @classmethod
    def is_waiting_detail(cls, user_id: int) -> bool:
        """Verifica si el usuario está esperando detalles"""
        return cls.get_user(user_id).waiting_for_detail

    @classmethod
    def increment_interaction(cls, user_id: int) -> int:
        """Aumenta el contador de interacciones y lo persiste"""
        count = cls._contador.get(str(user_id), 0)
        if count < 100:
            count += 1
        cls._contador[str(user_id)] = count
        guardar_json(cls._contador, config.ARCHIVO_INTERACCIONES)
        user = cls.get_user(user_id)
        user.interactions = count
        user.last_interaction = datetime.now()
        return count

    @classmethod
    def get_interaction(cls, user_id: int) -> int:
        """Devuelve el contador actual de interacciones"""
        user = cls.get_user(user_id)
        return user.interactions

    @classmethod
    def clear_user(cls, user_id: int) -> None:
        """Limpia el estado de un usuario"""
        if user_id in cls._users:
            del cls._users[user_id]

    @classmethod
    def cleanup_old_sessions(cls, max_age_hours: int = 24) -> None:
        """Limpia sesiones antiguas"""
        now = datetime.now()
        to_remove = []
        for user_id, data in cls._users.items():
            age = (now - data.last_interaction).total_seconds() / 3600
            if age > max_age_hours:
                to_remove.append(user_id)
        
        for user_id in to_remove:
            cls.clear_user(user_id)
