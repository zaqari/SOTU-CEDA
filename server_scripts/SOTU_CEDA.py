import os
import torch
import pandas as pd
from tqdm import tqdm
from kgen2.CEDA import ceda_model
from datetime import datetime as dt





###########################################################################################
###### Basic set-up: variables
###########################################################################################
print('CUDA:', torch.cuda.is_available())

start = dt.now()
PATH = '/home/user/SOTU/'
output_name = os.path.join(PATH, 'ckpts', 'ckpt-{}.pt')
dataset = os.path.join(PATH, 'merged.json')

print(PATH, '\n\n')

level = [7]




###########################################################################################
###### Data and progress
###########################################################################################
# Data
df = pd.read_json(dataset)
df['line_no'] = df.index.values
df.index = range(len(df))
df['text'] = df['text'].apply(lambda x: x.replace('\n', ' '))
df['SOTU'] = df['SOTU'].apply(lambda x: x.replace('\n', ' '))

meta_data_cols = [col for col in list(df) if col not in ['text', 'SOTU']]

# Tracking
tracker_name = os.path.join(PATH, 'tracker.txt')
if os.path.exists(tracker_name):
    df = df.loc[~df['YEAR'].isin(pd.read_table(tracker_name, sep='\t')['YEAR'].values)]
else:
    pd.DataFrame(columns=['YEAR']).to_csv(tracker_name, sep='\t', index=False, encoding='utf-8')




###########################################################################################
###### Process
###########################################################################################
for year in df['YEAR'].unique():
    print('\n+++++++{}+++++++'.format(year))

    GRAPH = ceda_model(
        sigma=1.5,
        device='cuda',
        wv_model='roberta-base',
        wv_layers=level
    )

    sub = df.loc[df['YEAR'].isin([year])]

    GRAPH.fit(sub['SOTU'].values.tolist(), sub['text'].values.tolist())

    GRAPH.meta_data = sub[meta_data_cols].to_dict(orient='records')

    GRAPH.checkpoint(str(output_name).format(year))

    pd.DataFrame({'YEAR': year}).to_csv(tracker_name, index=False, header=False, encoding='utf-8', sep='\t', mode='a')

print('=======][=======')