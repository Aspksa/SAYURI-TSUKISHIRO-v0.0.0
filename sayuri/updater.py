"""Safe staged updates from the project's GitHub repository.

No user data is overwritten. Updates are staged while the server runs and
applied by the Windows launcher before the next server start.
"""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from .core import ROOT

OWNER = "Aspksa"
REPO = "SAYURI-TSUKISHIRO-v0.0.0"
# Until main contains the application, track the development branch.
DEFAULT_BRANCH = "main"
ALLOWED_BRANCHES = ("main", DEFAULT_BRANCH)
MAX_FILE = 512 * 1024
MAX_TOTAL = 4 * 1024 * 1024
MAX_FILES = 60
UPDATES = ROOT / "data" / ".updates"
PENDING = UPDATES / "pending"
ALLOWED_EXACT = {"SAYURITSUKISHIRO.bat", "PORTABLE.md", ".gitignore", "README.md",
                 "update-manifest.json"}
ALLOWED_DIRS = ("sayuri/", "web/", "tests/")


class UpdateError(Exception):
    pass


def request_bytes(url, limit=MAX_FILE):
    req = Request(url, headers={"User-Agent": "SayuriPortableUpdater/0.0.0",
                                "Accept": "application/vnd.github+json"})
    try:
        with urlopen(req, timeout=20) as response:
            data = response.read(limit + 1)
    except Exception as exc:
        raise UpdateError("GitHub is unavailable: " + str(exc)) from exc
    if len(data) > limit:
        raise UpdateError("GitHub response exceeds size limit")
    return data


def allowed(path):
    if not isinstance(path, str) or "\\" in path or not path or path.startswith("/"):
        return False
    bits = path.split("/")
    if any(part in ("", ".", "..") or part.startswith(".") for part in bits):
        return path in ALLOWED_EXACT
    return path in ALLOWED_EXACT or (
        path.startswith(ALLOWED_DIRS)
        and not any(part in ("data", "runtime", "__pycache__") for part in bits)
        and path.endswith((".py", ".html", ".css", ".js"))
    )


def github_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def manifest_and_tree(branch):
    if branch not in ALLOWED_BRANCHES:
        raise UpdateError("Unsupported update branch")
    base = f"https://api.github.com/repos/{OWNER}/{REPO}"
    manifest_url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{branch}/update-manifest.json"
    try:
        manifest = json.loads(request_bytes(manifest_url, 100_000))
        ref_data = json.loads(request_bytes(f"{base}/git/ref/heads/{branch}", 100_000))
        commit_sha = ref_data["object"]["sha"]
        tree = json.loads(request_bytes(f"{base}/git/trees/{commit_sha}?recursive=1", 2_000_000))
        files = manifest["files"]
        if (not isinstance(files, list) or not files or len(files) > MAX_FILES or
                len(set(files)) != len(files) or not all(allowed(p) for p in files)):
            raise UpdateError("Invalid update manifest")
        if tree.get("truncated"):
            raise UpdateError("GitHub tree was truncated")
        entries = {x["path"]: x["sha"] for x in tree["tree"] if x.get("type") == "blob"}
        if any(path not in entries for path in files):
            raise UpdateError("Manifest refers to a missing file")
        return files, entries, tree.get("sha")
    except (KeyError, TypeError, ValueError) as exc:
        raise UpdateError("Invalid response from GitHub") from exc


def check(branch=DEFAULT_BRANCH, root=ROOT):
    files, entries, tree_sha = manifest_and_tree(branch)
    root = Path(root)
    changed = []
    for path in files:
        local = root / path
        if not local.is_file() or github_blob_sha(local.read_bytes()) != entries[path]:
            changed.append(path)
    return {"branch": branch, "source": f"{OWNER}/{REPO}",
            "revision": tree_sha, "changed": changed, "available": bool(changed)}


def stage(branch=DEFAULT_BRANCH, root=ROOT):
    files, entries, tree_sha = manifest_and_tree(branch)
    root = Path(root)
    changed = [p for p in files if not (root / p).is_file()
               or github_blob_sha((root / p).read_bytes()) != entries[p]]
    if not changed:
        return {"staged": False, "changed": [], "restart_required": False}
    # Data directory and local configuration are never listed in the manifest.
    updates = root / "data" / ".updates"
    updates.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="prepare-", dir=updates))
    total = 0
    try:
        for path in changed:
            url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{branch}/{path}"
            data = request_bytes(url)
            total += len(data)
            if total > MAX_TOTAL or github_blob_sha(data) != entries[path]:
                raise UpdateError(f"Integrity check failed: {path}")
            target = work / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        meta = {"branch": branch, "revision": tree_sha,
                "files": {p: entries[p] for p in changed}}
        (work / ".pending.json").write_text(json.dumps(meta), encoding="utf-8")
        pending = updates / "pending"
        if pending.exists():
            shutil.rmtree(pending)
        work.rename(pending)
        return {"staged": True, "changed": changed, "restart_required": True}
    except BaseException:
        if work.exists():
            shutil.rmtree(work)
        raise


def apply_pending(root=ROOT):
    root = Path(root)
    pending = root / "data" / ".updates" / "pending"
    if not pending.exists():
        return False
    try:
        meta = json.loads((pending / ".pending.json").read_text(encoding="utf-8"))
        items = meta["files"]
        if not isinstance(items, dict) or not items or any(not allowed(p) for p in items):
            raise UpdateError("Invalid pending update")
        for path, sha in items.items():
            if github_blob_sha((pending / path).read_bytes()) != sha:
                raise UpdateError("Pending update failed integrity checks")
        backup = root / "data" / ".updates" / "backup"
        if backup.exists():
            shutil.rmtree(backup)
        backup.mkdir(parents=True)
        originals = []
        try:
            for path in items:
                dest = root / path
                old = backup / path
                if dest.exists():
                    old.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, old)
                originals.append(path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                staged = pending / path
                os.replace(staged, dest)
        except BaseException:
            for path in reversed(originals):
                old = backup / path
                dest = root / path
                if old.exists():
                    shutil.copy2(old, dest)
                elif dest.exists():
                    dest.unlink()
            raise
        shutil.rmtree(pending)
        # Preserve the backup as an additional recovery option.
        return True
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise UpdateError("Could not apply update: " + str(exc)) from exc


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2 and sys.argv[1] == "--apply":
        try:
            print("Pending update applied." if apply_pending() else "No pending update.")
        except UpdateError as exc:
            print(exc, file=sys.stderr)
            sys.exit(1)
    else:
        print("Usage: python -m sayuri.updater --apply")
