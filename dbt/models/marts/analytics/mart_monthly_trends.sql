-- Q1 growth, Q2 product mix, Q6 consumer groups. Counts only: rates are
-- computed in the dashboard so they stay correct at any level of grouping.
with complaints as (

    select * from {{ ref('fct_complaints') }}

)

select
    date_trunc('month', date_received)      as complaint_month,
    product_family,
    is_big3_bureau,
    consumer_group,

    count(*)                                as complaints,
    count_if(is_timely_response)            as timely_responses,
    count_if(is_closed)                     as closed_complaints,
    count_if(has_relief)                    as complaints_with_relief,
    count_if(has_monetary_relief)           as complaints_with_monetary_relief,
    count_if(is_in_progress)                as complaints_in_progress

from complaints
group by all