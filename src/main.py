import ctypes
import mimetypes
import sys
import threading
import time
import traceback
from pathlib import Path

from PIL import Image
from pystray import Icon as icon, Menu as menu, MenuItem as item
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from immich import Immich
from settings import ConfigError, load_config

CONFIG_DIR = Path.home() / ".buicha-photo"
APP_VERSION = "2026.06.15.1"
AUTOSTART_DELAY_SECONDS = 20
WATCH_DIRECTORY_RETRY_SECONDS = 15


def _show_error(message):
    # The app runs without a console, so surface fatal problems in a dialog
    # instead of a cryptic "Runtime Error" popup.
    ctypes.windll.user32.MessageBoxW(0, message, "ぶいちゃフォト", 0x10)


def _log_text(text):
    # The app has no console; write diagnostics to a log file instead.
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_DIR / "buicha-photo.log", "a", encoding="utf-8") as log_file:
            log_file.write(text + "\n")
    except Exception:
        pass


def _log_exception(exc_type, exc, tb):
    log_path = CONFIG_DIR / "buicha-photo.log"
    _log_text("\n" + "".join(traceback.format_exception(exc_type, exc, tb)))
    _show_error(f"エラーが発生しました:\n{exc}\n\n詳細はログをご確認ください:\n{log_path}")


sys.excepthook = _log_exception

_log_text(f"--- buicha-photo {APP_VERSION} started ---")


def _acquire_single_instance():
    mutex = ctypes.windll.kernel32.CreateMutexW(
        None, False, "Local\\BuichaPhotoDesktopClient"
    )
    if not mutex or ctypes.windll.kernel32.GetLastError() == 183:
        return None
    return mutex


instance_mutex = _acquire_single_instance()
if instance_mutex is None:
    sys.exit(0)

if "--autostart" in sys.argv:
    _log_text(f"[startup] waiting {AUTOSTART_DELAY_SECONDS} seconds after Windows login")
    time.sleep(AUTOSTART_DELAY_SECONDS)


def on_clicked(icon, item):
    global state
    state = not item.checked
    if state is True:
        print("starting synchronisation")
    else:
        print("ending synchronisation")


def get_extensions_for_type():
    mimetypes.init()
    temp = []
    for ext in mimetypes.types_map:
        if mimetypes.types_map[ext].split('/')[0] == "video" or mimetypes.types_map[ext].split('/')[0] == "image":
            temp.append(ext)
    for ext in mimetypes.common_types:
        if mimetypes.common_types[ext].split('/')[0] == "video" or mimetypes.common_types[ext].split('/')[0] == "image":
            temp.append(ext)

    return tuple(temp)


class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        global state
        if (
            state
            and not event.is_directory
            and event.src_path.lower().endswith(media_file_extensions)
        ):
            print(f"File {event.src_path} has been created!")
            api.created(event.src_path)

    def on_deleted(self, event):
        global state
        if (
            state
            and not event.is_directory
            and event.src_path.lower().endswith(media_file_extensions)
        ):
            print(f"File {event.src_path} has been deleted!")
            api.delete(event.src_path)

    # TODO: make these event handlers work
    #   def on_moved(self, event):
    #       if not event.is_directory and event.src_path.endswith(".png") or event.src_path.endswith(".jpg") or event.src_path.endswith(".jpeg"):
    #           print(f"File {event.src_path} has been moved!")
    #           api.move(event.src_path,event.dest_path)
    #  def on_modified(self, event):
    #      if not event.is_directory and event.src_path.endswith(".png") or event.src_path.endswith(".jpg") or event.src_path.endswith(".jpeg"):
    #          print(f"File {event.src_path} has been modified!")
    #          api.modify(event.src_path)


# Load both current UTF-8 configs and legacy CP932 configs written by older
# installers. Legacy files are rewritten as UTF-8 after a successful load.
config_path = CONFIG_DIR / "config.yaml"
if not config_path.exists():
    _show_error(
        "設定ファイルが見つかりません。\n\n"
        "インストーラ（buicha-photo-installer.exe）を実行して、\n"
        "セットアップを完了してから起動してください。"
    )
    sys.exit(1)

try:
    config, config_encoding, config_text = load_config(config_path)
except (ConfigError, OSError) as exc:
    _log_text("[config] could not load config:\n" + traceback.format_exc())
    _show_error(f"設定ファイルを読み込めませんでした:\n{exc}")
    sys.exit(1)

if config_encoding.lower() not in ("utf-8", "utf-8-sig"):
    try:
        config_path.write_text(config_text, encoding="utf-8", newline="\n")
        _log_text(f"[config] migrated {config_encoding} config to UTF-8")
    except OSError:
        _log_text("[config] could not migrate config to UTF-8:\n" + traceback.format_exc())

media_file_extensions = get_extensions_for_type()

immich_host = config["api"]["url"]
album_name = config["api"].get("album")
api_key = config["api"]["key"]
directories_to_watch = config["watchdog"]["directories"]

state = True

# At Windows login the network (or VPN) may not be ready yet, which would make
# the first server request fail. Retry instead of crashing so auto-start works.
api = None
for attempt in range(30):
    try:
        api = Immich(immich_host, api_key, album_name)
        break
    except Exception:
        _log_text(f"[startup] connection attempt {attempt + 1} failed:\n" + traceback.format_exc())
        time.sleep(10)

if api is None:
    _log_text("[startup] could not reach the server after several attempts; exiting")
    sys.exit(1)

try:
    api.test_connection()
    api.print_shelve()
    api.upload_all_images(directories_to_watch, media_file_extensions)
except Exception:
    _log_text("[startup] initial sync failed:\n" + traceback.format_exc())

# Create observer and event handler
observer = Observer()
event_handler = MyHandler()


def schedule_watch_directories():
    pending = {str(Path(directory).expanduser()) for directory in directories_to_watch}
    while pending:
        for directory in list(pending):
            if not Path(directory).is_dir():
                continue
            try:
                observer.schedule(event_handler, directory, recursive=True)
            except Exception:
                _log_text(
                    f"[watchdog] could not watch {directory!r}:\n"
                    + traceback.format_exc()
                )
                continue

            pending.remove(directory)
            _log_text(f"[watchdog] watching {directory}")

        if pending:
            _log_text(
                "[watchdog] waiting for unavailable directories: "
                + ", ".join(sorted(pending))
            )
            time.sleep(WATCH_DIRECTORY_RETRY_SECONDS)


observer.start()
threading.Thread(
    target=schedule_watch_directories,
    name="watch-directory-retry",
    daemon=True,
).start()

# Update the state in `on_clicked` and return the new state in
# a `checked` callable
icon('test', Image.open(str(CONFIG_DIR / 'icon.ico')), menu=menu(
    item(
        'Sync directories to Immich',
        on_clicked,
        checked=lambda item: state)
)
     ).run()
