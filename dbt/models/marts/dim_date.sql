-- One row per calendar day from the first complaint (Dec 2011) to today
with day_numbers as (

    select row_number() over (order by seq4()) - 1 as day_offset
    from table(generator(rowcount => 10000))

),

days as (

    select dateadd(day, day_offset, '2011-12-01'::date) as date_day
    from day_numbers

)

select
    date_day,
    year(date_day)                      as year,
    quarter(date_day)                   as quarter,
    month(date_day)                     as month,
    monthname(date_day)                 as month_name,
    date_trunc('month', date_day)       as month_start,
    date_trunc('week', date_day)        as week_start,
    dayofweekiso(date_day)              as day_of_week,     -- 1 = Monday
    dayname(date_day)                   as day_name,
    dayofweekiso(date_day) in (6, 7)    as is_weekend
from days
where date_day <= current_date()