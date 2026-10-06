import concurrent.futures
import hashlib
import json
import os
import shutil
import struct
import sys
import time
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


BUCKET_ID = os.environ.get("HF_BUCKET_ID", "eysho-it/pocket-tts-models")
BUCKET_ROOT = Path("/bucket")
MODEL_OUT_DIR = Path(os.environ.get("MODEL_OUT_DIR", "/models"))
VOICE_OUT_DIR = Path(os.environ.get("VOICE_OUT_DIR", "/voices"))
STATE_DIR = Path(os.environ.get("STATE_DIR", "/german"))
TOKEN = os.environ.get("HF_TOKEN")
WORKERS = max(1, min(int(os.environ.get("DOWNLOAD_WORKERS", "4")), 8))
API_ROOT = "https://huggingface.co/api/buckets/"
RESOLVE_ROOT = "https://huggingface.co/buckets/"


def request(url):
    headers = {"User-Agent": "pocket-tts-model-sidecar/1.0"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return Request(url, headers=headers)


def get_bucket_files():
    url = f"{API_ROOT}{quote(BUCKET_ID, safe='/')}/tree"
    last_error = None
    for attempt in range(5):
        try:
            with urlopen(request(url), timeout=60) as response:
                files = json.load(response)
            break
        except HTTPError as error:
            if error.code < 500 and error.code != 429:
                raise
            last_error = error
        except (URLError, OSError) as error:
            last_error = error
        if attempt < 4:
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"Could not list bucket files after retries: {last_error}")
    if not isinstance(files, list) or not files:
        raise RuntimeError(f"Bucket has no files or returned an invalid file list: {url}")
    for entry in files:
        path = PurePosixPath(entry["path"])
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"Unsafe path returned by bucket API: {entry['path']}")
    return files


def download(entry, previous_manifest):
    relative_path = entry["path"]
    target = BUCKET_ROOT.joinpath(*PurePosixPath(relative_path).parts)
    expected_size = int(entry["size"])
    revision_hash = entry.get("xetHash")
    if (
        target.is_file()
        and target.stat().st_size == expected_size
        and previous_manifest.get(relative_path) == revision_hash
    ):
        return f"cached {relative_path}"

    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"{RESOLVE_ROOT}{quote(BUCKET_ID, safe='/')}/resolve/{quote(relative_path, safe='/')}"
    temporary = target.with_name(target.name + ".part")
    last_error = None
    for attempt in range(3):
        try:
            digest = hashlib.sha256()
            received = 0
            with urlopen(request(url), timeout=120) as response, temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
            if received != expected_size:
                raise RuntimeError(
                    f"{relative_path}: expected {expected_size} bytes, received {received}"
                )
            temporary.replace(target)
            return f"downloaded {relative_path} ({received} bytes, sha256 {digest.hexdigest()[:12]})"
        except (HTTPError, URLError, OSError, RuntimeError) as error:
            last_error = error
            temporary.unlink(missing_ok=True)
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to download {relative_path}: {last_error}")


def write_raven_bos_embedding():
    checkpoint = BUCKET_ROOT / "german" / "model.safetensors"
    output_path = BUCKET_ROOT / "de" / "bos_before_voice.npy"
    with checkpoint.open("rb") as source:
        header_size = struct.unpack("<Q", source.read(8))[0]
        header = json.loads(source.read(header_size))
        tensor = header.get("flow_lm.bos_before_voice")
        if not tensor or tensor.get("dtype") != "BF16" or tensor.get("shape") != [1, 1, 1024]:
            raise RuntimeError("German checkpoint has no compatible BF16 bos_before_voice tensor")
        start, end = tensor["data_offsets"]
        source.seek(8 + header_size + start)
        bf16_bytes = source.read(end - start)
    if len(bf16_bytes) != 2048:
        raise RuntimeError("Unexpected bos_before_voice tensor size")

    values = struct.unpack("<1024H", bf16_bytes)
    float32_bytes = b"".join(struct.pack("<I", value << 16) for value in values)
    header_text = "{'descr': '<f4', 'fortran_order': False, 'shape': (1, 1, 1024), }"
    padding = (16 - ((10 + len(header_text) + 1) % 16)) % 16
    header_bytes = (header_text + " " * padding + "\n").encode("latin1")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output:
        output.write(b"\x93NUMPY\x01\x00")
        output.write(struct.pack("<H", len(header_bytes)))
        output.write(header_bytes)
        output.write(float32_bytes)
    print(f"prepared {output_path.relative_to(BUCKET_ROOT)} from the German checkpoint", flush=True)


