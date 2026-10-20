-- Optional Impala query layer on the Hadoop job TSV output.
-- Replace LOCATION with the completed job output directory.
CREATE EXTERNAL TABLE IF NOT EXISTS earthscape_monthly (
 station_month STRING, mean_temperature DOUBLE, observation_count INT
) ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE LOCATION '/earthscape/analytics/job-1';
SELECT * FROM earthscape_monthly ORDER BY station_month;
