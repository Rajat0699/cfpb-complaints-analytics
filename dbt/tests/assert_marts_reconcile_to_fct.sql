-- Every summary mart must add back up to the fact table.
-- Returns one row per mart whose total doesn't match (the test passes with zero rows).
with fct as (

    select
        count(*)                            as total,
        count_if(state_code is not null)    as total_with_state
    from {{ ref('fct_complaints') }}

),

marts as (

    select 'mart_monthly_trends' as mart, sum(complaints) as mart_total from {{ ref('mart_monthly_trends') }}
    union all
    select 'mart_company_scorecard', sum(complaints) from {{ ref('mart_company_scorecard') }}
    union all
    select 'mart_issue_summary', sum(complaints) from {{ ref('mart_issue_summary') }}
    union all
    select 'mart_state_summary', sum(complaints) from {{ ref('mart_state_summary') }}

)

select
    marts.mart,
    marts.mart_total,
    iff(marts.mart = 'mart_state_summary', fct.total_with_state, fct.total) as expected_total
from marts
cross join fct
where marts.mart_total <> iff(marts.mart = 'mart_state_summary', fct.total_with_state, fct.total)