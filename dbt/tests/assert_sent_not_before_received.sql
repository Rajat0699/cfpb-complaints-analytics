-- ~7k historical complaints have date_sent_to_company before date_received
-- (a source data quirk), so this warns instead of failing the build.
{{ config(severity='warn') }}

select complaint_id, date_received, date_sent_to_company
from {{ ref('stg_cfpb__complaints') }}
where date_sent_to_company < date_received
