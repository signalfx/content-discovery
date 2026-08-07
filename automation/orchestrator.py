"""Deprecated shim — use python -m contentforge.pipeline.orchestrator instead."""

if __name__ == "__main__":
    from contentforge.pipeline.orchestrator import main

    raise SystemExit(main())
