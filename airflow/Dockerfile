# Airflow lab image: the official Apache Airflow image plus this lab's DAGs and
# Python dependencies. Same Airflow version as the repo's root stack
# (docker-compose-airflow.yaml), so DAGs written here run there unchanged.
#
#   docker build -t fis-airflow-lab .
#   docker run --rm -p 127.0.0.1:8089:8080 fis-airflow-lab
#
# Or just `docker compose up --build` (see README.md).
FROM apache/airflow:3.3.2

# Lab defaults. Every setting maps to airflow.cfg as AIRFLOW__<SECTION>__<KEY>.
#  - LOAD_EXAMPLES=False: the UI shows only this lab's DAGs, not Apache's ~80 examples.
#  - SIMPLE_AUTH_MANAGER_ALL_ADMINS=True: no login screen, everyone is admin.
#    Fine on a laptop. Never ship an image with this set.
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False \
    AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS=True

# Install extra Python packages *at build time*, not at container start
# (_PIP_ADDITIONAL_REQUIREMENTS reinstalls on every boot). Pinning
# apache-airflow to the image's own version stops pip from silently
# upgrading or downgrading Airflow to satisfy a dependency.
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /requirements.txt

# Bake the DAGs into the image so it works with no volume mounts.
# docker-compose.yaml mounts ./dags over this for live editing.
COPY --chown=airflow:root dags/ /opt/airflow/dags/

EXPOSE 8080

# `airflow standalone` runs everything in one container: it migrates a SQLite
# metadata DB, then starts the scheduler, dag-processor, triggerer and API
# server (UI) with the LocalExecutor. Great for learning; for anything shared
# use Postgres and separate services, like the root docker-compose-airflow.yaml.
CMD ["standalone"]
