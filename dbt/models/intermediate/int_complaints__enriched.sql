with complaints as (

    select * from {{ ref('stg_cfpb__complaints') }}

),

product_mapping as (

    select * from {{ ref('product_mapping') }}

),

enriched as (

    select
        complaints.*,

        -- stable product family across the 2017 and 2023 renames
        product_mapping.product_family,

        -- the three national credit bureaus (~86% of complaints since 2024)
        complaints.company_name in (
            'EQUIFAX, INC.',
            'Experian Information Solutions Inc.',
            'TRANSUNION INTERMEDIATE HOLDINGS, INC.'
        )                                                       as is_big3_bureau,

        complaints.company_response like 'Closed%'              as is_closed,
        complaints.company_response = 'In progress'             as is_in_progress,

        -- what the consumer actually got; null while still open
        case complaints.company_response
            when 'Closed with monetary relief'      then 'Monetary'
            when 'Closed with non-monetary relief'  then 'Non-monetary'
            when 'Closed with relief'               then 'Relief (type not recorded)'
            when 'Closed with explanation'          then 'No relief'
            when 'Closed without relief'            then 'No relief'
            when 'Closed'                           then 'No relief'
        end                                                     as relief_type,

        datediff(day, complaints.date_received, complaints.date_sent_to_company)
                                                                as days_to_company

    from complaints
    left join product_mapping
        on complaints.product = product_mapping.product

)

select * from enriched