#!/usr/bin/env python

import matplotlib.pyplot as plt
import pandas as pd
import sys

df = pd.read_csv(sys.argv[1])
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df = df.set_index('Timestamp')

for country in set(df['Country']):
    country_data = df[df['Country'] == country]
    plt.figure(figsize=(12.00,7.0))
    country_data['Z_Score'].plot()
    country_data['Delay_Z_Score'].plot()
    plt.legend()
    plt.axhline(y=0, color='k', linestyle='--')
    plt.ylabel('Z-score')
    start_year = country_data[country_data['Z_Score'].notnull()].index[0].year
    end_year = country_data[country_data['Z_Score'].notnull()].index[-1].year
    plt.title(f'Excess Deaths in {country} {start_year}-{end_year} via EuroMOMO')
    plt.tight_layout()
    plt.savefig(f'{country}_{start_year}-{end_year}.png', pad_inches=0.1)
    plt.close()
