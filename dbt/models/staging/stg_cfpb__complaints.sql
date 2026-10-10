with source as (

    select * from {{ source('cfpb', 'complaints') }}

),

cleaned as (

    select
        complaint_id::number                                as complaint_id,

        -- bulk file has YYYY-MM-DD, API has ISO timestamps: keep the date part
        try_to_date(left(date_received, 10))                as date_received,
        try_to_date(left(date_sent_to_company, 10))         as date_sent_to_company,

        -- the source mixes real nulls with the literal string 'None'
        product,
        nullif(sub_product, 'None')                         as sub_product,
        issue,
        nullif(sub_issue, 'None')                           as sub_issue,

        company                                             as company_name,
        nullif(state, 'None')                               as state,
        nullif(zip_code, 'None')                            as zip_code,
        submitted_via,

        nullif(tags, 'None')                                as tags,
        coalesce(tags ilike '%Servicemember%', false)       as is_servicemember,
        coalesce(tags ilike '%Older American%', false)      as is_older_american,

        company_response_to_consumer                        as company_response,
        nullif(company_public_response, 'None')             as company_public_response,
        timely_response = 'Yes'                             as is_timely_response,

        _load_source,
        _loaded_at

    from source

)

select * from cleaned
