# YouTube and podcast import

The Web App page **Import** (bottom navigation) downloads audio from YouTube — and from the other sites
[yt-dlp](https://github.com/yt-dlp/yt-dlp) supports — as well as podcast episodes directly on the Phoniebox,
converts it to MP3 and puts it into a new folder of the music library. No PC, FTP or Samba copy needed.

1. Paste the link of a video, a playlist, a podcast feed or an audio file and tap *Load*.
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

## Podcasts and audio files

Everything a podcast app can play can be imported:

* **A podcast feed** (RSS): all episodes are listed with date and duration, newest first as in the feed.
  None is selected — tick the episodes you want (*Reverse* turns the order around). The feed link is
  shown by most podcast apps ("share" / "copy feed URL") or on the website of the podcast ("RSS",
  "Podcast abonnieren"). Example: `https://kinder.wdr.de/radio/diemaus/audio/diemaus-60/diemaus-60-106.podcast`
* **A single episode**: the direct link to its audio file (e.g. `https://…/episode_MP3-128.mp3`). Title,
  album and artist are taken from the tags of the file.

MP3 episodes are copied, not converted again: this is fast (seconds instead of minutes on a Raspberry Pi)
and keeps the quality. The image of the episode, or else the cover in the file, becomes the cover.

There is no subscription yet: new episodes are imported by hand. After an import, *More tracks into this
folder* goes back to the list of the same link with the folder preselected.

## Existing folders

The field *Folder* lists the folders of the music library (type to search). Pick one to add the tracks to
it, or type a new name: *New folder* creates it directly in the music library. When adding to a folder,
artist and album are taken from its files.

The Phoniebox plays a folder in alphabetical order of the file names, so new tracks are named to fit:

* If every file starts with a number (`01 - …`), the new tracks get the next numbers and play at the end.
* Otherwise they get no number and sort in alphabetically. The files already in the folder stay as they are.

To decide the order yourself, switch on *Set the order myself*: all tracks of the folder are listed with
the new ones and can be moved. On import, **all files of the folder are renamed** to `01 - …`, `02 - …` in
that order. The remembered position and cards follow the new names. This works also while the folder is
being played: the current track plays on, then the queue is loaded again in the new order (with the new
tracks) and continues at the same track and position. A paused folder is stopped at its position instead;
play continues there.

## Requirements

* **ffmpeg** — installed with the Phoniebox.
* **yt-dlp** and **mutagen** (Python packages) — part of `requirements.txt` for new installations. On an
  existing installation, tap *Install* on the Import page, or run
  `~/RPi-Jukebox-RFID/.venv/bin/pip install "yt-dlp[default]" mutagen`.
* A **JavaScript runtime** for YouTube, `node` by default. yt-dlp needs a recent version (see the hint
  on the Import page; at the time of writing node 22 or newer). The installer sets up node 22 together
  with the Web App. Older installations may have node 20: update node (see
  [Install node manually](../../developers/webapp.md#install-node-manually)), or set
  `ytimport.js_runtime_path` to use a different node only for the import.
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
