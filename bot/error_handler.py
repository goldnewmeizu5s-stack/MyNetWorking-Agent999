"""Send errors and debug info to admin via Telegram."""
import logging
import traceback

from aiogram import Bot

logger = logging.getLogger(__name__)
MAX_TG_MSG = 4096


class ErrorForwarder:
    """Forwards errors and debug info to admin in Telegram."""

    def __init__(self, bot: Bot, admin_id: int):
        self.bot = bot
        self.admin_id = admin_id

    async def send_error(self, context: str, error: Exception, extra: str = "") -> None:
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        tb_str = "".join(tb)[-1500:]
        text = (
            f"🚨 <b>Error in {context}</b>\n\n"
            f"<b>Type:</b> {type(error).__name__}\n"
            f"<b>Message:</b> {str(error)[:500]}\n"
        )
        if extra:
            text += f"\n<b>Extra:</b>\n<pre>{self._escape(extra[:1000])}</pre>\n"
        text += f"\n<b>Traceback:</b>\n<pre>{self._escape(tb_str)}</pre>"
        await self._send(text)

    async def send_debug(self, title: str, data: str) -> None:
        text = f"🔍 <b>{title}</b>\n\n<pre>{self._escape(data[:3500])}</pre>"
        await self._send(text)

    async def send_info(self, text: str) -> None:
        await self._send(text[:MAX_TG_MSG])

    async def _send(self, text: str) -> None:
        try:
            if len(text) > MAX_TG_MSG:
                for i in range(0, len(text), MAX_TG_MSG):
                    chunk = text[i:i + MAX_TG_MSG]
                    await self.bot.send_message(self.admin_id, chunk, parse_mode="HTML")
            else:
                await self.bot.send_message(self.admin_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to send error to admin: %s", e)

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
