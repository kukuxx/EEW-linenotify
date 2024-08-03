import re
import asyncio
from datetime import datetime
from typing import Optional

import aiohttp

from src import EEW, BaseNotificationClient, Settings, Config, Logger

LINE_NOTIFY_API = "https://notify-api.line.me/api/notify"


class LineNotifyClient(BaseNotificationClient):
    """
    Represents a [custom] EEW notification client.
    """

    def __init__(self, logger: Logger, config: Config,
                 notify_token: str) -> None:
        """
        Initialize a new [custom] notification client.

        :param logger: The logger instance.
        :type logger: Logger
        :param config: The configuration.
        :type config: Config
        :param notify_token: The LINE Notify API token.
        :type notify_token: str
        """
        self.logger = logger
        self.config = config
        self._notify_token = notify_token
        self._custom_set = Settings.get("customization")
        self.response_status: int = None
        self._region_intensity: Optional[dict[tuple[str, str],
                                              tuple[str, int]]] = {}

    def get_eew_message(self, eew: EEW):
        #取得EEW訊息並排版
        eq = eew.earthquake
        time_str = eq.time.strftime("%m月%d日 %H:%M:%S")
        # i = eew.serial - 1
        # title = f"\n速報更新{i}"
        content = (f"\n{time_str},\n發生規模 {eq.mag} 地震,\n編號{eew.id},"
                   f"\n震央位在{eq.location.display_name or eq.location},"
                   f"\n震源深度{eq.depth} 公里,\n最大震度{eq.max_intensity.display}")
        last = f"\n⚠️圖片僅供參考⚠️\n⚠️以氣象署為準⚠️"
        # provider = f"\n(發報單位: {eew.provider.display_name})"
        # if eew.serial > 1:
        #     _message = f"{title} {content} {provider}"
        # else:
        #     _message = f"{content} {provider}"
        _message = f"{content} {last}"
        return _message

    def get_region_intensity(self, eew: EEW):
        #取得各地震度和抵達時間
        customize = self._custom_set.get("enable")
        eq = eew.earthquake
        if not customize:
            for city, intensity in eq.city_max_intensity.items():
                if intensity.intensity.value > 0:
                    key = (city, intensity.region.name)
                    if eew.serial <= 1:
                        self._region_intensity[key] = (
                            intensity.intensity.display,
                            int(intensity.distance.s_arrival_time.timestamp()))
                    else:
                        # 更新震度不更新抵達時間
                        self._region_intensity[key] = (
                            intensity.intensity.display,
                            self._region_intensity[key][1])
        else:
            for city, intensity_list in eq.city_max_intensity.items():
                for intensity in intensity_list:
                    if intensity.intensity.value >= 0:
                        key = (city, intensity.region.name)
                        if eew.serial <= 1:
                            self._region_intensity[key] = (
                                intensity.intensity.display,
                                int(intensity.distance.s_arrival_time.
                                    timestamp()))
                        else:
                            self._region_intensity[key] = (
                                intensity.intensity.display,
                                self._region_intensity[key][1])

        return self._region_intensity

    def check_intensity(self):
        threshold = self._custom_set.get("threshold")
        for key, value in self._region_intensity.items():
            intensity_value, _ = value
            match = re.search(r'\d+', intensity_value)
            if int(match.group()) >= threshold:
                return True
            else:
                return False

    async def _send_region_intensity(self, eew: EEW):
        #發送各地震度和抵達時間並排版
        eq = eew.earthquake
        await eq._intensity_calculated.wait()
        if eq._intensity_calculated.is_set():
            self.get_region_intensity(eew)
        if self._region_intensity is not None and self.check_intensity():
            current_time = int(datetime.now().timestamp())
            if eew.serial <= 1:
                region_intensity_message = "\n🚨趴下,掩護,穩住🚨\n⚠️震度僅供參考⚠️\n預估震度|抵達時間:"
            else:
                region_intensity_message = "\n🚨趴下,掩護,穩住🚨\n⚠️震度僅供參考⚠️\n震度更新|抵達時間:"

            for (city,
                 region), (intensity,
                           s_arrival_time) in self._region_intensity.items():
                arrival_time = max(s_arrival_time - current_time, 0)
                region_intensity_message += f"\n{city} {region}:{intensity}\n剩餘{arrival_time}秒抵達"

            region_intensity_message += "\n⚠️請以氣象署為準⚠️"

            _headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {self._notify_token}"
            }
            async with aiohttp.ClientSession(headers=_headers) as session:
                await self._post_line_api(
                    session, intensity_msg=region_intensity_message)

    async def _send_eew_img(self, eew: EEW):
        #發送各地震度圖片
        eq = eew.earthquake
        try:
            message = self.get_eew_message(eew)
            await eq._draw_task
            if eq.map._drawn:
                image = eq.map.save().getvalue()
            __headers = {"Authorization": f"Bearer {self._notify_token}"}
            async with aiohttp.ClientSession(headers=__headers) as session:
                await self._post_line_api(session, msg=message, img=image)

        except asyncio.CancelledError:
            self.logger.error(f"Failed get image")
        except Exception as e:
            self.logger.exception(
                f"Failed to send image alert to Line-Notify: {e}")

    async def _post_line_api(self,
                             session: aiohttp.ClientSession,
                             img=None,
                             msg: str = None,
                             intensity_msg: str = None) -> None:
        try:
            # Check if image exists but both message and region_intensity_message do not
            if img and not msg and not intensity_msg:
                raise ValueError("Image provided without a message.")

            form = aiohttp.FormData()
            if msg:
                form.add_field('message', msg)
            elif intensity_msg:
                form.add_field('message', intensity_msg)
            if img:
                form.add_field('imageFile', img)

            async with session.post(url=LINE_NOTIFY_API,
                                    data=form) as response:
                if response.ok:
                    self.response_status = response.status
                    self.logger.info(
                        f"Message sent to Line-Notify successfully")

                else:
                    raise aiohttp.ClientResponseError(response.request_info,
                                                      status=response.status,
                                                      history=response.history,
                                                      message=await
                                                      response.text())
        except ValueError as e:
            self.logger.error(f"ValueError: {e}")
        except Exception as e:
            self.logger.exception(
                f"Failed to send message alert to Line-Notify: {e}")

    async def start(self) -> None:
        """
        The entrypoint for the notification client.
        If this client doesn't need to run in the event loop, just type `pass` because this method is required.

        Note: DO NOT do any blocking calls to run the otification client.
        """
        self.logger.info("LINE Notify is ready")

    async def send_eew(self, eew: EEW):
        """
        If an new EEW is detected, this method will be called.

        Note: This method should not do any blocking calls.

        :param eew: The EEW.
        :type eew: EEW
        """

        # headers = {
        #     "Content-Type": "application/x-www-form-urlencoded",
        #     "Authorization": f"Bearer {self._notify_token}"
        # }
        # message = self.get_eew_message(eew)
        # async with aiohttp.ClientSession(headers=headers) as session:
        #     await self._send_message(session, msg=message)

        await self._send_region_intensity(eew)
        if eew.final:
            asyncio.create_task(self._send_eew_img(eew))

    async def update_eew(self, eew: EEW):
        """
        If an EEW is updated, this method will be called.

        Note: This method should not do any blocking calls.

        :param eew: The updated EEW.
        :type eew: EEW
        """
        # headers = {
        #     "Content-Type": "application/x-www-form-urlencoded",
        #     "Authorization": f"Bearer {self._notify_token}"
        # }
        # message = self.get_eew_message(eew)
        # async with aiohttp.ClientSession(headers=headers) as session:
        #     await self._send_message(session, msg=message)

        await self._send_region_intensity(eew)
        if eew.final:
            asyncio.create_task(self._send_eew_img(eew))
