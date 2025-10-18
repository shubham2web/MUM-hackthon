from server import app

print("=== Checking endpoint names ===")
for rule in app.url_map.iter_rules():
    if 'debate' in rule.rule:
        print(f"Endpoint name: '{rule.endpoint}'")
        print(f"URL rule: {rule.rule}")
        print(f"Methods: {rule.methods}")