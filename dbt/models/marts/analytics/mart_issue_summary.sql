-- Q4: what consumers are complaining about
with complaints as (

    select * from {{ ref('fct_complaints') }}

)

select
    year(date_received)                     as complaint_year,
    product_family,
    issue,
    is_big3_bureau,

    count(*)                                as complaints,
    count_if(is_closed)                     as closed_complaints,
    count_if(has_relief)                    as complaints_with_relief,
    count_if(has_monetary_relief)           as complaints_with_monetary_relief

from complaints
group by all