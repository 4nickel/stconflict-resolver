#### Conflict resolution tool for syncthing

> This is work-in-progress. It should work as expected, but has only been tested on Linux.

This tool scans a directory for sync-conflicts and helps you resolve them, either manually or by applying some simple heuristics.

A summary of recommended actions is shown to the user, and no action is taken, unless the ``--commit`` flag is provided.

Usage:
```sh
stconflict-resolver <path>
stconflict-resolver --commit <path>
```