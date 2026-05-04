# etl-framework

Active-metadata-driven framework for ETL automation in Lakehouse-style
corporate data warehouses. Reads declarative YAML specs of warehouse entities
and produces:

* PySpark scripts for the four supported load patterns
  (Full / Incremental / SCD Type 1 / SCD Type 2);
* per-layer Apache Airflow DAGs;
* optional DDL for downstream Greenplum / ClickHouse marts;
* column-level data lineage published to OpenMetadata or exported as
  OpenLineage events.

The framework is the implementation companion of the master's thesis
"Разработка фреймворка автоматизации создания ETL-процессов на основе
активных метаданных корпоративного хранилища данных" (РТУ МИРЭА, ИКМО-02-24).

## Layout

```
src/etl_framework/
    models/         Pydantic v2 schema of an EntitySpec (active metadata)
    repository/     Filesystem-backed YAML repository + cross-entity validator
    discovery/      Postgres reflection that emits draft EntitySpecs
    codegen/        Jinja2 templates and the generation engine
    lineage/        Lineage builder + OpenMetadata publisher + OpenLineage exporter
    security/       Secret-reference resolution and audit log
    cli/            `etlf` CLI entry point (Typer)
examples/retail/    Five reference EntitySpecs covering all four load strategies
docker/             Postgres seed for the local OLTP source
docker-compose.yml  Local stack: Postgres + MinIO + Spark + Airflow + OpenMetadata
tests/              Pytest suite (48 tests; runs without docker)
```

## Quickstart

```bash
pip install -e ".[dev]"          # install with test/lint deps
pytest -q                        # 48 tests, ~1s

# Validate the bundled retail repository
etlf validate examples/retail

# Generate PySpark + Airflow DAGs into ./build
etlf generate examples/retail -o build --sql-sinks

# Export OpenLineage events
etlf lineage export examples/retail -o build/openlineage.json
```

## Generating an entity from scratch

```bash
# Discover schema from a live Postgres instance and write a draft spec
OLTP_USER=oltp OLTP_PASSWORD=oltp \
  etlf discover examples/retail \
    --source postgres_oltp --schema public --table products \
    --layer stg \
    -o examples/retail/entities/stg_products.yaml

# Then enrich the draft (load strategy, transforms, schedule) and commit it
etlf validate examples/retail
etlf generate examples/retail -o build
```

## Local end-to-end stack

```bash
docker compose up -d postgres-oltp minio minio-init
docker compose up -d spark-master spark-worker
docker compose up -d airflow-postgres airflow-init airflow-webserver airflow-scheduler
# OpenMetadata is heavy — start only when needed:
docker compose up -d openmetadata-mysql elasticsearch openmetadata
```

Generated DAGs are bind-mounted into Airflow, so re-running `etlf generate`
makes them appear in the scheduler within a minute. PySpark applications run
on the Spark master via `SparkSubmitOperator`; the Iceberg/S3 catalog lives in
MinIO under the `warehouse` bucket.

## Spec format

A minimum example:

```yaml
apiVersion: etlf/v1
kind: Entity
metadata:
  name: stg_clients
  layer: stg
source:
  ref: postgres_oltp.public.clients
target:
  catalog: warehouse
  schema: stg
  table: clients
  format: iceberg
load:
  strategy: full
mapping:
  - target: client_id
    type: BIGINT
    source: id
    pk: true
  - target: email
    type: VARCHAR(160)
    source: email
    transform: "lower(trim($))"
schedule:
  cron: "@hourly"
```

See `examples/retail/entities/` for SCD1, SCD2, incremental, and downstream
mart variants.

## Secret references

Connection passwords and similar sensitive fields use *secret references*,
never literal values:

* `env:NAME` — read from process environment
* `file:/path` — read from a single-line file
* anything else — treated as a literal (useful for local demos only)

References travel into generated PySpark code unchanged; resolution happens
at job runtime, so `git diff` and the artifact registry never see secrets.
