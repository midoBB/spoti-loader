import json
import os
import logging
import sys
import sqlite3
import requests
from librespot.audio.decoders import AudioQuality
from librespot.core import Session
from spoti_loader.const import (
    USER_READ_EMAIL,
    PLAYLIST_READ_PRIVATE,
    USER_LIBRARY_READ,
    USER_FOLLOW_READ,
    SAVED_TRACKS_URL,
    ITEMS,
    LIMIT,
    OFFSET,
    TRACK,
    NAME,
    ID,
)
from spoti_loader.utils import invoke_url_with_params
from spoti_loader.downloader import download_track


logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def fatalf(msg, *args):
    logging.error(msg, *args)
    sys.exit(1)


def get_cred_file():
    xdg_config_home = os.getenv("XDG_CONFIG_HOME")
    if xdg_config_home is None:
        xdg_config_home = os.path.expanduser("~/.config")
    return os.path.join(xdg_config_home, "spoti-loader", "cred.json")


def load_json_file(filepath: str) -> tuple[str, str, str]:
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        username = data.get("username")
        password = data.get("password")
        output = data.get("output")
        discord = data.get("discord")
        if not username or not password or not output:
            raise ValueError("Username/password/output is missing or empty.")
        return username, password, output, discord
    except FileNotFoundError:
        fatalf(f"File {filepath} not found.")
    except json.JSONDecodeError:
        fatalf(f"Invalid JSON in file {filepath}.")


username, password, output, discord = load_json_file(get_cred_file())
output = os.path.expanduser(output)
quality = AudioQuality.HIGH
conf = Session.Configuration.Builder().set_store_credentials(False).build()
session = Session.Builder(conf).user_pass(username, password).create()
token = (
    session.tokens()
    .get_token(
        USER_READ_EMAIL, PLAYLIST_READ_PRIVATE, USER_LIBRARY_READ, USER_FOLLOW_READ
    )
    .access_token
)


def get_saved_tracks() -> list:
    songs = []
    offset = 0
    limit = 50
    while True:
        resp = invoke_url_with_params(
            token, SAVED_TRACKS_URL, limit=limit, offset=offset
        )
        offset += limit
        songs.extend(resp[ITEMS])
        if len(resp[ITEMS]) < limit:
            break
    return songs


def send_to_discord(webhook_url, title, content, color=2605644):
    headers = {"Content-Type": "application/json"}

    data = {
        "content": None,
        "embeds": [{"title": title, "description": content, "color": color}],
    }
    requests.post(webhook_url, headers=headers, data=json.dumps(data))


def send_discord_notifications(songs, errors):
    songs = [song for song in songs if song is not None]
    errors = [error for error in errors if error is not None]
    for i in range(0, len(songs), 20):
        batch_songs = songs[i : i + 20]
        if len(batch_songs) > 0:
            succes_title = "**Downloaded songs : **"
            count_msg = f"{len(batch_songs)} tracks successfully downloaded"
            batch_songs.insert(0, count_msg)
            batch_songs.insert(0, succes_title)
            batch_songs.insert(0, "@everyone")
            success_message = "\n".join(batch_songs)
            send_to_discord(discord, "SpotiLoader Downloads", success_message)
    for i in range(0, len(errors), 20):
        batch_errors = errors[i : i + 20]
        if len(batch_errors) > 0:
            errormsg = "**Errors when downloading songs : **"
            batch_errors.insert(0, "@everyone")
            batch_errors.insert(0, errormsg)
            error_message = "\n".join(batch_errors)
            send_to_discord(discord, "SpotiLoader Errors", error_message, 16753920)


def download_songs() -> tuple[list, list]:
    errors = []
    downloaded = []
    for song in get_saved_tracks():
        if song[TRACK][NAME] and song[TRACK][ID]:
            try:
                songtitle = download_track(session, token, output, song[TRACK][ID])
                if songtitle is not None:
                    logger.info(f"Downloaded {song[TRACK][NAME]}")
                downloaded.append(songtitle)
            except Exception as e:
                errors.append(e)
                logger.error(f"Error when downloading {song[TRACK][NAME]}")
                logger.error(e)
    return downloaded, errors


downloaded, errors = download_songs()

if discord is not None:
    send_discord_notifications(downloaded, errors)
