# Validation

11 application integration tests passed using an embedded PostgreSQL engine through a private REST-shaped test adapter. SQL schema creation, re-running setup, real seed analytics, duplicate/invalid ingestion, alerts, monthly aggregation, shared sessions, logout, role/CSRF enforcement, private tickets, archives, snapshots and account invalidation were checked. Anonymous table and RPC access was denied. Three included validation/analytics tests also passed. JavaScript passed a syntax check.

Live deployment to Vercel/Supabase and browser interaction have not been verified in this environment. Follow DEPLOY_GUIDE.md to perform those checks after configuring the accounts.
