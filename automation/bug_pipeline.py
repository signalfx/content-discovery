"""Deprecated shim — use python -m contentforge.pipeline.bug_pipeline instead."""

if __name__ == "__main__":
    from contentforge.pipeline.bug_pipeline import main

    raise SystemExit(main())
