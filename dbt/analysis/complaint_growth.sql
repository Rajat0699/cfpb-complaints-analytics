--  Answers how fast are the complaints growing and how much is that from three credit bureaus.

with yearly as (
    select 
          year(complaint_month) as complaint_year,
          count(distinct complaint_month) as months_of_data,
          sum(complaints) as complaints,
          sum(iff(not is_big3_bureau, complaints, 0)) as other_complaints,
          sum(complaints) / count(distinct complaint_month) as complaints_per_month,
          sum(iff(not is_big3_bureau, complaints, 0)) / count(distinct complaint_month) as other_per_month
    from {{ref('mart_monthly_trends')}}

    group by 1
        
)
select
    complaint_year,
    months_of_data,
    complaints,
    round(complaints_per_month)                                         as complaints_per_month,
    round(100 * complaints_per_month
              / lag(complaints_per_month) over (order by complaint_year) - 100, 1)
                                                                        as growth_pct,
    round(100 * (1 - other_complaints / complaints), 1)                 as bureau_share_pct,
    other_complaints,
    round(100 * other_per_month
              / lag(other_per_month) over (order by complaint_year) - 100, 1)
                                                                        as other_growth_pct
from yearly
order by complaint_year