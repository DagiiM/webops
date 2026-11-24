"""Bounded static-only publication from a public GitHub archive.

No checkout hooks, package installation, build commands, or application code run.
The resulting site is served on its own local port, never the control-panel origin.
"""
import io
import re
import shutil
import stat
import time
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import requests

MAX_ARCHIVE = 20 * 1024 * 1024
MAX_EXPANDED = 40 * 1024 * 1024
MAX_FILES = 2000
ASSETS = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".png", ".jpg", ".jpeg",
          ".gif", ".svg", ".ico", ".webp", ".woff", ".woff2", ".ttf", ".txt", ".avif", ".pdf"}

def extract_static_archive(raw, destination):
    destination = Path(destination)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) > MAX_FILES or sum(m.file_size for m in members) > MAX_EXPANDED:
            raise ValueError("Repository exceeds static publication size limits")
        destination.mkdir(parents=True, mode=0o700, exist_ok=False)
        try:
            roots = set()
            for item in members:
                path = PurePosixPath(item.filename)
                if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in item.filename:
                    raise ValueError("Invalid archive path")
                roots.add(path.parts[0])
                if len(roots) != 1:
                    raise ValueError("Unexpected archive root")
                parts = path.parts[1:]
                if not parts or item.is_dir() or any(p.startswith(".") for p in parts):
                    continue
                if stat.S_ISLNK(item.external_attr >> 16) or Path(parts[-1]).suffix.lower() not in ASSETS:
                    continue
                target = destination.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=65536)
            if not any((destination / sub / "index.html").is_file() for sub in ("public", "dist", "build", ".")):
                raise ValueError("Static publication requires an index.html")
        except Exception:
            shutil.rmtree(destination)
            raise

def download_static_repository(deployment, destination):
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+)", deployment.repo_url)
    if not match:
        raise ValueError("Static publication requires a public HTTPS GitHub repository")
    owner, repo = match.groups()
    repo = repo.removesuffix(".git")
    branch = deployment.branch
    if not repo or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,99}", branch) or ".." in branch:
        raise ValueError("Invalid repository branch")
    url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{quote(branch, safe='/')}"
    limit = time.monotonic() + 35
    chunks = bytearray()
    with requests.get(url, stream=True, allow_redirects=False, timeout=(5, 8)) as response:
        if response.status_code != 200:
            raise ValueError(f"GitHub archive returned HTTP {response.status_code}")
        for chunk in response.iter_content(65536):
            if time.monotonic() > limit or len(chunks) + len(chunk) > MAX_ARCHIVE:
                raise ValueError("GitHub archive exceeded time or size limit")
            chunks.extend(chunk)
    extract_static_archive(chunks, destination)
