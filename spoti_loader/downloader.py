from spoti_loader.utils import invoke_url, fix_filename, get_log_db
from spoti_loader.const import *
from pathlib import PurePath, Path
import os
import re
import sqlite3
import math
import ffmpy
import music_tag
import requests
import json
from librespot.metadata import TrackId
from librespot.audio.decoders import VorbisOnlyAudioQuality, AudioQuality


def conv_artist_format(artists) -> str:
    return ", ".join(artists)


def set_audio_tags(
    filename, artists, genres, name, album_name, release_year, disc_number, track_number
) -> None:
    tags = music_tag.load_file(filename)
    tags[ALBUMARTIST] = artists[0]
    tags[ARTIST] = conv_artist_format(artists)
    tags[GENRE] = genres[0]
    tags[TRACKTITLE] = name
    tags[ALBUM] = album_name
    tags[YEAR] = release_year
    tags[DISCNUMBER] = disc_number
    tags[TRACKNUMBER] = track_number
    tags.save()


def set_music_thumbnail(filename, image_url) -> None:
    img = requests.get(image_url).content
    tags = music_tag.load_file(filename)
    tags[ARTWORK] = img
    tags.save()


def create_download_directory(download_path: str) -> None:
    Path(os.path.expanduser(download_path)).mkdir(parents=True, exist_ok=True)


def get_content_stream(session, content_id):
    return session.content_feeder().load(
        content_id, VorbisOnlyAudioQuality(AudioQuality.HIGH), False, None
    )


def get_song_lyrics(token, song_id: str, file_save: str) -> None:
    raw, lyrics = invoke_url(
        token, f"https://spclient.wg.spotify.com/color-lyrics/v2/track/{song_id}"
    )
    if lyrics:
        try:
            formatted_lyrics = lyrics["lyrics"]["lines"]
        except KeyError:
            raise ValueError(f"Failed to fetch lyrics: {song_id}")
        if lyrics["lyrics"]["syncType"] == "UNSYNCED":
            with open(file_save, "w+", encoding="utf-8") as file:
                for line in formatted_lyrics:
                    file.writelines(line["words"] + "\n")
            return
        elif lyrics["lyrics"]["syncType"] == "LINE_SYNCED":
            with open(file_save, "w+", encoding="utf-8") as file:
                for line in formatted_lyrics:
                    timestamp = int(line["startTimeMs"])
                    ts_minutes = str(math.floor(timestamp / 60000)).zfill(2)
                    ts_seconds = str(math.floor((timestamp % 60000) / 1000)).zfill(2)
                    ts_millis = str(math.floor(timestamp % 1000))[:2].zfill(2)
                    file.writelines(
                        f"[{ts_minutes}:{ts_seconds}.{ts_millis}]"
                        + line["words"]
                        + "\n"
                    )
            return
    raise ValueError(f"Failed to fetch lyrics: {song_id}")


def add_to_already_downloaded(song_id, filename) -> None:
    conn = sqlite3.connect(get_log_db())
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO songs (id, filename) VALUES (?, ?)", (song_id, filename)
    )
    conn.commit()
    conn.close()


def remove_song_from_log(song_id):
    conn = sqlite3.connect(get_log_db())
    cursor = conn.cursor()
    cursor.execute("DELETE FROM songs where id = ?", (song_id,))
    conn.commit()
    conn.close()


def song_previously_downloaded(song_id: str) -> bool:
    conn = sqlite3.connect(get_log_db())
    cursor = conn.cursor()
    cursor.execute("SELECT EXISTS (SELECT 1 FROM songs WHERE id = ?);", (song_id,))
    result = cursor.fetchone()

    # Close the database connection
    conn.close()

    # Return True if the song_id exists, False otherwise
    return result[0] == 1


def get_song_info(
    token,
    song_id,
):
    (raw, info) = invoke_url(token, f"{TRACKS_URL}?ids={song_id}&market=from_token")
    with open("output.json", "w") as f:
        # Write the dictionary data into the file
        json.dump(info, f)
    if not TRACKS in info:
        raise ValueError(f"Invalid response from TRACKS_URL:\n{raw}")
    try:
        track = info[TRACKS][0]
        artists = []
        for data in info[TRACKS][0][ARTISTS]:
            artists.append(data[NAME])

        album_name = info[TRACKS][0][ALBUM][NAME]
        name = info[TRACKS][0][NAME]
        release_year = info[TRACKS][0][ALBUM][RELEASE_DATE].split("-")[0]
        disc_number = info[TRACKS][0][DISC_NUMBER]
        track_number = info[TRACKS][0][TRACK_NUMBER]
        scraped_song_id = info[TRACKS][0][ID]
        is_playable = info[TRACKS][0][IS_PLAYABLE]
        duration_ms = info[TRACKS][0][DURATION_MS]

        image = info[TRACKS][0][ALBUM][IMAGES][0]
        for i in info[TRACKS][0][ALBUM][IMAGES]:
            if i[WIDTH] > image[WIDTH]:
                image = i
        image_url = image[URL]

        return (
            artists,
            info[TRACKS][0][ARTISTS],
            album_name,
            name,
            image_url,
            release_year,
            disc_number,
            track_number,
            scraped_song_id,
            is_playable,
            duration_ms,
        )
    except Exception as e:
        raise ValueError(f"Failed to parse TRACKS_URL response: {str(e)}\n{raw}")


