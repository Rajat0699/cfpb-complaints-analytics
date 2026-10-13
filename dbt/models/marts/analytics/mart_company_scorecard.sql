-- Q3: which companies resolve complaints best and worst
with complaints as (

    select * from {{ ref('fct_complaints') }}

)

select
    company_name,
    year(date_received)                     as complaint_year,
    product_family,
    is_big3_bureau,

    count(*)                                as complaints,
    count_if(is_timely_response)            as timely_responses,
    count_if(is_closed)                     as closed_complaints,
    count_if(has_relief)                    as complaints_with_relief,
    count_if(has_monetary_relief)           as complaints_with_monetary_relief,
    count_if(is_in_progress)                as complaints_in_progress

from complaints
group by all