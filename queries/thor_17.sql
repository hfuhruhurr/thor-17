with 
daily_token_depths as (
select 
  block_timestamp::date as data_date,
  pool_name             ,
  rune_e8/1e8           as closing_rune_amount,
  asset_e8/1e8          as closing_asset_amount

from 
  thorchain.block_pool_depths 

qualify
  row_number() over (partition by data_date, pool_name order by block_timestamp desc) = 1  -- neat trick to grab most recent
) 
,

daily_token_prices as (
select 
  block_timestamp::date as data_date,
  pool_name             ,
  rune_usd              as closing_p_rune,
  asset_usd             as closing_p_asset

from 
  thorchain.prices 

qualify
  row_number() over (partition by data_date, pool_name order by block_timestamp desc) = 1  -- most recent record for the specified pool and date
)
,

massaged_raw as (
select 
  block_timestamp::date                                   as data_date,
  pool_name                                               ,
  from_address                                            as lper,
  iff(lp_action = 'add_liquidity'   , from_address, NULL) as provider,
  iff(lp_action = 'remove_liquidity', from_address, NULL) as takerawayer
  
    
from 
  thorchain.liquidity_actions
) 
,

daily_unique_lpers as (
select 
  data_date,
  pool_name,
  count(distinct lper)        as n_unique_lpers,
  count(distinct provider)    as n_unique_providers,
  count(distinct takerawayer) as n_unique_takerawayers

from 
  massaged_raw

group by 1,2
)

select 
  d.data_date,
  d.pool_name,
  (d.closing_rune_amount*p.closing_p_rune) + (d.closing_asset_amount*p.closing_p_asset) as pool_depth_usd,
  l.n_unique_lpers,
  l.n_unique_providers,
  l.n_unique_takerawayers

from 
  daily_token_depths d 
  
  join daily_token_prices p 
    on d.data_date = p.data_date 
       and d.pool_name = p.pool_name

  join daily_unique_lpers l 
    on d.data_date = l.data_date
       and d.pool_name = l.pool_name

order by 1,2

