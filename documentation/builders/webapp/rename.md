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

## Order of a folder

The box plays a folder in the alphabetical order of its file names. To change it, open the folder in
**Library → Folders** and tap the arrows button next to the pencil (shown with two songs or more):

* **Sort** puts the songs in order at once: by name (A–Z, Z–A, ignoring a leading number), by the
  **track number** tag, or by the date of the file (**newest** / **oldest** first, e.g. podcast episodes in the
  order they were added).
* Then move single songs with the arrows. Every line shows the name the file will get.
* **Save** renames the files to `01 - Title.mp3`, `02 - …` in this order and sets their track number tag
  (if `mutagen` is installed). The title and the date of the files stay.

Cards playing one of the songs and the remembered position are adapted, but the folder starts again with its first
song. Like renaming, this is not possible while the folder is playing or paused. Folders whose content is set by a
playlist (`.m3u`) or a `livestream.txt` / `podcast.txt` can't be reordered.

## Sorting and view

The button next to the search sorts the list of the library: by name (A–Z, Z–A), by artist (albums and songs) or
**recently added** first. In a folder, the subfolders come first, then the songs. For the songs, A–Z is the order
they are played in; Z–A and *recently added* only change the list, not the play order (use *Order of a folder* for
that). The library opens with the view (*Folders*, *Albums*, *Songs*) and the sorting chosen last; both are kept in
the browser.

## For developers

The RPCs are `player.ctrl.get_rename_info(path)`, `player.ctrl.rename(path, new_name, title)`,
`player.ctrl.get_order_info(folder)` and `player.ctrl.reorder(folder, files)`; cards are adapted by
`cards.rewrite_paths` / `cards.rewrite_paths_many`. File helpers are in `jukebox.library_edit`.
