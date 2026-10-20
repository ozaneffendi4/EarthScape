# EarthScape — Vercel and Supabase edition

Read **DEPLOY_GUIDE.md** for the complete upload and setup steps.

- Vercel hosts the existing dashboard plus a Python API.
- Supabase PostgreSQL persists measurements, hashed sessions, accounts, alerts, support, job snapshots and encrypted archives.
- Real scikit-learn regression and Isolation Forest analytics remain active.
- SQL monthly aggregation replaces background Hadoop execution in this hosted edition.
- No Render account, local database files or bundled Windows runtime are required for this deployment.

Add this folder separately to the existing GitHub repository. Set the Vercel Root Directory to **EarthScape_Vercel**. Run **supabase_setup.sql** in a new Supabase project's SQL Editor and configure the six server-side environment variables from the guide.

Never commit real credentials. Share only the viewer demo account. Original local/Hadoop project files remain separate.