def count_files(path):
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob("*") if _.is_file())


def write_status(status, files_downloaded=None, model_files=None, voice_files=None):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "bucket": BUCKET_ID,
        "downloaded_files": files_downloaded if files_downloaded is not None else count_files(BUCKET_ROOT),
        "model_files": model_files if model_files is not None else count_files(MODEL_OUT_DIR),
        "voice_files": voice_files if voice_files is not None else count_files(VOICE_OUT_DIR),
        "models_dir": str(MODEL_OUT_DIR),
        "voices_dir": str(VOICE_OUT_DIR),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    status_path = STATE_DIR / "status.json"
    status_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"status: {status} -> {status_path}", flush=True)


def sync_runtime_layout():
    MODEL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    VOICE_OUT_DIR.mkdir(parents=True, exist_ok=True)

    for relative in ("de", "german"):
        source_dir = BUCKET_ROOT / relative
        target_dir = MODEL_OUT_DIR / relative
        if source_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            for child in source_dir.iterdir():
                destination = target_dir / child.name
                if child.is_dir():
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(child, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, destination)

    flattened_aliases = {
        "flow_lm_main_int8.onnx": "de/lm_main.int8.onnx",
        "flow_lm_flow_int8.onnx": "de/lm_flow.int8.onnx",
        "mimi_decoder_int8.onnx": "de/decoder.int8.onnx",
        "mimi_encoder.onnx": "de/encoder.onnx",
        "text_conditioner.onnx": "de/text_conditioner.onnx",
        "bos_before_voice.npy": "de/bos_before_voice.npy",
    }
    for alias_name, relative_source in flattened_aliases.items():
        source_path = BUCKET_ROOT / relative_source
        if source_path.exists():
            shutil.copy2(source_path, MODEL_OUT_DIR / alias_name)

    if (BUCKET_ROOT / "de" / "default.wav").exists():
        shutil.copy2(BUCKET_ROOT / "de" / "default.wav", VOICE_OUT_DIR / "default.wav")
        shutil.copy2(BUCKET_ROOT / "de" / "default.wav", VOICE_OUT_DIR / "de-default.wav")

    print(f"runtime layout synced to {MODEL_OUT_DIR} and {VOICE_OUT_DIR}", flush=True)


def main():
    BUCKET_ROOT.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_status("downloading", files_downloaded=0, model_files=0, voice_files=0)

    manifest_path = BUCKET_ROOT / ".hf-bucket-manifest.json"
    try:
        old_manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        old_manifest = {}

    files = get_bucket_files()
    previous_manifest = old_manifest.get("files", {})
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(download, item, previous_manifest) for item in files]
        for future in concurrent.futures.as_completed(futures):
            print(future.result(), flush=True)

    write_raven_bos_embedding()
    sync_runtime_layout()
    manifest = {
        "bucket": BUCKET_ID,
        "files": {item["path"]: item.get("xetHash") for item in files},
    }
    temporary_manifest = manifest_path.with_suffix(".tmp")
    temporary_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary_manifest.replace(manifest_path)
    write_status(
        "ready",
        files_downloaded=len(files),
        model_files=count_files(MODEL_OUT_DIR),
        voice_files=count_files(VOICE_OUT_DIR),
    )
    print(f"Ready: {len(files)} bucket files in {BUCKET_ROOT}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"model sidecar failed: {error}", file=sys.stderr, flush=True)
        raise