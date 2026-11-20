# Volume in the Web App

The volume of the box can be changed on every page of the Web App, not only on the start page:

* **Slider at the top:** next to the clock, every page (Library, Cards, Import, Settings) shows a small volume
  slider with a mute button. The start page has its large slider instead. Both follow changes from elsewhere
  (a volume card, a GPIO rotary encoder, another phone) right away.
* **Keyboard (PC):** while the Web App is the active window:

  | Key | Does |
  |---|---|
  | `+` (also on the number pad) | Louder by 5 % |
  | `-` | Quieter by 5 % |
  | `M` | Mute / unmute |
  | Volume keys of the keyboard (Fn / media keys: louder, quieter, mute) | The same |

  Holding a key down keeps changing the volume. The keys do nothing while you type into a field (e.g. a link on
  the page *Import*), and `Ctrl` + `+` / `-` still zooms the page. The volume keys of the keyboard also change the
  volume of the computer — the browser can't prevent that; use `+` / `-` to change only the box. Whether the browser
  passes the volume keys on to the page depends on browser and system (Chrome and Edge on Windows and Linux
  usually do, browsers on macOS don't).

The maximum volume (*Settings → Audio*) limits the slider and the keys as well.

## Phone

Browsers on phones (Android, iOS) don't pass the volume buttons of the phone on to web pages; they always change
the volume of the phone. Use the slider at the top instead, or put buttons for louder / quieter on the home screen
of the phone with the [HTTP API](../http-api.md) (`/api/alias/change_volume?args=5` / `args=-5`).
