#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python tools/export_hadoop.py
hdfs dfs -mkdir -p /earthscape/curated
hdfs dfs -put -f data/observations.ndjson /earthscape/curated/observations.ndjson
mapred streaming -files hadoop/mapper.py,hadoop/reducer.py -input /earthscape/curated/observations.ndjson -output "/earthscape/analytics/monthly-$(date +%s)" -mapper 'python3 mapper.py' -reducer 'python3 reducer.py'
