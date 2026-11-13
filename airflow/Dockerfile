# The Airflow image for this repo: the official apache/airflow image plus the
# Python packages our DAGs import. docker-compose-airflow.yaml (repo root) builds
# it and runs it for every Airflow container.
#
# DAGs are NOT baked in: the compose file mounts the repo's dags/ folder, so you
# edit DAGs without rebuilding. Rebuild only when requirements.txt (or this file)
# changes:  docker compose -f docker-compose-airflow.yaml up -d --build
FROM apache/airflow:3.3.2

# System (apt) packages, if a DAG ever needs one. apt must run as root, and pip
# below must run as the airflow user, so switch back afterwards:
#
# USER root
# RUN apt-get update \
#  && apt-get install -y --no-install-recommends <package> \
#  && apt-get clean && rm -rf /var/lib/apt/lists/*
# USER airflow

# Installed at build time, once, rather than on every container start
# (which is what _PIP_ADDITIONAL_REQUIREMENTS does). Pinning apache-airflow to
# the image's own version makes the build fail, instead of silently upgrading
# or downgrading Airflow, if a package needs a different version of it.
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /requirements.txt
