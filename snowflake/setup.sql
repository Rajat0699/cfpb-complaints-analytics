-- Phase 0 - one-time Snowflake setup. Run the whole file in a Snowsight
-- worksheet as ACCOUNTADMIN. Safe to re-run (everything is IF NOT EXISTS).
--
-- Creates:
--   CFPB_WH            XS warehouse, auto-suspends after 60s idle
--   CFPB.RAW           landing schema, owned by the loader (Python)
--   CFPB.ANALYTICS     dbt Cloud production schema, owned by the transformer (dbt)
--   CFPB_LOADER        role: writes RAW
--   CFPB_TRANSFORMER   role: reads RAW, builds everything else
--   CFPB_LOADER_SVC    service user for extract_load/load_snowflake.py
--   CFPB_DBT_SVC       service user for dbt Cloud
--   RAW.COMPLAINTS, RAW.LOAD_LOG, RAW.COMPLAINTS_STAGE
--
-- Service users log in with key pairs (Snowflake blocks password-only logins).
-- After running this file, run snowflake/make_keys.sh and paste the two
-- ALTER USER ... SET RSA_PUBLIC_KEY statements it prints.

USE ROLE ACCOUNTADMIN;
SET my_user = CURRENT_USER();

-- Compute -------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS CFPB_WH
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

-- Roles ---------------------------------------------------------------------
CREATE ROLE IF NOT EXISTS CFPB_LOADER;
CREATE ROLE IF NOT EXISTS CFPB_TRANSFORMER;
GRANT ROLE CFPB_LOADER      TO ROLE SYSADMIN;
GRANT ROLE CFPB_TRANSFORMER TO ROLE SYSADMIN;
GRANT ROLE CFPB_LOADER      TO USER IDENTIFIER($my_user);  -- so you can query as either role
GRANT ROLE CFPB_TRANSFORMER TO USER IDENTIFIER($my_user);

GRANT USAGE ON WAREHOUSE CFPB_WH TO ROLE CFPB_LOADER;
GRANT USAGE ON WAREHOUSE CFPB_WH TO ROLE CFPB_TRANSFORMER;

-- Database + schemas ----------------------------------------------------------
CREATE DATABASE IF NOT EXISTS CFPB;
CREATE SCHEMA IF NOT EXISTS CFPB.RAW;
CREATE SCHEMA IF NOT EXISTS CFPB.ANALYTICS;

GRANT USAGE ON DATABASE CFPB TO ROLE CFPB_LOADER;
GRANT USAGE ON DATABASE CFPB TO ROLE CFPB_TRANSFORMER;
GRANT CREATE SCHEMA ON DATABASE CFPB TO ROLE CFPB_TRANSFORMER;  -- dbt Cloud dev schemas (dbt_<name>)

GRANT OWNERSHIP ON SCHEMA CFPB.RAW       TO ROLE CFPB_LOADER      COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA CFPB.ANALYTICS TO ROLE CFPB_TRANSFORMER COPY CURRENT GRANTS;

-- dbt reads RAW (including tables created later)
GRANT USAGE ON SCHEMA CFPB.RAW TO ROLE CFPB_TRANSFORMER;
GRANT SELECT ON ALL TABLES IN SCHEMA CFPB.RAW TO ROLE CFPB_TRANSFORMER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA CFPB.RAW TO ROLE CFPB_TRANSFORMER;

-- Service users (keys added by make_keys.sh output) -----------------------------
CREATE USER IF NOT EXISTS CFPB_LOADER_SVC
    TYPE = SERVICE
    DEFAULT_ROLE = CFPB_LOADER
    DEFAULT_WAREHOUSE = CFPB_WH
    DEFAULT_NAMESPACE = CFPB.RAW;
GRANT ROLE CFPB_LOADER TO USER CFPB_LOADER_SVC;

CREATE USER IF NOT EXISTS CFPB_DBT_SVC
    TYPE = SERVICE
    DEFAULT_ROLE = CFPB_TRANSFORMER
    DEFAULT_WAREHOUSE = CFPB_WH
    DEFAULT_NAMESPACE = CFPB.ANALYTICS;
GRANT ROLE CFPB_TRANSFORMER TO USER CFPB_DBT_SVC;

-- RAW objects, created as the loader so it owns them ----------------------------
USE ROLE CFPB_LOADER;
USE WAREHOUSE CFPB_WH;
USE SCHEMA CFPB.RAW;

CREATE FILE FORMAT IF NOT EXISTS PARQUET_FMT TYPE = PARQUET;

-- Internal stage: load_snowflake.py PUTs Parquet files here, COPYs, then removes them
CREATE STAGE IF NOT EXISTS COMPLAINTS_STAGE FILE_FORMAT = PARQUET_FMT;

-- One row per complaint_id, as published (all VARCHAR; typing happens in dbt).
-- Column names match extract_load/schema.py.
CREATE TABLE IF NOT EXISTS COMPLAINTS (
    date_received                 VARCHAR,
    product                       VARCHAR,
    sub_product                   VARCHAR,
    issue                         VARCHAR,
    sub_issue                     VARCHAR,
    company_public_response       VARCHAR,
    company                       VARCHAR,
    state                         VARCHAR,
    zip_code                      VARCHAR,
    tags                          VARCHAR,
    submitted_via                 VARCHAR,
    date_sent_to_company          VARCHAR,
    company_response_to_consumer  VARCHAR,
    timely_response               VARCHAR,
    complaint_id                  VARCHAR,
    _load_source                  VARCHAR,       -- 'bulk' or 'api'
    _source_file                  VARCHAR,
    _loaded_at                    TIMESTAMP_TZ
);

CREATE TABLE IF NOT EXISTS LOAD_LOG (
    source_file    VARCHAR,
    load_source    VARCHAR,
    file_mtime     TIMESTAMP_TZ,
    rows_in_file   NUMBER,
    rows_inserted  NUMBER,
    rows_updated   NUMBER,
    loaded_at      TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
);
