# YouTube import

The Web App page **Import** (bottom navigation) downloads audio from YouTube — and from the other sites
[yt-dlp](https://github.com/yt-dlp/yt-dlp) supports — directly on the Phoniebox, converts it to MP3 and
puts it into a new folder of the music library. No PC, FTP or Samba copy needed.

1. Paste the link of a video or a playlist and tap *Load*.
2. Edit the folder name, artist and album, the track titles and their order. Unselect tracks you don't
   want. A video with chapters (e.g. an audio book) can be split into one track per chapter.
3. Tap *Import*. Each track is downloaded, converted to MP3 (or cut out of the video) and tagged with
   title, artist, album, track number and the thumbnail as cover. You can leave the page meanwhile, the
   import continues on the box.
4. When it is done: *Assign card* registers a card for the new folder.

Folder names contain only letters, digits and `_` (umlauts are written out: `Max übernachtet` becomes
`Max_uebernachtet`). Track files are named `01 - Title.mp3`, so the folder plays in the edited order.
An existing folder is never overwritten.

> [!NOTE]
> Only download content you are allowed to download. Respect the terms of the site and copyrights.

## Requirements

* **ffmpeg** — installed with the Phoniebox.
* **yt-dlp** and **mutagen** (Python packages) — part of `requirements.txt` for new installations. On an
  existing installation, tap *Install* on the Import page, or run
  `~/RPi-Jukebox-RFID/.venv/bin/pip install "yt-dlp[default]" mutagen`.
* A **JavaScript runtime** for YouTube, `node` by default. yt-dlp needs a recent version (see the hint
  on the Import page; at the time of writing node 22 or newer). The node installed for building the Web
  App may be older. To use a different node only for the import, set `ytimport.js_runtime_path`.
* The plugin in `shared/settings/jukebox.yaml`:

```yaml
modules:
  named:
    # ... after the other modules
    ytimport: ytimport
```

YouTube changes often, and yt-dlp follows quickly: if downloads fail, tap *Update yt-dlp* on the Import
page and restart the jukebox afterwards.

## Configuration

All settings are optional (`shared/settings/jukebox.yaml`, defaults in
`resources/default-settings/jukebox.default.yaml`):

```yaml
ytimport:
  # MP3 quality (ffmpeg VBR -q:a): 0 = best / largest .. 9 = smallest. 2 is about 190 kbit/s
  audio_quality: 2
  # JavaScript runtime yt-dlp uses for YouTube (one of: node, deno, bun, quickjs)
  js_runtime: node
  # Path to the runtime (file or folder) if it is not the one found in PATH. Empty: from PATH
  js_runtime_path: ''
  # Lower CPU priority of downloads and conversion, so that playback keeps running smoothly (0 .. 19)
  nice: 19
  # At most this many entries of a playlist are listed
  max_playlist_entries: 200
  # Working directory for downloads; keep it outside the music library (MPD watches the library)
  tmp_dir: ../../shared/tmp/ytimport
  ffmpeg: ffmpeg
```

## Notes

* Converting is slow on small boards: on a Raspberry Pi 3 an hour of audio takes a few minutes. It runs
  with low priority, so playback is not interrupted.
* One job runs at a time. Tracks that fail (e.g. a private video in a playlist) are skipped and listed
  at the end.
* RPC: `ytimport.ctrl.fetch_info`, `start_import`, `cancel`, `get_status`, `get_versions`,
  `update_ytdlp`. The progress is published on the topic `ytimport.status`.
