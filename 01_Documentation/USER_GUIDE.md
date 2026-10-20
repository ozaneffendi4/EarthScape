# User guide
Open START_EARTHSCAPE.bat, or use START_FULL_STACK.bat for Hadoop mode. Sign in with the accounts in README.md.

Overview displays observation count, selected-station mean temperature, model anomaly count and agency-wide open alerts. Change the station selector to filter analysis. Data explorer displays/export the latest 100 matching records. Models shows a 14-day trend forecast, final-20% time-ordered test MAE, correlation and possible anomalies.

Ingestion accepts CSV or a JSON array. Fields: day (ISO date/time), station, temperature (°C), rainfall (mm), co2 (ppm), source (weather/sensor/satellite). An optional timestamp overrides day and is normalized to UTC. Blank numeric values are allowed if at least one measurement is present. Valid rows are accepted even when other rows fail; rejected row numbers are shown. Repeated timestamp/station/source rows are skipped. Different timestamps from one station are retained.

Sensor stream sends a reading at the current time. Repeat sends preserve each timestamp. The command-line sensor_stream.py feeder can push readings continuously. Raw records enter the same ingestion pipeline as historical files. PNG/TIFF satellite uploads are verified and archived encrypted; uploaded images are listed under Archived satellite assets. They are not used for image-derived weather prediction.

Processing jobs submits station/month averaging. Local mode runs mapper/reducer locally; full-stack mode executes on HDFS/YARN. Each completed job displays its engine, input count, output count and summary. The archive transfer count displays pending HDFS synchronization.

Alerts appear automatically above the temperature threshold and refresh every ten seconds. Admins/analysts acknowledge them. Threshold changes affect future readings. Support tickets are visible to their owner and administrators, who can resolve them. Administration lets admins set thresholds, create backups, create/update accounts, inspect metrics and review audits. Viewer accounts cannot ingest, process or alter policy.

FAQ: If the browser does not open automatically, go to http://127.0.0.1:8080. If port 8080 is already used by this application, the launcher opens the existing instance. If an import reports duplicates, the same identities already exist. If forecast values are absent, provide at least ten dates with temperatures. If a Hadoop job remains queued, check Docker logs and pipeline status. Sessions expire after one hour; sign in again. The website is self-contained and does not use third-party CDN scripts.
