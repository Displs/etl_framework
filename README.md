# etl-framework

Фреймворк автоматизации создания ETL-процессов корпоративного хранилища
данных на основе активных метаданных. Принимает декларативные YAML-спецификации
сущностей хранилища и формирует:

* PySpark-скрипты для четырёх поддерживаемых паттернов загрузки —
  Full / Incremental / SCD Type 1 / SCD Type 2;
* DAG'и Apache Airflow по одному на слой хранилища;
* DDL для внешних витрин Greenplum / ClickHouse;
* граф происхождения данных уровня колонок — публикуется в OpenMetadata
  или экспортируется в виде OpenLineage-событий.

## Структура репозитория

```
src/etl_framework/
    models/         Pydantic v2-модель EntitySpec (активные метаданные)
    repository/    Файловый YAML-репозиторий и кросс-сущностный валидатор
    discovery/     Reflection PostgreSQL → черновая EntitySpec
    codegen/       Jinja2-шаблоны и движок генерации
    lineage/       Построитель lineage + публикация в OpenMetadata + OpenLineage
    security/      Разрешение ссылок на секреты и журнал аудита
    cli/           Команда `etlf` (Typer)
examples/retail/   Пять эталонных EntitySpec, покрывающих все 4 стратегии загрузки
docker/            Seed-данные для локального PostgreSQL-источника
docker-compose.yml Локальный стек: Postgres + MinIO + Spark + Airflow + OpenMetadata
tests/             Pytest-сюита (48 тестов; работает без docker)
```

## Быстрый старт

```bash
pip install -e ".[dev]"          # установка с dev-зависимостями
pytest -q                        # 48 тестов, ~1 сек.

# Валидация поставляемого ритейл-репозитория
etlf validate examples/retail

# Генерация PySpark-скриптов и DAG'ов Airflow в ./build
etlf generate examples/retail -o build --sql-sinks

# Экспорт событий OpenLineage
etlf lineage export examples/retail -o build/openlineage.json
```

## Создание новой сущности с нуля

```bash
# Discovery схемы из живого PostgreSQL и формирование черновой спецификации
OLTP_USER=oltp OLTP_PASSWORD=oltp \
  etlf discover examples/retail \
    --source postgres_oltp --schema public --table products \
    --layer stg \
    -o examples/retail/entities/stg_products.yaml

# Дальше — уточнить логику в YAML (стратегия загрузки, transform'ы,
# расписание) и зафиксировать в git
etlf validate examples/retail
etlf generate examples/retail -o build
```

## Локальный сквозной стенд

```bash
docker compose up -d postgres-oltp minio minio-init
docker compose up -d spark-master spark-worker
docker compose up -d airflow-postgres airflow-init airflow-webserver airflow-scheduler
# OpenMetadata тяжёлый, поднимается только при необходимости:
docker compose up -d openmetadata-mysql elasticsearch openmetadata
```

Сгенерированные DAG'и подмонтированы в Airflow через bind-mount, поэтому
повторный `etlf generate` приводит к их появлению в планировщике в течение
минуты. PySpark-приложения уходят на Spark-мастер через `SparkSubmitOperator`;
каталог Iceberg/S3 живёт в MinIO в бакете `warehouse`.

## Формат спецификации

Минимальный пример:

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

Развёрнутые примеры для SCD1, SCD2, инкрементальной загрузки и витрины во
внешний приёмник — см. `examples/retail/entities/`.

## Ссылки на секреты

Пароли подключений и прочие чувствительные поля задаются *ссылками на
секреты*, а не литералами:

* `env:NAME` — читать из переменной окружения процесса;
* `file:/path` — читать из однострочного файла;
* всё остальное — литерал (годится только для локальных демо).

Ссылка переносится в сгенерированный PySpark-код без изменений, секрет
разрешается во время выполнения задачи. В итоге ни `git diff`, ни реестр
артефактов никогда не видят литерального значения секрета.

## Состав поставки

* `pyproject.toml` — пакет `etl-framework` с extras `dev`, `openmetadata`, `spark`;
* CLI: `etlf validate|generate|discover|lineage export|lineage publish`;
* модель активных метаданных на Pydantic v2 со строгой валидацией;
* шаблоны кодогенерации на Jinja2 — расширяются добавлением одного файла;
* модули discovery, lineage, security, audit;
* docker-compose-стек локального окружения;
* pytest с покрытием всех компонентов.
