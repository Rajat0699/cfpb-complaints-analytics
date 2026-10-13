-- Complaints per year and the share answered on time
select
    year(date_received)                                  as complaint_year,
    count(*)                                             as complaints,
    round(100 * avg(iff(is_timely_response, 1, 0)), 1)   as timely_response_Rate
from {{ ref('stg_cfpb__complaints') }}
group by 1
order by 1