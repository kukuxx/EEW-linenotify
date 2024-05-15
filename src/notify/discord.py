import asyncio

import discord

from ..earthquake.eew import EEW
from ..logging import Logger
from ..utils import MISSING
from .abc import NotificationClient


class EEWMessages:
    """
    Represents discord messages with EEW data.
    """

    __slots__ = ("eew", "messages", "__info_embed_cache", "__intensity_embed_cache")

    def __init__(self, eew: EEW, messages: list[discord.Message]) -> None:
        """
        Initialize a new discord message.

        :param eew: The EEW instance.
        :type eew: EEW
        :param message: The discord message.
        :type message: discord.Message
        """
        self.eew = eew
        self.messages = messages
        self.__info_embed_cache: discord.Embed = None
        self.__intensity_embed_cache: discord.Embed = None

    def info_embed(self) -> discord.Embed:
        # cache
        if self.__info_embed_cache is not None:
            return self.__info_embed_cache

        # shortcut
        eew = self.eew
        eq = eew.earthquake
        self.__info_embed_cache = discord.Embed(
            title=f"地震速報　第{eew.serial}報{'(最終報)' if eew.final else ''}",
            description=f"""\
{eq.time.strftime("%m/%d %H:%M:%S")} 左右{f"於 {eq.location.display_name}附近 " if eq.location.display_name else ""}發生有感地震，慎防搖晃。
預估規模`{eq.mag}`，震源深度 {eq.depth}公里，最大震度{eq.max_intensity.display}""",
            color=0xFF0000,
        ).set_author(
            name="Taiwan Earthquake Early Warning",
            icon_url="https://cdn.discordapp.com/emojis/1018381096532070572.png",
        )
        return self.__info_embed_cache

    def intensity_embed(self) -> discord.Embed:
        # cache
        # if self.__intensity_embed_cache is not None:
        #     return self.__intensity_embed_cache

        self.__intensity_embed_cache = discord.Embed(
            title="震度等級預估",
            description="\n".join(
                (
                    f"{city}最大震度：{intensity.region.name} {intensity.intensity.display} "
                    f"<t:{intensity.distance.s_time.timestamp()}:R>內抵達"
                    if intensity.distance.s_left_time().seconds > 0
                    else "已抵達"
                )
                for city, intensity in self.eew.earthquake.city_max_intensity.items()
            ),
        )
        return self.__intensity_embed_cache

    async def _send_singal_message(self, channel: discord.TextChannel, mention: str = None):
        try:
            return await channel.send(mention, embed=self.__info_embed_cache)
        except Exception:
            return None

    async def _edit_singal_message(self, message: discord.Message):
        try:
            return await message.edit(embeds=[self.__info_embed_cache, self.intensity_embed()])
        except Exception:
            return None

    @classmethod
    async def send(
        cls,
        eew: EEW,
        notification_channels: list[dict[str, str | discord.TextChannel | None]],
    ) -> "EEWMessages":
        """
        Send a new discord message.

        :param eew: The EEW instance.
        :type eew: EEW
        :param channels: Discord channels.
        :type channels: list[discord.TextChannel]
        :param mention: The mention to send.
        :type mention: str
        :return: The new discord messages.
        :rtype: EEWMessage
        """
        self = cls(eew, [])
        self.info_embed()
        self.messages = list(
            filter(
                None,
                await asyncio.gather(
                    *(
                        self._send_singal_message(d["channel"], d["mention"])
                        for d in notification_channels
                    )
                ),
            )
        )
        return self

    async def edit(self) -> None:
        """
        Edit the discord messages to update S wave arrival time.
        """
        await asyncio.gather(*(self._edit_singal_message(message) for message in self.messages))

    async def update_eew(self, eew: EEW) -> None:
        """
        Edit the discord messages if EEW data is updated.

        :param eew: The EEW instance.
        :type eew: EEW
        """
        self.eew = eew
        self.__info_embed_cache = None
        self.info_embed()
        await self.edit()


class DiscordNotification(NotificationClient, discord.Bot):
    """
    Represents a discord notification client.
    """

    # eew-id: EEWMessages
    alerts: dict[str, EEWMessages] = {}

    def __init__(self, logger: Logger, config: dict, token: str) -> None:
        """
        Initialize a new discord notification client.

        :param logger: The logger instance.
        :type logger: Logger
        :param config: The configuration.
        :type config: dict
        :param token: The discord bot token.
        :type token: str
        """
        self.logger = logger
        self.config = config

        logger.disable("discord")  # avoid pycord shard info spamming the console

        self._client_ready = False
        intents = discord.Intents.default()
        super().__init__(owner_ids=self.config["discord"]["owners"], intents=intents)
        asyncio.create_task(self.start(token))

    async def get_or_fetch_channel(self, id: int, default=MISSING):
        try:
            return self.get_channel(id) or await self.fetch_channel(id)
        except Exception as e:
            if default is not MISSING:
                return default
            raise e

    async def on_ready(self) -> None:
        """
        The event that is triggered when the bot is ready.
        """
        if self._client_ready:
            return

        self.notification_channels: list[dict[str, str | discord.TextChannel | None]] = []
        for data in self.config["discord"]["channels"]:
            channel = await self.get_or_fetch_channel(data["id"])
            if channel is None:
                self.logger.warning(f"Ignore channel '{data['id']}' because it was not found.")
                continue
            mention = (
                None
                if not (m := data.get("mention"))
                else (f"<@&{m}>" if isinstance(m, int) else f"@{m.removeprefix('@')}")
            )
            self.notification_channels.append({"channel": channel, "mention": mention})

        self.logger.info(
            f"""Discord Bot started.
-------------------------
Logged in as: {self.user.name}#{self.user.discriminator} ({self.user.id})
 API Latency: {self.latency * 1000:.2f} ms
Guilds Count: {len(self.guilds)}
-------------------------"""
        )
        self._client_ready = True

    async def start(self, token: str, *, reconnect: bool = True) -> None:
        return await super().start(token, reconnect=reconnect)

    async def close(self) -> None:
        await super().close()
        self.logger.info("Discord Bot closed.")

    async def send_eew(self, eew: EEW) -> EEWMessages:
        m = await EEWMessages.send(EEW, self.notification_channels)
        self.alerts[eew.id, m]
        return m

    async def update_eew(self, eew: EEW) -> EEWMessages:
        m = self.alerts.get(eew.id)
        if m is None:
            m = await self.send_eew(eew)

        await m.update_eew(eew)
        return m
