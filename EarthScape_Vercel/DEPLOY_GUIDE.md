# EarthScape on Vercel and Supabase

This edition runs the real Python analytics API on Vercel and keeps observations, users, sessions, jobs, tickets and encrypted image archives in Supabase PostgreSQL. It uses the original interface and real scikit-learn models. Your original local/Hadoop project is unchanged.

## 1. Create a free Supabase project

1. Visit https://supabase.com/dashboard and sign in.
2. Create an organization on the Free plan, then a project named `EarthScape`.
3. Choose a strong database password and save it privately. Select a region near your visitors.
4. Wait until the database is ready.
5. Open SQL Editor, create a new query, paste ALL of `supabase_setup.sql`, then Run. This creates the application tables, permissions, server-only functions and 720 synthetic observations. No database password is stored in this SQL.
6. Open Project Settings / API or the Connect dialog and copy the Project URL.
7. Find the server-only legacy `service_role` API key under Settings / API Keys (the Legacy API Keys section if shown). Do not use the public anon/publishable key. Never paste the service_role key in chat, frontend code or GitHub.

The database password and the service_role API key are different. This edition uses the HTTPS API, so it does not need your database connection password or a DATABASE_URL.

## 2. Upload this folder to GitHub

1. Extract `EarthScape_Vercel.zip`.
2. In your existing GitHub repository use Add file / Upload files.
3. Drag the complete `EarthScape_Vercel` folder, preserving its subfolders, and commit.
4. Check that the repository contains `EarthScape_Vercel/api/index.py`, `EarthScape_Vercel/public/index.html` and `EarthScape_Vercel/vercel.json`.

Do not overwrite `05_Project/EarthScape` or upload another copy of the portable runtime. This deployment is separate. Files beginning with a dot may be hidden in Windows; the required Python version is also declared in `pyproject.toml` so missing dotfiles do not change it.

## 3. Create an encryption key privately

If Python is installed locally, run:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Or use the Python runtime already supplied in the original full package. Open a Command Prompt inside `05_Project/EarthScape` and run:

    portable\windows\python\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Copy the printed key privately. It is a new cloud archive key, not the Supabase API key. Keep it in a password manager. Replacing it makes existing encrypted archives/snapshots unreadable. Never use an online secret generator.

## 4. Import into Vercel

1. Visit https://vercel.com/new and import your GitHub repository.
2. Use the Hobby plan for an eligible personal demonstration, within its free limits.
3. Framework Preset: Other.
4. Root Directory: `EarthScape_Vercel` (NOT `05_Project/EarthScape`, NOT `public`, NOT `static`).
5. Leave Build Command and Install Command at their defaults, with no custom commands. The Python builder reads requirements.txt.
6. Output Directory is `public`, already defined in vercel.json. Python functions remain in api/.
7. Before deploying, add the six environment variables below. Enable them for Production; also enable Preview if you plan to test previews. Do not expose database credentials to previews from untrusted code.

| Name | Value |
|---|---|
| SUPABASE_URL | Your Supabase Project URL, starting with https:// |
| SUPABASE_SERVICE_ROLE_KEY | Your private server-only service_role API key |
| EARTHSCAPE_ENCRYPTION_KEY | The new Fernet key generated in step 3 |
| EARTHSCAPE_ADMIN_PASSWORD | Your private admin password, at least 12 characters |
| EARTHSCAPE_ANALYST_PASSWORD | Another private password, at least 12 characters |
| EARTHSCAPE_VIEWER_PASSWORD | A password you can share with portfolio visitors, at least 12 characters |

8. Click Deploy. Open the generated `.vercel.app` address.
9. Sign in as `admin`, `analyst`, or `viewer` using the matching password you selected. The first login creates those accounts in PostgreSQL. No registration or Supabase Auth user creation is necessary.
10. If environment values were added after deploying, choose Redeploy so the running function receives them.

Passwords initialize accounts once. Later environment changes do not reset existing accounts. Change existing accounts in Administration; account changes invalidate their sessions. If you lose all admin access, use a trusted local recovery workflow rather than exposing a password reset endpoint.

