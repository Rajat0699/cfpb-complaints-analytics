-- Q5: where complaints come from, per 100K residents (2025 population for every year)
with complaints as (

    select * from {{ ref('fct_complaints') }}

),

states as (

    select * from {{ ref('dim_state') }}

),

by_state as (

    select
        state_code,
        year(date_received)                 as complaint_year,
        count(*)                            as complaints,
        count_if(is_big3_bureau)            as big3_bureau_complaints,
        count_if(is_closed)                 as closed_complaints,
        count_if(has_relief)                as complaints_with_relief
    from complaints
    where state_code is not null
    group by all

)

select
    by_state.*,
    states.state_name,
    states.state_type,
    states.census_region,
    states.population_2025,
    round(100000 * by_state.complaints / nullif(states.population_2025, 0), 1)
                                            as complaints_per_100k
from by_state
left join states
    on by_state.state_code = states.state_code