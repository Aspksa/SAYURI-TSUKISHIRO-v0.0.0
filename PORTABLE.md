# Portable use and GitHub updates — SAYURI TSUKISHIRO v0.0.0

Local Windows prototype, **no Cloud.ru**, no cloud synchronization.

## Folder and portable launch
Use a **writable** folder on HDD, SSD, or USB drive. The application uses relative paths based on its own location. `data/sayuri.db` and SQLite WAL stay beside the application; never remove the USB while Sayuri is running.

Install Python 3 for Windows or supply a compatible Windows portable Python runtime at `runtime/python/python.exe` with the standard library and SQLite. The Python runtime is **not** bundled. Run `SAYURITSUKISHIRO.bat` then open `http://127.0.0.1:8765`.

To obtain the sources using GitHub without manual ZIP downloads (Git must be installed):

```bat
git clone https://github.com/Aspksa/SAYURI-TSUKISHIRO-v0.0.0.git
```

## Left sidebar
- Overview (core health)
- Database (SQLite notes)
- Project Update (GitHub)

## Updates from GitHub
The updater tracks the **main** branch of this GitHub repository.

1. Open **Project Update** in the left navigation and click **Check for updates**.
2. Review changes and click **Prepare update**.
3. Close the running BAT window gracefully (Ctrl+C). Run `SAYURITSUKISHIRO.bat` again; the launcher applies verified, staged application files before starting the server.
4. On failure, the updater attempts rollback; a previous-file backup remains under `data/.updates/backup`.

Changes are only fetched from the fixed GitHub repository. Files are verified against GitHub Git blob SHA-1 values and restricted to the manifest's application paths. No delete actions are taken. **Database, runtime and local user data are excluded.** The launcher file is intentionally stable and is not overwritten while it executes.

Internet access is required for GitHub update checks, not normal local operation. The API is **localhost-only**: there is no user authentication or safe LAN/Internet deployment yet. Only trust changes merged to the configured repository branch; branch code updates can execute on your machine on restart.

Run unit tests locally: `python -m unittest discover -s tests -v`. Windows/USB smoke testing is still required.
