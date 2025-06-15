# Nombre de archivo: telegram_stub.py
# Ubicación de archivo: tests/telegram_stub.py
# User-provided custom instructions
from types import ModuleType, SimpleNamespace
from pathlib import Path
import sys

class Message:
    def __init__(self, text="", document=None, voice=None):
        self.text = text
        self.document = document
        self.documents = [document] if document else []
        self.documento = None
        self.voice = voice
        self.sent = None
        self.from_user = SimpleNamespace(id=1)

    async def reply_document(self, f, filename=None):
        self.sent = filename
        self.documento = filename

    async def reply_text(self, *a, **k):
        pass

class CallbackQuery:
    def __init__(self, message=None):
        self.message = message
        self.from_user = SimpleNamespace(id=1)

    async def answer(self, *a, **k):
        pass

class Document:
    def __init__(self, file_name="file.txt", content=""):
        self.file_name = file_name
        self._content = content

    async def get_file(self):
        class F:
            async def download_to_drive(_, path):
                Path(path).write_text(self._content)
        return F()

class Update:
    def __init__(self, message=None, edited_message=None, callback_query=None):
        self.message = message
        self.edited_message = edited_message
        self.callback_query = callback_query
        self.effective_user = getattr(message, "from_user", SimpleNamespace(id=1))

class InlineKeyboardButton:
    def __init__(self, *a, **k):
        pass

class InlineKeyboardMarkup:
    def __init__(self, *a, **k):
        pass

class ReplyKeyboardMarkup:
    def __init__(self, *a, **k):
        self.keyboard = a[0] if a else []

telegram_mod = ModuleType("telegram")
telegram_mod.Update = Update
telegram_mod.Message = Message
telegram_mod.CallbackQuery = CallbackQuery
telegram_mod.InlineKeyboardButton = InlineKeyboardButton
telegram_mod.InlineKeyboardMarkup = InlineKeyboardMarkup
telegram_mod.ReplyKeyboardMarkup = ReplyKeyboardMarkup
telegram_mod.Document = Document
sys.modules.setdefault("telegram", telegram_mod)

telegram_ext = ModuleType("telegram.ext")
class ContextTypes:
    DEFAULT_TYPE = object
telegram_ext.ContextTypes = ContextTypes
sys.modules.setdefault("telegram.ext", telegram_ext)