## 5. Test the live site

- Open `/api/health` on your Vercel address. It should return `ok: true`; this checks API routing only, not database readiness.
- Log in as viewer and open Overview, Models and Data explorer.
- Filter Karachi and verify the station-specific dashboard.
- Log out and sign in as analyst. Import a CSV/JSON sample (up to 1,000 records per request).
- Send a 44 C reading and inspect the generated alert.
- Run monthly aggregation and inspect the completed job.
- Upload a PNG/TIFF smaller than 1 MB.
- Create a support ticket. Sign in as admin and resolve it.
- In Administration create an encrypted logical snapshot.
- Sign out and reopen the site to verify data persistence.

For a shareable portfolio, provide only the viewer password. Keep admin and analyst credentials private.

## Hosted features and limits

The real forecast uses linear regression and Isolation Forest. Monthly aggregation runs as a PostgreSQL request, with retained input snapshots and results. This deployment does not run HDFS/YARN, background sensor listeners or an hourly backup worker. Do not describe its processing as distributed Hadoop execution.

Portfolio limits: 5,000 observations, 1,000 import records/request, 1 MB images, 15 MB of encrypted image payloads in total, 500 tickets, 50 accounts, latest 20 jobs and latest three manual encrypted logical snapshots. Import validation rejects invalid/missing data and preserves duplicate identity handling. Login throttling is shared in PostgreSQL, not local function memory.

Image payloads and snapshots are Fernet encrypted and stored in PostgreSQL, suitable for this small demo. Bulk object storage and independent disaster recovery are outside this version. The snapshots include observations, alerts, tickets, settings and image archives, but omit login secrets and sessions. To retrieve a snapshot for recovery, privately export its payload from es_backups in the Supabase dashboard and decrypt it locally with the same Fernet key. Never run arbitrary SQL from visitor input.

The dashboard refreshes every 60 seconds. Serverless uptime/request metrics are not fabricated: use Vercel monitoring instead. The displayed database size is the whole PostgreSQL database, not only EarthScape's rows.

Supabase Free currently includes a 500 MB database and pauses projects after one week of inactivity. Vercel and Supabase have usage limits, so free access is not a promise of unlimited capacity or permanent availability. Stay on Free/Hobby and check their dashboards. No Render account is needed.

## Troubleshooting

- Homepage 404: verify Root Directory is EarthScape_Vercel, output directory is public, and public/index.html exists.
- /api/health 404: verify api/index.py and vercel.json were uploaded. Redeploy.
- Database request failed: check the Supabase project is active, SQL ran successfully, and URL/service_role key match that project. Look at Vercel logs. Do not post secrets in a screenshot.
- Login initialization error: all three account password variables must have at least 12 characters before the first login.
- Invalid credentials after a password environment edit: existing accounts keep their database passwords; edit accounts through Administration.
- Missing forecast: import enough valid temperatures across at least ten distinct dates. Anomaly detection needs twenty temperature-bearing records.
- Decryption failure: restore the original cloud Fernet key.
- Function timeouts or quota warnings: reduce imports/data volume and inspect provider usage. An always-on large Hadoop cluster is a separate deployment.

## Validation

Eleven local application integration tests passed against a real embedded PostgreSQL engine through a private REST-shaped test adapter: auth/roles/CSRF, session persistence/logout, real analytics, duplicate/invalid imports and alerts, completed aggregation, private tickets, archive/snapshot persistence, account/session invalidation, route rewriting, and measurement validation. SQL initialization and repeat execution passed. PostgreSQL denied anonymous table and function access.

This package has not been deployed to your Vercel/Supabase accounts. Provider routing, account permissions, live latency and billing eligibility require the live checks above. This is a prepared deployment package, not a claim of an already published site.

## Official references

https://vercel.com/docs/functions/runtimes/python
https://vercel.com/docs/functions/limitations
https://supabase.com/pricing
https://supabase.com/docs/guides/api/securing-your-api
