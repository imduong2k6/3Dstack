# Pipeline Map

Source of the Pipeline Map artifact, the page where the user reviews the pipeline and asks for changes. The link is in the manager's memory, not here, and the page is private to the user's account.

Rebuild after any change to the skills, agents or this folder:

```bash
python docs/pipeline/map/inventory.py
python docs/pipeline/map/build.py
```

Then publish `docs/pipeline/map/pipeline_map.html` (generated, not committed) to the artifact's existing URL. Omit `icon` and `capabilities`, so the stored ones carry forward.

| File | Holds |
| --- | --- |
| `data.py` | Stages, gates, routes, agents' jobs, rules, decisions and my suggestions |
| `blocks.py` | What each block on the map does, checks, researches and writes |
| `build.py`, `template.html` | The page |
| `inventory.py` | Reads skills and agents from the repo into `inventory.json` |
| `labels.json`, `board.json`, `roadmap.json` | Frozen once from sources outside the repo: Skills Map labels, the user's board answers, the audit report's roadmap rows. Edit them by hand from now on. `build.py` fails if a skill is added or removed without its label |

`build.py` refuses to write a page containing private project names, read as one regex from `private_names.txt`. That file is git-ignored because it names them, so a fresh clone must create it before building. Projects stay out of this repo (`house-rules` rule 3).

The page's database holds what the user and Claude write at run time, so it isn't in this folder: `feedback/<id>` (`title`, `verdict`, `note`, `updated`, `status`, `reply`) and `changes/<id>` (`at`, `title`, `what`, `status`, `from`, `commit`). `status` on a comment is `open`, `answered`, `waiting`, `doing` or `done`; on a change it is `waiting`, `doing` or `done`.
