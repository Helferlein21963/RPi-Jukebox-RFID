# Rename folders and songs

Folders and songs of the music library can be renamed in the Web App: **Library → Folders**.

* **Folder:** open it and tap the pencil next to its name (beside the play button).
* **Song:** tap the pencil at the end of its line. Besides the file name you can change its **title** —
  the title tag shown in *Albums* and *Songs*. The file extension (e.g. `.mp3`) stays.

Spaces and umlauts are allowed. Characters that don't work in file names (`\ / : * ? " < > |`) are replaced by
spaces; the dialog shows the resulting name.

**Cards are adapted:** cards playing the folder (or a song or subfolder in it) play it under the new name. The
dialog shows how many cards are affected. The remembered position for continuing a folder is kept as well.

Good to know:

* What is playing or paused can't be renamed — stop the playback first.
* Changing the title needs the Python package `mutagen`. It is installed together with yt-dlp on the page
  **Import** (see [YouTube and podcast import](./youtube-import.md)); without it, the title field is disabled.
* *Albums* and *Songs* show the change after MPD has updated its database (a few seconds), the folder view
  right away.
* The library folder itself can't be renamed.

For developers: the RPCs are `player.ctrl.get_rename_info(path)` and `player.ctrl.rename(path, new_name, title)`;
cards are adapted by `cards.rewrite_paths`.
