with complaints as (

    select * from {{ ref('int_complaints__enriched') }}

)

select
    -- keys (join to the dimensions)
    complaint_id,
    date_received,                                      -- dim_date.date_day
    company_name,                                       -- dim_company
    {{ product_key('product', 'sub_product') }}         as product_key,     -- dim_product
    state                                               as state_code,      -- dim_state

    -- attributes kept on the fact so most questions need no joins
    product_family,
    issue,
    sub_issue,
    submitted_via,
    company_response,
    relief_type,
    zip_code,
    date_sent_to_company,
    case
        when is_servicemember and is_older_american then 'Servicemember & older American'
        when is_servicemember                       then 'Servicemember'
        when is_older_american                      then 'Older American'
        else 'Other consumers'
    end                                                 as consumer_group,

    -- flags
    is_big3_bureau,
    is_closed,
    is_in_progress,
    is_timely_response,
    is_servicemember,
    is_older_american,
    coalesce(relief_type <> 'No relief', false)         as has_relief,
    coalesce(relief_type = 'Monetary', false)           as has_monetary_relief,

    -- measures
    days_to_company

from complaints