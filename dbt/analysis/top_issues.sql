-- what are people actually complainng about, top 3 issues per product family in 2025
-- Q4: What are people actually complaining about? Top 3 issues per product family in 2025.
with issues as (

    select
        product_family,
        issue,
        sum(complaints)                 as complaints,
        sum(closed_complaints)          as closed_complaints,
        sum(complaints_with_relief)     as complaints_with_relief
    from {{ ref('mart_issue_summary') }}
    where complaint_year = 2025
    group by all

)

select
    product_family,
    row_number() over (partition by product_family order by complaints desc)   as issue_rank,
    issue,
    complaints,
    round(100 * ratio_to_report(complaints) over (partition by product_family), 1)
                                                                                as pct_of_family,
    round(100 * div0(complaints_with_relief, closed_complaints), 1)            as relief_rate_pct
from issues
qualify issue_rank <= 3
order by sum(complaints) over (partition by product_family) desc, issue_rank