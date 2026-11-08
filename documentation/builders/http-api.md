# HTTP API and widgets on the phone

The Phoniebox can be controlled with simple web addresses (URLs), e.g. `http://phoniebox.local/api/alias/toggle`
for play / pause. With an app like [HTTP Shortcuts](https://http-shortcuts.rmy.ch/) (Android, free and open
source) these URLs become buttons on the home screen of your phone — a remote control without opening the Web App.

The Web App and the RPC interface use ZeroMQ, which such apps cannot talk to. The plugin `http_api`
translates the URLs into [RPC commands](./rpc-commands.md).

## URLs

Replace `phoniebox.local` with the name or IP address of your Phoniebox.

| URL | Does |
|---|---|
| `/api/alias/toggle` | Play / pause |
| `/api/alias/next_song` | Next song |
| `/api/alias/prev_song` | Previous song |
| `/api/alias/next_folder` | Next folder (see below) |
| `/api/alias/prev_folder` | Previous folder |
| `/api/alias/change_volume?args=5` | Louder (by 5 %) |
| `/api/alias/change_volume?args=-5` | Quieter |
| `/api/alias/play_card?args=Hoerspiele/Max` | Play a folder like a card swipe (a second "swipe" pauses, see second swipe action) |
| `/api/alias/play_folder?args=Hoerspiele/Max` | Play a folder from the beginning |
| `/api/alias/<alias>` | Every alias of the [RPC commands](./rpc-commands.md), e.g. `shutdown`, `timer_shutdown` |
| `/api/rpc/<package>/<plugin>/<method>` | Every RPC call, e.g. `/api/rpc/player/ctrl/play_song?args=3` |
| `/api/status` | Player state, current song and volume |

The URLs work on port 80 via nginx (`http://phoniebox.local/api/...`) and directly on port 5559
(`http://phoniebox.local:5559/api/...`). Installations from before this feature have no nginx entry for
`/api/` yet: use port 5559, or add the `location /api/` block from `resources/default-settings/nginx.default`
to `/etc/nginx/sites-available/default` and run `sudo systemctl restart nginx`.

**Arguments**: `args` is a JSON list (`args=[5]`) or a single value (`args=5`, `args=Hoerspiele/Max`), `kwargs` a
JSON object (`kwargs={"folder":"Hoerspiele/Max","recursive":true}`). A folder name that consists only of digits
must be quoted: `args=["2024"]`. Encode special characters in a URL (space: `%20`). Instead of the
query you can send a JSON body with POST: `{"args": [5]}` / `{"kwargs": {...}}`.

**Next / previous folder** switches to the neighbor of the current folder in the same parent folder, in
alphabetical order (as in the library); after the last folder comes the first again. Example: `Hoerspiele/Folge_02`
→ `Hoerspiele/Folge_03`. Folders without songs are skipped, sub-folders are played as well, and the folder
continues where it was left if *continue where left off* is enabled for cards (Settings → RFID Cards). The current
folder is the one played last, or else the folder of the current song. The aliases `next_folder` / `prev_folder`
also work for cards and GPIO buttons.

GET and POST both work. The answer is JSON: `{"result": ...}`, or `{"error": "..."}` with status 404 (unknown
URL / alias / RPC call), 400 (wrong arguments) or 500 (error while running the command).

Test it in the browser or with curl:

```bash
curl http://phoniebox.local/api/status
curl http://phoniebox.local/api/alias/toggle
```

## Widget on an Android phone

1. Install **HTTP Shortcuts** (Google Play or F-Droid).
2. Create a new shortcut ("regular shortcut"): name e.g. *Play/Pause*, method GET, URL
   `http://phoniebox.local/api/alias/toggle`. Pick an icon.
3. In the response settings, choose to show nothing (or only errors), so tapping doesn't open a window.
4. Repeat for the other buttons (next, louder, quieter, a favorite folder, ...).
5. Long-press the home screen → *Widgets* → *HTTP Shortcuts* and drag a widget onto the home screen; choose the
   shortcut. Some launchers can also put the shortcuts directly on the home screen.

HTTP Shortcuts has one button per widget. For a remote control, put the widgets side by side, e.g.:

| | | |
|---|---|---|
| ⏪ `prev_folder` | ⏯ `toggle` | ⏩ `next_folder` |
| ⏮ `prev_song` | 🔉 `change_volume?args=-5` / 🔊 `args=5` | ⏭ `next_song` |

Hide the labels of the widgets (option of the widget) and choose matching icons, then the buttons look like
one control.

The phone must be in the same network as the Phoniebox. If `phoniebox.local` doesn't resolve on your phone,
use the IP address of the box.

The Web App can also be placed on the home screen as an icon: open it in Chrome → menu → *Add to Home screen*.

## Configuration

`shared/settings/jukebox.yaml` (edit only while the service is stopped, see [Configuration](./configuration.md)):

```yaml
modules:
  named:
    # ...
    http_api: http_api
http_api:
  enable: true
  # 0.0.0.0: all network interfaces. 127.0.0.1: only via nginx (port 80)
  host: 0.0.0.0
  port: 5559
```

Existing installations: add `http_api: http_api` as the last entry of `modules: named:`.

> [!IMPORTANT]
> There is no password. Everyone in your local network can control the Phoniebox — the same as with the
> Web App and the RPC ports. This includes commands like `shutdown`. Don't make port 80 or 5559 reachable
> from the internet.
