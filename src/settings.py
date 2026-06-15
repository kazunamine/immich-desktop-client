import codecs
import locale
from pathlib import Path

import yaml


class ConfigError(ValueError):
    pass


def _decode_config(raw):
    encodings = []
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encodings.append("utf-16")

    encodings.extend(("utf-8-sig", locale.getpreferredencoding(False), "cp932", "mbcs"))

    tried = set()
    decode_errors = []
    for encoding in encodings:
        normalized = encoding.lower()
        if normalized in tried:
            continue
        tried.add(normalized)

        try:
            return raw.decode(encoding), encoding
        except (LookupError, UnicodeDecodeError) as exc:
            decode_errors.append(f"{encoding}: {exc}")

    raise ConfigError(
        "設定ファイルの文字コードを判別できませんでした。\n" + "\n".join(decode_errors)
    )


def load_config(path):
    path = Path(path)
    text, encoding = _decode_config(path.read_bytes())

    try:
        config = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"設定ファイルの形式が正しくありません: {exc}") from exc

    if not isinstance(config, dict):
        raise ConfigError("設定ファイルの内容が空か、正しい形式ではありません。")

    try:
        api = config["api"]
        watchdog = config["watchdog"]
        api_key = api["key"]
        api_url = api["url"]
        directories = watchdog["directories"]
    except (KeyError, TypeError) as exc:
        raise ConfigError(f"設定ファイルに必須項目がありません: {exc}") from exc

    if not isinstance(api_key, str) or not api_key.strip():
        raise ConfigError("APIキーが設定されていません。")
    if not isinstance(api_url, str) or not api_url.strip():
        raise ConfigError("API URLが設定されていません。")
    if (
        not isinstance(directories, list)
        or not directories
        or any(not isinstance(directory, str) or not directory.strip() for directory in directories)
    ):
        raise ConfigError("監視フォルダが正しく設定されていません。")

    return config, encoding, text
