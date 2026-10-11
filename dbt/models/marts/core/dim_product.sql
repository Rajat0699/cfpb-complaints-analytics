with complaints as (

    select * from {{ ref('int_complaints__enriched') }}

)

select
    {{ product_key('product', 'sub_product') }}   as product_key,
    product_family,
    product,
    sub_product,
    min(date_received)                            as first_complaint_date,
    max(date_received)                            as last_complaint_date,
    count(*)                                      as total_complaints
from complaints
group by all