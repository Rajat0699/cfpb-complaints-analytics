-- leaving out the three credit bureaus, which product generate complaints, and how the mix changed between 2019 and 2025.

-- Q2: Leaving out the three credit bureaus, which products generate complaints,
--     and how has the mix changed between 2019 and 2025?
with by_family as (
    select 
          year(complaint_month) as complaint_year,
          product_family,
          sum(complaints) as complaints

        from {{ref('mart_monthly_trends')}}
        where not is_big3_bureau
         and year(complaint_month) in (2019,2025)
        group by all
    
),

with_share as (

    select
        *,
        ratio_to_report(complaints) over (partition by complaint_year)  as share_of_year
    from by_family

)

select
    product_family,
    sum(iff(complaint_year = 2019, complaints, 0))                      as complaints_2019,
    sum(iff(complaint_year = 2025, complaints, 0))                      as complaints_2025,
    round(complaints_2025 / nullif(complaints_2019, 0), 1)              as growth_multiple,
    round(100 * max(iff(complaint_year = 2019, share_of_year, null)), 1) as share_2019_pct,
    round(100 * max(iff(complaint_year = 2025, share_of_year, null)), 1) as share_2025_pct
from with_share
group by product_family
order by complaints_2025 desc