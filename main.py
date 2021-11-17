import streamlit as st
import pandas as pd 
import datetime 
import plotly 
import plotly.express as px 
import numpy as np 

# pages are broken into containers (horizontal units) and columns (vertical units)
intro = st.container()
window_picker = st.container()
chain_chart = st.container()
asset_chart = st.container()
uniques = st.container()
appendix = st.container()

# only run once as long as parameters don't change
@st.cache
def get_data(filename):
    # read in data
    df = pd.read_csv(filename, index_col='DATA_DATE', parse_dates=True)
    # extract chain and asset info from poorly constructed pool_name field
    df[['CHAIN', 'ASSET']] = df['POOL_NAME'].str.split('.', 1, expand=True)
    df[['ASSET', 'ALT_INFO']] = df['ASSET'].str.split('-', 1, expand=True)

    return df 


def filter_dataframe(message, df):
    months = df.index.to_period('M').unique()
    window = st.select_slider(message, 
                              options=months, 
                              value=[months[0],months[len(months)-1]])
    
    start_date = window[0].start_time
    end_date = window[1].end_time
    
    filtered_df = df.loc[start_date:end_date]

    return filtered_df
    
with intro:
    st.markdown('# THORChain Pool Depth')
    st.markdown('The interpreted goal is to answer the following two questions:')
    md = '''
1. How much liquidity is there by pool?
2. How many people provide this liquidity?

I will answer these questions in visual form in two ways:  one by chain and the other by asset.
    '''

    st.markdown(md)


with window_picker:
    df = get_data('data/thor_17.csv')
    filtered_df = filter_dataframe('Move sliders to filter on the time frame of your choice...', df) 
    
    
with chain_chart:
    st.header('By chain:')
    
    chain = st.select_slider('Select chain to graph...', 
                             options=filtered_df['CHAIN'].unique())
    
    dawg = filtered_df[filtered_df['CHAIN'] == chain]
    
    fig = px.scatter(dawg, 
                     x=dawg.index, 
                     y='POOL_DEPTH_USD',  
                     color='ASSET',
                     title='Pool Depth ($)')
    
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.scatter(dawg, 
                     x=dawg.index, 
                     y=['N_UNIQUE_LPERS', 'N_UNIQUE_PROVIDERS', 'N_UNIQUE_TAKERAWAYERS'],
                     title='# Unique Players by Player Type'
                     )

    st.plotly_chart(fig2, use_container_width=True)


with asset_chart:
    st.header('By asset:')
    
    asset = st.select_slider('Select asset to graph...', 
                             options=np.sort(filtered_df['ASSET'].unique()))
    
    dawg = filtered_df[filtered_df['ASSET'] == asset]
    
    fig = px.scatter(dawg, 
                     x=dawg.index, 
                     y='POOL_DEPTH_USD', 
                     color='CHAIN',
                     title='Pool Depth ($)')
    
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.scatter(dawg, 
                     x=dawg.index, 
                     y=['N_UNIQUE_LPERS', 'N_UNIQUE_PROVIDERS', 'N_UNIQUE_TAKERAWAYERS'],
                     title='# Unique Players by Player Type'
                     )

    st.plotly_chart(fig2, use_container_width=True)


with uniques:
    st.markdown('Just for giggles, here are some extra stats.  Enjoy!')

    st.subheader('Average Daily # Of Unique ...')
    lp_col, provider_col, takerawayer_col = st.columns(3)

    n_lpers = filtered_df['N_UNIQUE_LPERS'].mean()
    n_lpers_str = f'{n_lpers:.1f}'

    n_providers = filtered_df['N_UNIQUE_PROVIDERS'].mean()
    n_providers_str = f'{n_providers:.1f}'

    n_takerawayers = filtered_df['N_UNIQUE_TAKERAWAYERS'].mean()
    n_takerawayers_str = f'{n_takerawayers:.1f}'

    lp_col.metric(label="Providers & Takerawayers", value=n_lpers_str)
    provider_col.metric(label="Providers", value=n_providers_str)
    takerawayer_col.metric(label="Takerawayers", value=n_takerawayers_str)

with appendix:
    st.header('Appendix')
    st.caption('SQL code:')
    st.code('''
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
    '''
    )