# Folio — Personal Media Library

A personal media library with a responsive English/Japanese interface, metadata and aliases, flexible ratings, search, bookmark imports, and a memory-only thumbnail relay. Built with Python's standard library, SQLite, and browser JavaScript.

## Run locally

Requires Python 3.11 or newer. From the repository directory:

```sh
cd media-library
python server.py --host 127.0.0.1 --port 8765
```

Open http://localhost:8765. For Windows launchers, automatic startup, LAN access, features, and tests, see [the application guide](media-library/README.md).

This version uses one shared local library without account authentication. Host it on your PC or trusted LAN; account registration and public hosting are future work.

## Development references

- [Requirements specification](Personal-Media-Database-Requirements-v2.0.md)
- [Verification notes](media-library/VERIFICATION.md)
- [Thumbnail investigation](media-library/THUMBNAIL-INVESTIGATION.md)
- [nhentai and duplicate-handling proposals](media-library/NHENTAI-AND-DUPLICATES.md)

The repository includes application source and documentation. Personal library databases, backups, logs, imported bookmark files, and local test output are excluded. A fresh installation creates its own empty database.
