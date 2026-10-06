"""Local file storage ("Disk"): folders, uploads and a trash bin under data/disk."""
import json
import mimetypes
import os
import shutil
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

MAX_UPLOAD = 4 * 1024 ** 3
RESERVE = 64 * 1024 ** 2
CHUNK = 1024 * 1024
# Only raster images are ever served inline; everything else is a download.
PREVIEW_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "image/avif"}
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
BAD_CHARS = set('<>:"/\\|?*')


class DiskError(ValueError):
    pass


def check_name(name):
    if not isinstance(name, str):
        raise DiskError("Некорректное имя")
    name = name.strip()
    if (not name or name in (".", "..") or len(name) > 200 or name.endswith(".")
            or any(c in BAD_CHARS or ord(c) < 32 for c in name)
            or name.split(".")[0].upper() in RESERVED):
        raise DiskError("Недопустимое имя: " + name[:60])
    return name


def stamp(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def remove_tree(path):
    def retry(func, target, _):
        # Windows refuses to delete read-only files; clear the flag and retry.
        os.chmod(target, stat.S_IWRITE)
        func(target)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def tree_size(path):
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


class Disk:
    def __init__(self, directory):
        base = Path(directory)
        self.files = base / "files"
        self.trash = base / "trash"
        self.tmp = base / "tmp"
        for folder in (self.files, self.trash, self.tmp):
            folder.mkdir(parents=True, exist_ok=True)
        for leftover in self.tmp.iterdir():  # interrupted uploads
            leftover.unlink(missing_ok=True)
        self._real = self.files.resolve()

    def resolve(self, rel=""):
        if not isinstance(rel, str):
            raise DiskError("Некорректный путь")
        parts = [p for p in rel.split("/") if p]
        for part in parts:
            if check_name(part) != part:
                raise DiskError("Недопустимое имя: " + part[:60])
        path = self.files.joinpath(*parts)
        real = path.resolve()
        if real != self._real and self._real not in real.parents:
            raise DiskError("Путь вне диска")
        return path

    def rel(self, path):
        return "" if path == self.files else path.relative_to(self.files).as_posix()

    def folder(self, rel):
        folder = self.resolve(rel)
        if not folder.is_dir():
            raise FileNotFoundError(rel)
        return folder

    def existing(self, rel):
        path = self.resolve(rel)
        if path == self.files:
            raise DiskError("Нельзя изменить корень диска")
        if not path.exists():
            raise FileNotFoundError(rel)
        return path

    def entry(self, path):
        info = path.stat()
        is_dir = path.is_dir()
        return {"name": path.name, "path": self.rel(path), "type": "dir" if is_dir else "file",
                "size": None if is_dir else info.st_size, "modified": stamp(info.st_mtime)}

    @staticmethod
    def free_name(folder, name):
        """Yandex-style conflict naming: "photo.jpg" -> "photo (1).jpg"."""
        if not (folder / name).exists():
            return folder / name
        stem, suffix = (name, "") if (folder / name).is_dir() else (Path(name).stem, Path(name).suffix)
        n = 1
        while (folder / f"{stem} ({n}){suffix}").exists():
            n += 1
        return folder / f"{stem} ({n}){suffix}"

    def list(self, rel=""):
        folder = self.folder(rel)
        items = [self.entry(p) for p in folder.iterdir() if not p.is_symlink()]
        items.sort(key=lambda e: (e["type"] != "dir", e["name"].lower()))
        return {"path": self.rel(folder), "items": items}

    def file(self, rel):
        path = self.existing(rel)
        if not path.is_file():
            raise DiskError("Это папка, а не файл")
        return path

    def mkdir(self, rel, name):
        target = self.folder(rel) / check_name(name)
        if target.exists():
            raise FileExistsError(name)
        target.mkdir()
        return self.entry(target)

    def upload(self, rel, name, stream, size):
        folder = self.folder(rel)
        name = check_name(name)
        if size < 0 or size > MAX_UPLOAD:
            raise DiskError("Файл больше 4 ГБ")
        if shutil.disk_usage(self.files).free - size < RESERVE:
            raise DiskError("Недостаточно места на носителе")
        tmp = self.tmp / (uuid.uuid4().hex + ".part")
        remaining = size
        try:
            with open(tmp, "wb") as out:
                while remaining:
                    chunk = stream.read(min(CHUNK, remaining))
                    if not chunk:
                        raise DiskError("Загрузка прервана")
                    out.write(chunk)
                    remaining -= len(chunk)
            target = self.free_name(folder, name)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
        return self.entry(target)

    def rename(self, rel, name):
        path = self.existing(rel)
        target = path.with_name(check_name(name))
        # Allow case-only renames, which Windows reports as "already exists".
        if target.exists() and not os.path.samefile(target, path):
            raise FileExistsError(name)
        path.rename(target)
        return self.entry(target)

    def delete(self, rel):
        """Move to the trash; nothing is destroyed until the trash is emptied."""
        path = self.existing(rel)
        item = uuid.uuid4().hex
        box = self.trash / item
        box.mkdir()
        meta = {"id": item, "name": path.name, "from": self.rel(path.parent),
                "type": "dir" if path.is_dir() else "file", "size": tree_size(path),
                "deleted": datetime.now(timezone.utc).isoformat()}
        try:
            shutil.move(str(path), str(box / "content"))
        except OSError:
            remove_tree(box)
            raise
        (box / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return meta

    def trash_items(self):
        items = []
        for box in self.trash.iterdir():
            try:
                items.append(json.loads((box / "meta.json").read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        items.sort(key=lambda m: m.get("deleted", ""), reverse=True)
        return items

    def box(self, item):
        if not isinstance(item, str) or len(item) != 32 or any(c not in "0123456789abcdef" for c in item):
            raise DiskError("Некорректный идентификатор")
        box = self.trash / item
        if not (box / "meta.json").is_file():
            raise FileNotFoundError(item)
        return box

    def restore(self, item):
        box = self.box(item)
        meta = json.loads((box / "meta.json").read_text(encoding="utf-8"))
        try:
            folder = self.resolve(meta.get("from", ""))
            folder.mkdir(parents=True, exist_ok=True)
        except (DiskError, OSError):
            folder = self.files  # original location is gone or blocked
        target = self.free_name(folder, check_name(meta["name"]))
        shutil.move(str(box / "content"), str(target))
        remove_tree(box)
        return self.entry(target)

    def empty_trash(self):
        count = 0
        for box in self.trash.iterdir():
            remove_tree(box)
            count += 1
        return count

    def usage(self):
        disk = shutil.disk_usage(self.files)
        return {"used": tree_size(self.files), "trash": tree_size(self.trash),
                "free": disk.free, "total": disk.total}


def preview_type(path):
    mime = mimetypes.guess_type(path.name)[0]
    return mime if mime in PREVIEW_TYPES else None
