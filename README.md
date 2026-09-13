# St. Barts · Service Stories

**The current build is Mark 1, with a Python backend.**

- [Open the Mark 1 code and guide](mark1/README.md)
- [GitHub → Railway + OpenAI setup](SETUP.md)
- [Working product direction](mark1/PRODUCT.md)

Run `Start Mark 1.command` and open http://127.0.0.1:4190.

The notes below describe the earlier JavaScript prototype, preserved as reference. Its data is not imported into Mark 1.

---

# St. Barts — Service Stories

A local prototype for discovering the product through real services.

Double-click **Start.command**, then use the app at http://127.0.0.1:4188. Keep its terminal open while using it. It needs Node.js 24+; the launcher prefers the installed Codex runtime and falls back to system Node.

## What the experiment does

- Opens with a greeting and a simple expectation question.
- Uses prior journal observations to select questions about prep, rushes, walk-ins, and leftovers. Each question has three tap answers.
- Branches based on answers (e.g. running low → possible constraint; leftovers → actual outcome).
- Saves original observations, answers, before/after expectations, derived suggestions, supporting note IDs, and useful/not-useful feedback.
- Allows custom questions and answer buttons, edits, and retirement. These changes have their own history so the prototype is part of the product-building process.
- Copies the four existing online notebook entries into this local database. Original records remain intact. Duplicate copied text is not counted as independent evidence in built-in pattern discovery.
- Keeps notes and questions separate from AI interpretations. Local discovery currently has a small, explicit set of rules informed by this journal, plus custom tracking. It is not model training or a general forecasting model.

## Ownership and persistence

Source code lives in this folder. `data/stories.sqlite` contains the records. `data/backups/YYYY-MM-DD.sqlite` contains local daily snapshots updated after saves. These are on the same disk, not off-device disaster recovery. Export in Settings includes notes, structured answers, insights, feedback, question templates, and product changes, never the API key.

The local app does not require ChatGPT hosting or an active chat. It is bound to your Mac's loopback address; it is not reachable from a phone or another device. Data remains after the app stops. The earlier online Site is unchanged and is not continuously synced with this local copy.

## Optional AI

In **••• → Settings**, paste an OpenAI key into the password field. The secret saved on the online Site cannot be transferred back automatically. Local keys are kept in `data/secrets.json` with owner-only file permissions and are excluded from exports, database backups, and Git. Alternatively set OPENAI_API_KEY in the server environment.

AI is opt-in: use Ask AI for a single response, or enable responses after notes in Settings. Recent notes and helpfulness feedback are sent to OpenAI only on those actions. API billing is separate. The model is gpt-4.1-mini with store:false. AI outputs are saved locally with references to supplied observations. They are hypotheses to assess, not certified conclusions. A real provider request requires a local key; no secret was copied from the hosted Site.

## Checks

Run `node --test tests/*.test.mjs` with Node 24+. Integration tests use a disposable separate database. No live journal data or API balance is used.
