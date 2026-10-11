select
    state_code,
    state_name,
    state_type,
    census_region,
    population_2025,
    state_type in ('State', 'District')     as is_50_states_and_dc
from {{ ref('state_population') }}