# Current interface

Menu and Stock are the active screens. Service is a Coming soon placeholder. Use the Stock tab for search, +/− updates, reminders, ordering/prep and recent changes. Food icon fields offer a food-emoji picker. The old Service Stories label is no longer displayed. Previous shift records remain in the database/export; shift-entry screens are not currently exposed.

The documentation below describes the initial Mark 1 foundation and includes earlier service features now hidden.

---

# Service Stories · Mark 1

A shared kitchen memory that helps the team know what is ready, what is missing, and what to do next. Built first for Saint Bart’s.

This is the Python version we improve from here. The older JavaScript prototype remains in the parent folder for reference. Mark 1 starts empty: no old journal, counts, estimates, or AI interpretations are imported.

## Try it locally

From the parent `service-stories` folder:

```sh
python3 -m venv .venv
.venv/bin/pip install -r mark1/requirements.txt
cd mark1
../.venv/bin/python app.py
```

Open http://127.0.0.1:4190. On this Mac, `Start Mark 1.command` also starts it. Keep the terminal open while using the local app. This address works only on the computer; Railway supplies the phone-accessible URL.

1. Select your name.
2. Open Menu, add a photo or paste menu text, review the proposed dishes, and confirm.
3. Open a dish and confirm its ingredients or prep. AI proposals do not become inventory until confirmed.
4. Answer one card at a time: storage, quantity, your duration estimate, and reminder level. Skip what you don’t know. Every submitted answer persists.
5. Use the same ingredient cards to receive, make, use, waste, count, or transfer stock.
6. Open Service for covers, stock reminders, ordering/prep tasks and quick notes. Close the service and check stock.
7. Tap your name for team activity, concerns, ownership and resolution.
8. In History choose **+ Past shift**. Four short steps capture date, covers, reservations, walk-ins, rush, weather/terrace, prep observations, quick incident tags, unusual events and a note. Reopen the date to edit. Historical details never change current inventory. One service per calendar date is supported in Mark 1.

No AI key? Manual dishes, all stock actions, service tracking, concerns, and the calculation rules still work. Photo reading and AI-written concern previews need a key.

## Connect OpenAI locally

Open **••• → Connect or change the OpenAI key**. Paste your existing key into the password field and save. Then try a menu photo.

The key is stored in `mark1/data/secret.json`, with owner-only file permissions, outside Git and outside exports. It is only accepted by the setup endpoint on localhost. On Railway use its private Variables instead. A configured key is not proof of an active API balance; the first AI request checks it. No key from the previous ChatGPT Site has been copied here.

## How the code fits together

| File | Responsibility |
|---|---|
| `app.py` | Python/Flask HTTP endpoints, name sessions, validation and atomic saves |
| `domain.py` | Stock movements, quantity checks, predictions and reminder rules |
| `storage.py` | SQLite connections, initialization and backup |
| `schema.sql` | The explicit database structure |
| `intelligence.py` | OpenAI menu reading and short concern previews; no stock writes |
| `static/` | Phone interface, styles and restrained motion |
| `tests/test_app.py` | Workflow, persistence and data-integrity checks |

Each saved action has an idempotency ID. SQLite serializes writes, and each ingredient has a version to catch stale edits. Quantities are totals of remaining batches, not inferred from chat. Unit conversion is intentionally not automatic: a shared item uses one unit. Batch transfers preserve dates. Corrections do not masquerade as consumption.

A prepared component may link to ingredient records. Making a batch does not yet consume those ingredients automatically: record actual usage separately. A measured recipe/yield system can be added when that workflow is validated.

Stock suggestions use your threshold and, once available, average explicitly logged usage across at least two closed services. Unlogged usage is not treated as zero. This is a simple provisional estimate, not a demand model or a safety assessment. Ordering/prep task acceptance preserves an available calculated estimate; observing empty stock records elapsed logged services. Intervening receipts, waste and corrections remain in history and must be considered when assessing that estimate.

Use-by reminders use entered dates. The app never establishes that food is safe. Storage concerns can show batches recorded in that location. Check your kitchen’s procedures and actual conditions.

Name selection is attribution, not secure identity. It deliberately has no passwords or roles. Anyone with access to the hosted app can select a name. The AI only proposes menu structure and concern copy; users confirm changes.

Team updates poll every 15 seconds while the app is open. They are in-app messages, not background phone push notifications. No offline write queue: successful saves need a connection. Unsaved free-text service notes and concerns are kept as browser drafts; other unsaved fields remain on screen after a save error.

## Data and backups

SQLite lives at `mark1/data/mark1.sqlite` locally, or `$DATA_DIR/mark1.sqlite` on Railway. Name sessions persist there too. The full JSON export includes business records and evidence but excludes session tokens and API secrets. Database backups include sessions but exclude the separate secret file.

Settings offers a database backup and a downloadable JSON export. Local database backups stay on the same disk. On Railway enable Volume backups as described in SETUP.md; a same-volume copy is not protection against losing the whole volume. Restore a full SQLite backup with the service stopped, replacing `mark1.sqlite` and removing obsolete WAL/SHM sidecars only after retaining the old files. JSON exports are for inspection/portability; a one-click restore UI is not yet included.

## Verification

```sh
../.venv/bin/python -m unittest discover -s tests -v
```

Tests use isolated temporary databases and mocked OpenAI responses. They do not touch the live app’s records or spend API credit. Real model extraction requires your key and menu; browser/phone visual testing and Railway deployment are still real-world acceptance checks.

See [SETUP.md](../SETUP.md) in the parent directory for GitHub → Railway deployment.