def download_track(session, token: str, downloadPath: str, track_id: str) -> None:
    try:
        output_template = "{artist} - {song_name}.{ext}"
        (
            artists,
            raw_artists,
            album_name,
            name,
            image_url,
            release_year,
            disc_number,
            track_number,
            scraped_song_id,
            is_playable,
            duration_ms,
        ) = get_song_info(token, track_id)
        song_name = fix_filename(artists[0]) + " - " + fix_filename(name)
        ext = EXT_MAP.get("aac")

        output_template = output_template.replace("{artist}", fix_filename(artists[0]))
        output_template = output_template.replace("{album}", fix_filename(album_name))
        output_template = output_template.replace("{song_name}", fix_filename(name))
        output_template = output_template.replace(
            "{release_year}", fix_filename(release_year)
        )
        output_template = output_template.replace(
            "{disc_number}", fix_filename(disc_number)
        )
        output_template = output_template.replace(
            "{track_number}", fix_filename(track_number)
        )
        output_template = output_template.replace("{id}", fix_filename(scraped_song_id))
        output_template = output_template.replace("{track_id}", fix_filename(track_id))
        output_template = output_template.replace("{ext}", ext)

        filename = PurePath(downloadPath).joinpath(output_template)
        filedir = PurePath(filename).parent

        filename_temp = filename
        check_name = Path(filename).is_file() and Path(filename).stat().st_size
        check_id = song_previously_downloaded(scraped_song_id)
        if check_id and not check_name:
            remove_song_from_log(scraped_song_id)
        if not check_id and check_name:
            c = (
                len(
                    [
                        file
                        for file in Path(filedir).iterdir()
                        if re.search(f"^{filename}_", str(file))
                    ]
                )
                + 1
            )
            fname = PurePath(PurePath(filename).name).parent
            ext = PurePath(PurePath(filename).name).suffix

            filename = PurePath(filedir).joinpath(f"{fname}_{c}{ext}")
        if check_id and check_name:
            return None
    except Exception as e:
        raise ValueError(f"Failed to query metadata : Track_ID{str(track_id)}")
    else:
        try:
            if not is_playable:
                raise ValueError(f"Song is not playable: {song_name}")
            else:
                if check_id and check_name:
                    raise ValueError(f"Song is already downloaded: {song_name}")
                else:
                    if track_id != scraped_song_id:
                        track_id = scraped_song_id
                    track = TrackId.from_base62(track_id)
                    stream = get_content_stream(session, track)
                    create_download_directory(filedir)
                    total_size = stream.input_stream.size
                    downloaded = 0
                    with open(filename_temp, "wb") as file:
                        b = 0
                        while b < 5:
                            data = stream.input_stream.stream().read(20000)
                            file.write(data)
                            downloaded += len(data)
                            b += 1 if data == b"" else 0
                    try:
                        get_song_lyrics(
                            token, track_id, PurePath(str(filename)[:-3] + "lrc")
                        )
                    except ValueError:
                        pass
                    convert_audio_format(filename_temp)
                    try:
                        set_audio_tags(
                            filename_temp,
                            artists,
                            [""],
                            name,
                            album_name,
                            release_year,
                            disc_number,
                            track_number,
                        )
                        set_music_thumbnail(filename_temp, image_url)
                    except Exception:
                        raise ValueError(
                            "Unable to write metadata, ensure ffmpeg is installed and added to your PATH."
                        )
                    if filename_temp != filename:
                        Path(filename_temp).rename(filename)
                    add_to_already_downloaded(scraped_song_id, PurePath(filename).name)
                    return song_name
        except Exception as e:
            if Path(filename_temp).exists():
                Path(filename_temp).unlink()


def convert_audio_format(filename) -> None:
    temp_filename = f"{PurePath(filename).parent}.tmp"
    Path(filename).replace(temp_filename)
    download_format = "aac"
    file_codec = CODEC_MAP.get(download_format, "copy")
    if file_codec != "copy":
        bitrate = "160k"
    else:
        bitrate = None
    output_params = ["-c:a", file_codec]
    if bitrate:
        output_params += ["-b:a", bitrate]
    ffmpeg_executable = os.path.join(os.getcwd(), "ffmpeg")
    ff_m = ffmpy.FFmpeg(
        executable=ffmpeg_executable,
        global_options=["-y", "-hide_banner", "-loglevel error"],
        inputs={temp_filename: None},
        outputs={filename: output_params},
    )
    ff_m.run()
    if Path(temp_filename).exists():
        Path(temp_filename).unlink()
