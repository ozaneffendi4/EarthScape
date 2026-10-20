# EarthScape Climate Agency — ready-to-use project

## Open the application on Windows 10/11 (64-bit)
1. Extract the complete ZIP to a normal folder.
2. Double-click **START_EARTHSCAPE.bat**.
3. The browser opens at http://127.0.0.1:8080. Keep the application window open while working.

Python and every application dependency are bundled. This mode does not require Python installation or an internet connection. Windows may show a downloaded-file security prompt; review the source if required by your computer's policy.

| Username | Password | Access |
|---|---|---|
| admin | EarthDemo!2026 | All features, accounts, policy, backups and audits |
| analyst | AnalystDemo!2026 | Import, process, analysis, alerts and own support tickets |
| viewer | ViewerDemo!2026 | Read analysis and create own support tickets |

To run the full Hadoop stack, install/start Docker Desktop and double-click **START_FULL_STACK.bat**. It builds and starts the application, NameNode, two DataNodes, ResourceManager and NodeManager automatically. First build requires internet and downloads Hadoop/Java/Python dependencies. Open http://localhost:8081. STOP_FULL_STACK.bat stops services while retaining data. On Linux/macOS, use `docker compose up --build -d` for the same stack or `bash start.sh` for the Python app.

## Included features
Role-based sign-in; CSV/JSON imports; timestamped sensor ingestion; encrypted satellite PNG/TIFF archive; station filtering; observation export; 14-day forecasts; Isolation Forest anomalies; correlations; monthly processing jobs; threshold alerts; support ticket resolution; user accounts; audit trail; health metrics; encrypted manual/hourly backups; recovery tool.

## Files
- app.py and storage_pipeline.py: application/API and durable Hadoop processing worker.
- static/: interactive responsive website.
- portable/windows/python/: embedded Python and complete Windows dependencies.
- data/: 720 reproducible synthetic observations, invalid-data fixture and satellite PNG/TIFF fixtures.
- deploy/, Dockerfile and compose.yaml: automatic Hadoop stack configuration.
- hadoop/: mapper/reducer, configs and optional Impala DDL.
- EarthScape_Analysis.ipynb and tools/climate_analysis.R: notebook/R analysis.
- docs/: project report in Word/PDF, diagrams, screenshots, website video, test results and operating guides.
- runtime/ and backups/: initialized database, encryption key, archives and database snapshot.
- original-forms/: the original supplied administrative templates.

## Quick evaluation
Sign in as admin. Review Overview, select Karachi and open Models. Upload sample.csv to demonstrate duplicate detection. Send a new 44°C sensor reading, inspect and acknowledge its alert. Archive sample_satellite.png. Run a processing job and inspect its monthly summary. Submit/resolve a support ticket. Create a backup and, if wanted, a viewer account. Sign in as viewer to confirm write restrictions.

## Assumptions
Seed observations and satellite fixtures are synthetic. Numerical units are °C, mm and ppm. Readings use ISO timestamps in UTC; duplicate timestamp/station/source identities are skipped. Imagery is archived, not interpreted as climate measurements. The models are educational baselines and correlations do not establish causation. Local mode runs the same mapper/reducer logic on this computer; the Docker mode runs genuine HDFS/YARN MapReduce. The lab cluster has two DataNode processes on one host, so it demonstrates replication but does not protect against total host failure. Production deployment requires managed keys, TLS, database access protection, independent backups, an environmental metadata policy and measured service-level objectives.

## Submission
The report and technical package are included. Add your actual student/enrollment/batch/group/centre details if your institute requires them and rename the ZIP with the batch and group. Original status/feedback templates are included; use actual dates and personal feedback. The supplied instructions permit only one final upload per group.
