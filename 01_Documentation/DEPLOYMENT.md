# Installation and operation

## Offline Windows application
Extract the ZIP completely, then double-click START_EARTHSCAPE.bat. The embedded Python 3.12.10 runtime loads the bundled Windows wheels. It starts app.py on loopback port 8080 and opens the browser. No package installation is needed. If startup fails, runtime/launcher.log contains the specific error. Do not run directly inside a ZIP preview window. Stop with Ctrl+C in the launcher window.

## Complete Hadoop stack
Docker Desktop (Windows/Linux containers, WSL2 backend) is the only prerequisite on Windows. START_FULL_STACK.bat performs `docker compose up --build -d`, waits for readiness and opens localhost:8081. The Dockerfile downloads Apache Hadoop 3.4.1, installs Java 17/Python and starts deploy/cluster.py. The script automatically creates safe new NameNode state if absent, starts two separately configured DataNodes and YARN services, then starts the application in HDFS mode. Existing volume data is preserved on restarts. Initial build needs internet and roughly 1 GB for the Hadoop download, with additional image space. Allocate at least 6 GB to the container and follow the assignment's recommended 16 GB host RAM.

Ports: application 8081; NameNode interface 9870; YARN interface 8088. Ports are mapped only to host loopback. Never expose this lab stack directly to the public internet. Named volumes preserve application state and cluster storage. `docker compose logs -f` shows logs; `docker compose down` stops services. Do not add `--volumes` unless intentionally erasing all saved data.

Open Processing jobs, click Run processing job, and wait for Completed. The worker exports a consistent input file, uploads to HDFS, submits Hadoop Streaming with two reducers, retrieves its output and stores the summary and execution log. Pending jobs are recovered on service restart. Raw encrypted archive uploads use a durable outbox; temporary HDFS failures stay queued and appear in pipeline status. Each request can succeed locally while archive transfer is pending; the UI explicitly displays queued transfers.

The verified test ran 720 records through HDFS/YARN and produced 24 monthly station groups. docs/hadoop-execution.log and hdfs-report.txt preserve evidence. Two DataNodes run as separate processes on the same machine; deploy across multiple hosts for genuine host-level redundancy. Increase replication on a multi-host deployment and configure HDFS permissions/secure authentication appropriately.

## Recovery
The application creates hourly encrypted snapshots while running and manual snapshots through Administration. Stop the service. Preserve the database and key. Run:
`python tools/restore_backup.py runtime/backups/<snapshot>.db.enc --key runtime/secret.key --output runtime/restored.db`
For the embedded Windows runtime, replace `python` with `portable\windows\python\python.exe`.
The restore tool refuses overwrites and checks SQLite integrity. Move the old earthscape.db aside, replace it with restored.db, then restart. Keep the matching key securely; losing it makes encrypted snapshots and archives unreadable. Copy encrypted backups and keys to separately protected storage for host-failure recovery.

## Production configuration
The lab package is ready for local use and evaluation. Production adds a TLS reverse proxy with EARTHSCAPE_HTTPS=1; encrypted disks for SQLite/curated data; Kerberos and managed HDFS encryption zones; off-host backups; service monitoring; shared authentication/session infrastructure; and a scalable relational serving database. The 99% uptime in the brief is an operating target that requires measurements over time. It is not a guarantee derived from a laboratory run. This container automatically restarts on failure and exposes a health check.
