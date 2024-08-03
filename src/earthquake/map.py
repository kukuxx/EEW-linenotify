import io
from typing import TYPE_CHECKING

import requests
import folium
from folium import GeoJson

if TYPE_CHECKING:
    from earthquake.eew import EarthquakeData

from ..settings import Settings
from .location import COUNTRY_DATA, TAIWAN_CENTER, TOWN_RANGE

url = Settings.get("uploadurl")
key = Settings.get("uploadkey")
INTENSITY_COLOR: dict[int, str] = {
    0: None,
    1: "#5Ed3CF",
    2: "#2D87FF",
    3: "#8FC923",
    4: "#F5F302",
    5: "#CCAA47",
    6: "#AC7E4F",
    7: "#FF9C26",
    8: "#D95656",
    9: "#C32EEE",
}


class Map:
    """
    Represents the map for earthquake.
    """

    __slots__ = ("_eq", "_image", "_drawn")

    def __init__(self, earthquake: "EarthquakeData"):
        """
        Initialize the map.

        :param earthquake: The earthquake data
        """
        self._eq = earthquake
        self._image = None
        self._drawn: bool = False
        "Whether the map has been drawn"

    @property
    def image(self) -> io.StringIO:
        """
        The map image of the earthquake.
        """
        return self._image

    def draw(self):
        if self._eq._expected_intensity is None:
            raise RuntimeError("Intensity have not been calculated yet.")

        try:
            CRS = "EPSG:4326"
            # 地圖初始化 設定中心為台灣中心
            m = folium.Map(
                location=[TAIWAN_CENTER.lat, TAIWAN_CENTER.lon],
                zoom_start=7,
                tiles=None,
                # attr="⚠️圖片僅供參考,實際請以氣象署公布為準⚠️",
                max_bounds=True,  # 限制地圖在初始範圍內
                zoomControl=False,  # 禁用缩放控件
                # min_zoom=7,                 # 設定最小縮放級別
                # max_zoom=9                  # 設定最大縮放級別
            )

            # 設定地圖的顯示範圍
            bounds = [[20.5, 118.5], [25.75, 123.5]]
            m.fit_bounds(bounds)

            # 停用地圖上的所有縮放和拖曳功能
            m.options["scrollWheelZoom"] = False
            m.options["doubleClickZoom"] = False
            m.options["touchZoom"] = False
            m.options["dragging"] = False

            autozoom_html = """
            <style>
                .marker-icon {
                    font-size: 48px;
                    color: red;
        
                    @media screen and (width > 992px) {
                        font-size: 24px;
                        color: red;
                    }
                }
        
                .float_image {
                    position: absolute;
                    z-index: 999999;
                    bottom: 25%;
                    left: 10%;
                    width: 10%;
        
                    @media screen and (width > 992px) {
                        position: absolute;
                        z-index: 999999;
                        bottom: 10%;
                        left: 25%;
                        width: 5%;
                    }
                }
            </style>
             <img class="float_image" alt="float_image"
                src="https://raw.githubusercontent.com/kukuxx/EEW-linenotify/main/asset/map_legend.png">
            </img>
            """

            m.get_root().html.add_child(folium.Element(autozoom_html))

            for code, region_gdf in TOWN_RANGE.items():
                TOWN_RANGE[code] = region_gdf.set_crs(CRS)

            # 繪製區域及其強度
            for code, region_gdf in TOWN_RANGE.items():
                if code in self._eq._expected_intensity:
                    intensity = self._eq._expected_intensity[
                        code].intensity.value
                    if intensity > 0:
                        # 繪製區域，並根據強度設定顏色
                        folium.GeoJson(
                            region_gdf,
                            style_function=lambda feature, intensity=intensity:
                            {
                                "fillColor": INTENSITY_COLOR[intensity],
                                "color": "black",
                                "weight": 0.25,
                                "fillOpacity": 1
                            }).add_to(m)

            # 繪製國家邊界
            folium.GeoJson(COUNTRY_DATA.set_crs(CRS),
                           style_function=lambda x: {
                               "color": "black",
                               "weight": 0.65,
                               "fillOpacity": 0
                           }).add_to(m)

            # 在震央位置新增標記 使用 HTML 和 CSS 建立帶有「X」符號的標記
            folium.Marker(
                location=[self._eq.lat, self._eq.lon],
                popup="震央",
                icon=folium.DivIcon(
                    html='<div class="marker-icon";>&#10006;&#xfe0e;</div>')
            ).add_to(m)

            _map = io.StringIO()
            html = m.get_root().render()
            _map.write(html)
            _map.seek(0)
            self._image = _map

            self._drawn = True

        except Exception as e:
            print(f"Error: {e}")

    def upload(self, id):
        filename = id
        fileobj = self._image.getvalue()

        data = {
            "scriptKey": f"{key}",
            "fileName": f"{filename}.html",
            "fileContent": fileobj,
        }

        response = requests.post(url, data=data)

        if not response.ok:
            print(f"Error: {response.text}")
