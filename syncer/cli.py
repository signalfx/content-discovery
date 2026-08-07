"""Deprecated shim — use python -m contentforge.syncer.cli instead."""

if __name__ == "__main__":
    from contentforge.syncer.cli import main

    raise SystemExit(main())
