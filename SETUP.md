# Put Mark 1 on your phone: GitHub → Railway

The Python app is ready locally. These steps publish that same code and create the cloud database. The old ChatGPT Site is a separate earlier version; it is not automatically updated by this build.

## 1. Save the code to GitHub

Use the **service-stories** folder as the repository root. It already contains Git history, the new `mark1/` Python app, a Dockerfile, and Railway configuration.

The easiest visual route is GitHub Desktop:

1. Choose **File → Add Local Repository** and select `service-stories`.
2. Publish the repository to your GitHub account. Keep it **private** for now. `service-stories` is a working repository name; we can rename the product later.
3. Confirm you see `Dockerfile`, `railway.json`, and the `mark1` folder in GitHub.

Do not drag the whole workspace onto GitHub’s file-upload page. The repository’s ignore rules exclude local databases, session records, the Python environment, and API keys. Only publish the source through Git.

If you prefer Git commands, create an empty private GitHub repository first and follow the exact “push an existing repository” commands it displays. Do not initialize it with an extra README. The local code is already committed.

## 2. Connect Railway

1. In Railway, create a project and choose **Deploy from GitHub repo**.
2. Authorize Railway to access the private repository and select it.
3. Use the repository root, with no Root Directory override. The included Dockerfile builds the Python app; `railway.json` selects it and configures the `/health` check.
4. Attach a **Volume** to this app service, mounted at **`/data`**.
5. In the app service’s **Variables**, add:

| Variable | Value |
|---|---|
| `DATA_DIR` | `/data` |
| `OPENAI_API_KEY` | Your existing OpenAI API key |
| `OPENAI_MODEL` | `gpt-4.1-mini` (optional; already the default) |

6. Apply/deploy the changes. If the very first automatic deployment starts before the volume is attached, it will stop with a storage-setup message. Attach the volume and redeploy; that is intentional protection against saving to a temporary filesystem.
7. Generate a public domain for the app in Railway’s networking settings. Open its HTTPS URL.
8. Add `PUBLIC_ORIGIN` with that exact HTTPS origin, without a trailing slash, then apply the change. Example format: `https://your-generated-domain.up.railway.app`—use your actual domain.
9. Keep **one replica**. The included server uses one process with four threads and SQLite on the attached volume.
10. Enable Railway’s Volume backup schedule. Use the app’s Export as an additional portable copy.

The app uses names, not passwords, as agreed. This Railway URL is not gated by the previous ChatGPT Site’s sign-in. Share it with the intended restaurant team; any visitor who can open it can choose a name and contribute. Stronger access control is a separate later feature.

Official references: [GitHub deployments](https://docs.railway.com/deployments/github-autodeploys), [persistent volumes](https://docs.railway.com/volumes), [variables](https://docs.railway.com/variables), [volume backups](https://docs.railway.com/volumes/backups).

## 3. Add the OpenAI key

For the online version, paste the key only into Railway’s `OPENAI_API_KEY` variable. Do not paste it into chat or commit it to GitHub. Apply the Railway change so the running app receives it.

In the app, **•••** should show **OpenAI key connected**. That means a key is configured. Open **Menu → Add your menu** and try a photo to verify actual API access. If OpenAI rejects the key or the account has no available API usage, the app shows the provider error without changing your stock.

For local use, open **••• → Connect or change the OpenAI key**, paste it, and save. Local and Railway setup are separate. The earlier ChatGPT Site key cannot be transferred back automatically.

Menu photos are sent to OpenAI when you press **Read my menu**. AI concern previews send the concern and relevant saved context. The Python server holds the key, and uses `store: false` on Responses requests. The photo itself is not retained after extraction; the editable proposed menu and confirmed records are saved.

Official API reference: [OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision).

## 4. Check the actual restaurant flow

1. Open the Railway URL on your phone; choose your name.
2. Upload the menu, review the dishes, and count one real ingredient.
3. Open the same URL on another device, select another name, and confirm the shared stock appears.
4. Add a concern and confirm the other device receives the in-app update while open.
5. Redeploy once and verify the same records remain. This checks the volume before you rely on the app during service.

Local and Railway databases are separate. Use the Railway URL on both devices for shared ongoing data. The Mac can be off when the Railway app is running.

After that, changes follow one path: edit locally → run checks → commit/push to GitHub → Railway deploys. The attached volume retains the restaurant’s records across code updates.
