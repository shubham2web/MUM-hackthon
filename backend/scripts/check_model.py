import joblib

bundle = joblib.load('models/ltr_reranker.joblib')
print(f'Type: {type(bundle)}')

if isinstance(bundle, dict):
    print(f'\n✅ Model is a bundle dict!')
    print(f'Keys: {list(bundle.keys())}')
    print(f'\nFeatures ({bundle.get("n_features", "N/A")}):')
    print(bundle.get('feature_names', 'N/A'))
    print(f'\nModel type: {bundle.get("model_type", "N/A")}')
    print(f'Calibrated: {bundle.get("calibrated", "N/A")}')
    
    # Check model's expected features
    model = bundle.get('model')
    if model:
        print(f'\nModel class: {type(model).__name__}')
        if hasattr(model, 'n_features_in_'):
            print(f'Model expects: {model.n_features_in_} features')
else:
    print('\n❌ Model is RAW (not a bundle) - has no feature validation!')
    if hasattr(bundle, 'n_features_in_'):
        print(f'Raw model expects: {bundle.n_features_in_} features')
