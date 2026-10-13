{#
    One key per product + sub-product pair. Used by both dim_product and
    fct_complaints, so the join keys are always built the same way.
#}
{% macro product_key(product_column, sub_product_column) %}
    md5(coalesce({{ product_column }}, '') || '|' || coalesce({{ sub_product_column }}, ''))
{% endmacro %}