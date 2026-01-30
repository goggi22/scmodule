# meta developer: @avalleywithoutwind
# requires: requests pillow

import asyncio
import contextlib
import functools
import io
import logging
import re
import time
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
        W, H = 1500, 600
        padding = 60
        cover_size = 480
        
        font_bytes = requests.get(self.font_url).content
        title_font = self._get_font(55, font_bytes)
        artist_font = self._get_font(45, font_bytes)
        time_font = self._get_font(25, font_bytes)

        img = self._prepare_background(W, H)
        draw = ImageDraw.Draw(img)
        
        cover = self._prepare_cover(cover_size, 30)
        img.paste(cover, (padding, (H - cover_size) // 2), cover)

        text_x = padding + cover_size + 60
        text_y_start = 100
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

        cur_time = f"{(self.progress//1000//60):02}:{(self.progress//1000%60):02}"
        dur_time = f"{(self.duration//1000//60):02}:{(self.duration//1000%60):02}"
        
        cur_w = time_font.getlength(cur_time)
        dur_w = time_font.getlength(dur_time)
        
        bar_y = 480
        bar_h = 8
        gap = 25
        
        draw.text((text_x, bar_y - 12), cur_time, font=time_font, fill="white")
        
        bar_start_x = text_x + cur_w + gap
        bar_end_x = text_x + text_width_limit - dur_w - gap
        bar_w = bar_end_x - bar_start_x
        
        prog_pct = self.progress / self.duration if self.duration > 0 else 0
        self._draw_progress_bar(draw, bar_start_x, bar_y, bar_w, bar_h, prog_pct)
        
        draw.text((bar_end_x + gap, bar_y - 12), dur_time, font=time_font, fill="white")

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
            " </b><code>.scauth</code><b> before performing this action.</b>"
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
            " </b><code>.scauth</code><b> перед выполнением этого действия.</b>"
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
        self._client_id = None
        self._client_secret = None
        self._redirect_uri = "https://goggi22.github.io/scmodule/"
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "client_id",
                "",
                "SoundCloud Client ID",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "client_secret", 
                "",
                "SoundCloud Client Secret",
                validator=loader.validators.Hidden(),
            ),
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
        )

    async def client_ready(self, client, db):
        self._client_id = self.config["client_id"]
        self._client_secret = self.config["client_secret"]
        
        try:
            if self.get("access_token"):
                await self._refresh_token_if_needed()
        except Exception:
            self.set("access_token", None)

    def tokenized(func) -> FunctionType:
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            if not args[0].get("access_token", False):
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

    async def _refresh_token_if_needed(self):
        """Refresh token if needed"""
        token_data = self.get("access_token")
        if not token_data:
            return
            
        expires_at = token_data.get("expires_at", 0)
        if time.time() >= expires_at - 300:  # Refresh 5 minutes before expiry
            await self._refresh_access_token()

    async def _refresh_access_token(self):
        """Refresh access token using refresh token"""
        token_data = self.get("access_token")
        if not token_data or not token_data.get("refresh_token"):
            return
            
        data = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": token_data["refresh_token"]
        }
        
        response = requests.post("https://secure.soundcloud.com/oauth/token", data=data)
        if response.status_code == 200:
            new_token = response.json()
            new_token["expires_at"] = time.time() + new_token.get("expires_in", 3600)
            self.set("access_token", new_token)

    async def _get_current_track(self):
        """Get current playing track from SoundCloud"""
        token_data = self.get("access_token")
        if not token_data:
            return None
            
        headers = {
            "Authorization": f"OAuth {token_data['access_token']}",
            "Accept": "application/json"
        }
        
        # First, let's check who we are
        me_response = requests.get("https://api.soundcloud.com/me", headers=headers)
        if me_response.status_code != 200:
            return None
            
        user_info = me_response.json()
        logger.info(f"Authorized as: {user_info.get('username', 'Unknown')}")
        
        # Try different endpoints to find user's music
        endpoints = [
            "https://api.soundcloud.com/me/activities",
            "https://api.soundcloud.com/me/favorites",
            "https://api.soundcloud.com/me/tracks"
        ]
        
        for endpoint in endpoints:
            response = requests.get(endpoint, headers=headers)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Endpoint {endpoint}: {len(data.get('collection', data if isinstance(data, list) else []))} items")
                
                if endpoint == "https://api.soundcloud.com/me/activities":
                    activities = data.get("collection", [])
                    for activity in activities:
                        if activity.get("type") == "track" and activity.get("origin"):
                            track = activity["origin"]
                            return self._format_track(track)
                            
                elif endpoint == "https://api.soundcloud.com/me/favorites":
                    favorites = data if isinstance(data, list) else data.get("collection", [])
                    if favorites:
                        return self._format_track(favorites[0])
                        
                elif endpoint == "https://api.soundcloud.com/me/tracks":
                    tracks = data if isinstance(data, list) else data.get("collection", [])
                    if tracks:
                        return self._format_track(tracks[0])
        
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
    @loader.command(
        ru_doc="- Получить ссылку для авторизации"
    )
    async def scauthcmd(self, message: Message):
        """- Get authorization link"""
        if not self._client_id or not self._client_secret:
            await utils.answer(message, "<b>Please configure client_id and client_secret in module config</b>")
            return
            
        if self.get("access_token", False):
            await utils.answer(message, self.strings("already_authed"))
            return
            
        auth_url = (
            f"https://secure.soundcloud.com/authorize"
            f"?client_id={self._client_id}"
            f"&redirect_uri={self._redirect_uri}"
            f"&response_type=code"
            f"&scope=non-expiring"
        )
        
        await utils.answer(message, self.strings("auth").format(auth_url))

    @error_handler
    @loader.command(
        ru_doc="- Вставить код авторизации"
    )
    async def sccodecmd(self, message: Message):
        """- Paste authorization code"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "<b>Please provide the callback URL</b>")
            return
            
        # Extract code from URL
        if "code=" in args:
            code = args.split("code=")[1].split("&")[0]
        else:
            await utils.answer(message, "<b>Invalid callback URL</b>")
            return
            
        data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_uri,
            "code": code
        }
        
        response = requests.post("https://secure.soundcloud.com/oauth/token", data=data)
        if response.status_code == 200:
            token_data = response.json()
            token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
            self.set("access_token", token_data)
            await utils.answer(message, self.strings("authed"))
        else:
            await utils.answer(message, f"<b>Authorization failed:</b> {response.text}")

    @error_handler
    @loader.command(
        ru_doc="- Выйти из аккаунта"
    )
    async def scunauthcmd(self, message: Message):
        """- Log out of account"""
        self.set("access_token", None)
        await utils.answer(message, self.strings("deauth"))

    @error_handler
    @tokenized
    @loader.command(
        ru_doc="- 🎧 Показать карточку играющего трека"
    )
    async def scnowcmd(self, message: Message):
        """- 🎧 View current track card."""
        await self._refresh_token_if_needed()
        
        track = await self._get_current_track()
        if not track:
            await utils.answer(message, self.strings("no_music"))
            return

        # Format time
        duration = f"{track['duration']//1000//60}:{track['duration']//1000%60:02}"
        progress = "0:00"  # SoundCloud API doesn't provide current position

        text = self.config["custom_text"].format(
            track=utils.escape_html(track["title"]),
            artist=utils.escape_html(track["user"]),
            duration=duration,
            progress=progress,
            soundcloud_url=track["permalink_url"],
        )

        if self.config["show_banner"] and track.get("artwork_url"):
            tmp_msg = await utils.answer(message, text + self.strings("uploading_banner"))
            
            try:
                # Get artwork
                artwork_response = requests.get(track["artwork_url"])
                if artwork_response.status_code == 200:
                    banners = SoundCloudBanners(
                        title=track["title"],
                        artist=track["user"],
                        duration=track["duration"],
                        progress=0,  # No progress info available
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

    async def watcher(self, message: Message):
        """Watcher to refresh tokens"""
        if self.get("access_token"):
            await self._refresh_token_if_needed()