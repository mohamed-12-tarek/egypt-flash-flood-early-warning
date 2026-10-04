FROM apache/airflow:2.10.2-python3.11

USER root
RUN apt-get update && apt-get install -y curl gnupg unixodbc-dev \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
 && mkdir /opt/uv-venv && chown airflow /opt/uv-venv

USER airflow
RUN pip install --no-cache-dir uv