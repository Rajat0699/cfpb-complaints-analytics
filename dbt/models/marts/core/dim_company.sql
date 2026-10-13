with complaints as (

    select * from {{ ref('int_complaints__enriched') }}

)

select
    company_name,
    boolor_agg(is_big3_bureau)      as is_big3_bureau,
    mode(product_family)            as main_product_family,
    min(date_received)              as first_complaint_date,
    max(date_received)              as last_complaint_date,
    count(*)                        as total_complaints
from complaints
group by company_name