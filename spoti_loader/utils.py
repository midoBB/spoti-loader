import requests
import re
import sqlite3
from spoti_loader.const import LIMIT, OFFSET
import os


def fix_filename(name):
    return re.sub(
        r'[/\\:|<>"?*\0-\x1f]|^(AUX|COM[1-9]|CON|LPT[1-9]|NUL|PRN)(?![^.])|^\s|[\s.]$',
        "_",
        str(name),
        flags=re.IGNORECASE,
    )


def invoke_url(token, url):
    headers = get_auth_header(token)
    response = requests.get(url, headers=headers)
    responsetext = response.text
    try:
        responsejson = response.json()
    except Exception as e:
        raise ValueError(f"Failed to parse TRACKS_URL response: {str(e)}")
    return responsetext, responsejson


def get_auth_header(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept-Language": "en",
        "Accept": "application/json",
        "app-platform": "WebPlayer",
    }


def get_auth_header_and_params(token, limit, offset):
    return {
        "Authorization": f"Bearer {token}",
        "Accept-Language": "en",
        "Accept": "application/json",
        "app-platform": "WebPlayer",
    }, {LIMIT: limit, OFFSET: offset}


def invoke_url_with_params(token, url, limit, offset, **kwargs):
    headers, params = get_auth_header_and_params(token, limit=limit, offset=offset)
    params.update(kwargs)
    return requests.get(url, headers=headers, params=params).json()


def get_log_db() -> str:
    xdg_config_home = os.getenv("XDG_CONFIG_HOME")
    if xdg_config_home is None:
        xdg_config_home = os.path.expanduser("~/.config")
    dbfile = os.path.join(xdg_config_home, "spoti-loader", "log.db")
    conn = sqlite3.connect(dbfile)
    c = conn.cursor()
    create_table_query = """CREATE TABLE IF NOT EXISTS songs (
                                id TEXT PRIMARY KEY,
                                filename TEXT
                        );"""
    c.execute(create_table_query)
    conn.commit()
    conn.close()
    return dbfile
