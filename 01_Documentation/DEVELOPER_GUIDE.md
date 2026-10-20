# Developer guide

## Architecture
app.py serves the responsive frontend and JSON API. SQLite is the local serving store. storage_pipeline.py manages durable HDFS archive transfers and processing jobs. deploy/cluster.py configures/starts a complete Hadoop 3.4.1 laboratory with two DataNodes and YARN; the Docker entrypoint runs this script. launch.py opens the offline desktop application through the bundled Windows Python 3.12.10 runtime.

## Tables
users(name,salt,hash,role); observations(id,day,station,temperature,rainfall,co2,source,timestamp), unique(timestamp,station,source); alerts(id,created,station,message,ack); tickets(id,created,owner,subject,body,status); settings(key,value); audit(id,created,actor,action); assets(id,created,name,path,kind); jobs(id,created,status,output,error). Station/date and open-alert indexes accelerate common queries. Startup migrates the earlier day-only schema without discarding records.

## API
POST /api/login {name,password}; GET /api/me returns name/role/csrf; POST /api/logout. GET /api/analytics?station= returns current statistics/models; GET /api/status returns basic process metrics. POST /api/ingest accepts {rows:[...]} or {csv:"..."}. GET /api/assets; POST /api/asset {name,data:base64} verifies PNG/TIFF and stores encrypted. GET /api/alerts; POST /api/ack {id}. POST /api/ticket {subject,body}; GET /api/tickets; POST /api/ticket-status {id,status}. GET /api/jobs; POST /api/process {} enqueues a job; GET /api/pipeline reports transfer queue. Admin-only: POST /api/settings {threshold}, POST /api/backup {}, GET /api/audit, GET /api/users, POST /api/user {name,password,role}.

Every authenticated mutation requires X-CSRF-Token. Administrator/analyst roles can import, process, archive and acknowledge. Viewers read and create their own support tickets. Administrators additionally manage users/policy/backups/audits/ticket status. Account password/role changes invalidate that user's sessions; the last administrator cannot be demoted.

## Models
Daily mean temperatures are sorted in time. LinearRegression trains on the first 80% of dates and evaluates MAE on the last 20%, then refits for a fourteen-day forecast. IsolationForest uses temperature/rain/CO2, median imputation, eighty trees, contamination .04 and seed 42. Correlation uses finite paired measurements with nonzero variance. At least ten dates and twenty temperature-bearing observations are required for forecasts and anomaly detection respectively. A fifteen-second cache reduces repeated training; ingestion invalidates it. Latest model metadata/forecast are saved under runtime/models. These are educational baselines.

## Hadoop worker
Raw encrypted monthly JSON files and satellite assets enter a durable outbox. The background worker uploads to HDFS and retries temporary failures, reporting pending/error counts. Jobs snapshot the serving database to NDJSON, stage it in HDFS, invoke Hadoop Streaming with two reducers and retrieve station/month mean-temperature/count TSV results. Output, inputs and execution logs are retained per job. A job interrupted during server restart returns to Queued. Outputs use a unique job directory. On restart, the supervisor waits for NameNode safe mode to end before starting the application.

## Security and recovery
Salted PBKDF2-HMAC-SHA256 at 310,000 iterations; one-hour random-token sessions; HttpOnly/SameSite=Strict cookies; optional Secure cookies; CSRF; role checks; parameterized SQL; escaped frontend values; ten-failure/five-minute IP sign-in throttle; payload bound of 10 MB; input validation. Fernet encrypts raw/asset archives and database snapshots. SQLite and curated HDFS records remain in plaintext on the local demonstration's disk, so production requires encrypted disks/HDFS zones, managed keys, TLS and protected serving-database access. Each backup uses a unique filename and a serialization lock; restore verifies database integrity.

## Validation
Run python -m unittest discover -s tests -v. HTTP checks are in tests/integration.py. Executed test results, browser checks, Hadoop/YARN execution log, HDFS report and screenshots are included in docs. The supplied Windows runtime was assembled from official Windows x64 distributions; application logic was verified on Linux. No long-term uptime, production load benchmark or legal-compliance certification is implied. Docker recipe uses the same supervisor successfully exercised directly in the laboratory; Docker Desktop itself is not installed in the build environment.
