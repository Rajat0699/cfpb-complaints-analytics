-- One day of slack: API dates are UTC, so "today" can already be tomorrow there.
select complaint_id, date_received
from {{ ref('stg_cfpb__complaints') }}
where date_received > dateadd(day, 1, current_date())
