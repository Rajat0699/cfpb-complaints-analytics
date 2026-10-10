#!/usr/bin/env bash
# Generates RSA key pairs for the two Snowflake service users and prints the
# ALTER USER statements to paste into Snowsight (after running setup.sql).
#
#   ~/.snowflake/cfpb_loader_key.p8  -> SNOWFLAKE_PRIVATE_KEY_PATH in .env
#   ~/.snowflake/cfpb_dbt_key.p8     -> paste into dbt Cloud's Snowflake connection
#
# Private keys are unencrypted and readable only by you; never commit them.
# Existing keys are kept, so re-running just re-prints the SQL.
set -euo pipefail
dir="$HOME/.snowflake"
mkdir -p "$dir" && chmod 700 "$dir"

for name in loader dbt; do
    key="$dir/cfpb_${name}_key.p8"
    if [ ! -f "$key" ]; then
        openssl genrsa 2048 2>/dev/null | openssl pkcs8 -topk8 -inform PEM -nocrypt -out "$key"
        chmod 600 "$key"
    fi
done

pub() { openssl rsa -in "$1" -pubout 2>/dev/null | grep -v -- '-----' | tr -d '\n'; }

echo "-- Paste into Snowsight (as ACCOUNTADMIN):"
echo "ALTER USER CFPB_LOADER_SVC SET RSA_PUBLIC_KEY = '$(pub "$dir/cfpb_loader_key.p8")';"
echo "ALTER USER CFPB_DBT_SVC    SET RSA_PUBLIC_KEY = '$(pub "$dir/cfpb_dbt_key.p8")';"
