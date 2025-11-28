import pandas as pd

df = pd.read_csv('models/ltr_training_data.csv')
print(f'Columns ({len(df.columns)}):')
print(df.columns.tolist())
print(f'\nhybrid_score present: {"hybrid_score" in df.columns}')

if 'hybrid_score' in df.columns:
    print('\nhybrid_score stats:')
    print(df['hybrid_score'].describe())
    print('\nFirst 5 hybrid_score values:')
    print(df['hybrid_score'].head())
else:
    print('\n❌ hybrid_score column MISSING!')
