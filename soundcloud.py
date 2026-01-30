# meta developer: @ke_mods & forked @avalleywithoutwind
# requires: requests pillow

import contextlib
import functools
import io
import logging
import traceback
from types import FunctionType

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from telethon.tl.types import Message

from .. import loader, utils

logger = logging.getLogger(__name__)

class SoundCloudBanners:
    def __init__(
        self,
        title: str,
        artist: str,
        duration: int,
        progress: int,
        track_cover: bytes,
        font_url: str
    ):
        self.title = title
        self.artist = artist
        self.duration = duration
        self.progress = progress
        self.track_cover = track_cover
        self.font_url = font_url

    def _get_font(self, size, font_bytes):
        return ImageFont.truetype(io.BytesIO(font_bytes), size)

    def _prepare_cover(self, size, radius):
        cover = Image.open(io.BytesIO(self.track_cover)).convert("RGBA")
        cover = cover.resize((size, size), Image.Resampling.LANCZOS)
        
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
        
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(cover, (0, 0), mask=mask)
        return output

    def _prepare_background(self, w, h):
        bg = Image.open(io.BytesIO(self.track_cover)).convert("RGBA")
        bg = bg.resize((w, h), Image.Resampling.BICUBIC)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=40))
        bg = ImageEnhance.Brightness(bg).enhance(0.4)
        return bg

    def _draw_progress_bar(self, draw, x, y, w, h, progress_pct, color="white", bg_color="#5e5e5e"):
        draw.rounded_rectangle((x, y, x + w, y + h), radius=h/2, fill=bg_color)
        
        fill_w = int(w * progress_pct)
        if fill_w > 0:
            draw.rounded_rectangle((x, y, x + fill_w, y + h), radius=h/2, fill=color)

        dot_radius = h * 1.2
        dot_x = x + fill_w
        dot_y = y + (h / 2)
        
        draw.ellipse(
            (dot_x - dot_radius, dot_y - dot_radius, dot_x + dot_radius, dot_y + dot_radius),
            fill=color
        )

    def horizontal(self):
        W, H = 1500, 400
        padding = 60
        cover_size = 280
        
        font_bytes = requests.get(self.font_url).content
        title_font = self._get_font(55, font_bytes)
        artist_font = self._get_font(45, font_bytes)

        img = self._prepare_background(W, H)
        draw = ImageDraw.Draw(img)
        
        cover = self._prepare_cover(cover_size, 30)
        img.paste(cover, (padding, (H - cover_size) // 2), cover)

        text_x = padding + cover_size + 60
        text_y_start = (H - 120) // 2
        text_width_limit = W - text_x - padding

        display_title = self.title
        while title_font.getlength(display_title) > text_width_limit and len(display_title) > 0:
            display_title = display_title[:-1]
        if len(display_title) < len(self.title): display_title += "…"

        display_artist = self.artist
        while artist_font.getlength(display_artist) > text_width_limit and len(display_artist) > 0:
            display_artist = display_artist[:-1]
        if len(display_artist) < len(self.artist): display_artist += "…"

        draw.text((text_x, text_y_start), display_title, font=title_font, fill="white")
        draw.text((text_x, text_y_start + 70), display_artist, font=artist_font, fill="#B3B3B3")

        by = io.BytesIO()
        img.save(by, format="PNG")
        by.seek(0)
        by.name = "banner.png"
        return by

@loader.tds
class SoundCloudMod(loader.Module):
    """Card with the currently playing track on SoundCloud."""

    strings = {
        "name": "SoundCloudMod",
        "need_auth": (
            "<emoji document_id=5778527486270770928>❌</emoji> <b>Please execute"
            " </b><code>.scauth</code><b> or set oauth_token in module config</b>"
        ),
        "already_authed": (
            "<emoji document_id=5778527486270770928>❌</emoji> <b>Already authorized</b>"
        ),
        "authed": (
            "<emoji document_id=5776375003280838798>✅</emoji> <b>Authentication"
            " successful</b>"
        ),
        "deauth": (
            "<emoji document_id=5877341274863832725>🚪</emoji> <b>Successfully logged out"
            " of account</b>"
        ),
        "auth": (
            '<emoji document_id=5778168620278354602>🔗</emoji> <a href="{}">Follow this'
            " link</a>, allow access, then enter <code>.sccode https://...</code> with"
            " the link you received."
        ),
        "no_music": (
            "<emoji document_id=5778527486270770928>❌</emoji> <b>No music is playing!</b>"
        ),
        "err": (
            "<emoji document_id=5778527486270770928>❌</emoji> <b>An error occurred."
            "</b>\n<code>{}</code>"
        ),
        "uploading_banner": "\n\n<emoji document_id=5841359499146825803>🕔</emoji> <i>Uploading banner...</i>",
    }

    strings_ru = {
        "_cls_doc": "Карточка с играющим треком в SoundCloud.",
        "need_auth": (
            "<emoji document_id=5778527486270770928>❌</emoji> <b>Выполни"
            " </b><code>.scauth</code><b> или установи oauth_token в конфиге модуля</b>"
        ),
        "already_authed": (
            "<emoji document_id=5778527486270770928>❌</emoji> <b>Уже авторизован</b>"
        ),
        "authed": (
            "<emoji document_id=5776375003280838798>✅</emoji> <b>Успешная аутентификация</b>"
        ),
        "deauth": (
            "<emoji document_id=5877341274863832725>🚪</emoji> <b>Успешный выход из аккаунта</b>"
        ),
        "auth": (
            '<emoji document_id=5778168620278354602>🔗</emoji> <a href="{}">Пройдите по этой ссылке</a>, разрешите вход, затем введите <code>.sccode https://...</code> с ссылкой которую вы получили.'
        ),
        "no_music": (
            "<emoji document_id=5778527486270770928>❌</emoji> <b>Музыка не играет!</b>"
        ),
        "err": (
            "<emoji document_id=5778527486270770928>❌</emoji> <b>Произошла ошибка."
            "</b>\n<code>{}</code>"
        ),
        "uploading_banner": "\n\n<emoji document_id=5841359499146825803>🕔</emoji> <i>Загрузка баннера...</i>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "show_banner",
                True,
                "Show banner with track info",
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "custom_text",
                (
                    "<emoji document_id=6007938409857815902>🎧</emoji> <b>Now playing:</b> {track} — {artist}\n"
                    "<emoji document_id=5877465816030515018>🔗</emoji> <b><a href='{soundcloud_url}'>SoundCloud</a></b>"
                ),
                "Custom text, supports {track}, {artist}, {soundcloud_url}, {progress}, {duration} placeholders",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "font",
                "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf",
                "Custom font. Specify URL to .ttf file",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "oauth_token",
                "",
                "SoundCloud OAuth token from browser cookies",
                validator=loader.validators.String(),
            ),
        )

    def tokenized(func) -> FunctionType:
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            oauth_token = args[0].config["oauth_token"]
            if not oauth_token:
                await utils.answer(args[1], args[0].strings("need_auth"))
                return
            return await func(*args, **kwargs)
        return wrapped

    def error_handler(func) -> FunctionType:
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception:
                logger.exception(traceback.format_exc())
                with contextlib.suppress(Exception):
                    await utils.answer(
                        args[1],
                        args[0].strings("err").format(traceback.format_exc()),
                    )
        return wrapped



    async def _get_current_track(self):
        """Get current playing track from SoundCloud"""
        oauth_token = self.config["oauth_token"]
        headers = {
            "Authorization": f"OAuth {oauth_token}",
            "Accept": "application/json"
        }
        
        # Try multiple endpoints to find tracks
        endpoints = [
            "https://api-v2.soundcloud.com/me/play-history/tracks",
            "https://api-v2.soundcloud.com/me/library/history",
            "https://api.soundcloud.com/me/favorites"
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    tracks = data.get("collection", [])
                    if tracks:
                        track_data = tracks[0].get("track") if tracks[0].get("track") else tracks[0]
                        return self._format_track(track_data)
            except:
                continue
        
        return None
    
    def _format_track(self, track):
        return {
            "id": track["id"],
            "title": track["title"],
            "user": track["user"]["username"],
            "duration": track.get("duration", 0),
            "permalink_url": track["permalink_url"],
            "artwork_url": track.get("artwork_url", track["user"].get("avatar_url"))
        }



    @error_handler
    @tokenized
    @loader.command(
        ru_doc="- 🎧 Показать карточку играющего трека"
    )
    async def scnowcmd(self, message: Message):
        """- 🎧 View current track card."""
        track = await self._get_current_track()
        if not track:
            await utils.answer(message, self.strings("no_music"))
            return

        duration = f"{track['duration']//1000//60}:{track['duration']//1000%60:02}"

        text = self.config["custom_text"].format(
            track=utils.escape_html(track["title"]),
            artist=utils.escape_html(track["user"]),
            duration=duration,
            progress="",
            soundcloud_url=track["permalink_url"],
        )

        if self.config["show_banner"] and track.get("artwork_url"):
            tmp_msg = await utils.answer(message, text + self.strings("uploading_banner"))
            
            try:
                artwork_response = requests.get(track["artwork_url"])
                if artwork_response.status_code == 200:
                    banners = SoundCloudBanners(
                        title=track["title"],
                        artist=track["user"],
                        duration=track["duration"],
                        progress=0,
                        track_cover=artwork_response.content,
                        font_url=self.config["font"],
                    )
                    file = banners.horizontal()
                    await utils.answer(tmp_msg, text, file=file)
                else:
                    await utils.answer(tmp_msg, text)
            except Exception:
                await utils.answer(tmp_msg, text)
        else:
            await utils.answer(message, text)