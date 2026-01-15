"""Enhanced diagnostic script to inspect model.config structure."""

import yaml
from minisweagent.models import get_model

# Your model configuration
model_config = {
    "model_name": "openai/gpt-5-mini",
    "model_class": "litellm_response",
    "model_kwargs": {
        "reasoning": {
            "effort": "low"
        }
    }
}

print("="*80)
print("Enhanced Model Structure Diagnostic")
print("="*80)

# Create model
print("\n1. Creating model...")
model = get_model(model_config["model_name"], model_config)
print(f"   Model type: {type(model).__name__}")

# Deep dive into config object
print("\n2. Inspecting model.config object...")
config = model.config
print(f"   Type: {type(config).__name__}")
print(f"   Module: {type(config).__module__}")

# Check config attributes
print("\n3. Config object attributes:")
config_attrs = [attr for attr in dir(config) if not attr.startswith('_')]
for i, attr in enumerate(config_attrs, 1):
    try:
        attr_value = getattr(config, attr)
        attr_type = type(attr_value).__name__
        # Show value for simple types
        if attr_type in ['str', 'int', 'float', 'bool', 'NoneType']:
            print(f"   {i:2d}. {attr:25s} -> {attr_type:20s} = {attr_value}")
        elif attr_type == 'dict':
            print(f"   {i:2d}. {attr:25s} -> {attr_type:20s} keys: {list(attr_value.keys())}")
        else:
            print(f"   {i:2d}. {attr:25s} -> {attr_type}")
    except Exception as e:
        print(f"   {i:2d}. {attr:25s} -> Error: {e}")

# Check if config has model_kwargs
print("\n4. Looking for model_kwargs in config...")
if hasattr(config, 'model_kwargs'):
    print(f"   ✓ config.model_kwargs exists")
    print(f"   Type: {type(config.model_kwargs)}")
    print(f"   Content: {config.model_kwargs}")
else:
    print(f"   ✗ config.model_kwargs does NOT exist")

# Check config.__dict__
print("\n5. Checking config.__dict__:")
if hasattr(config, '__dict__'):
    print(f"   ✓ config.__dict__ exists")
    print(f"   Keys: {list(config.__dict__.keys())}")
    for key, value in config.__dict__.items():
        print(f"      - {key}: {type(value).__name__} = {value if isinstance(value, (str, int, float, bool, type(None))) else type(value).__name__}")
else:
    print(f"   ✗ config.__dict__ does NOT exist")

# Try to find where model_kwargs from config actually went
print("\n6. Searching for 'reasoning' configuration...")
found_locations = []

def search_object(obj, path="", depth=0, max_depth=3):
    """Recursively search for 'reasoning' in object."""
    if depth > max_depth:
        return

    if hasattr(obj, '__dict__'):
        for key, value in obj.__dict__.items():
            new_path = f"{path}.{key}" if path else key
            if key == 'reasoning' or key == 'model_kwargs':
                found_locations.append((new_path, value))
                print(f"   Found at: {new_path}")
                print(f"   Value: {value}")
            elif isinstance(value, dict) and ('reasoning' in value or 'model_kwargs' in value):
                found_locations.append((new_path, value))
                print(f"   Found in dict at: {new_path}")
                print(f"   Relevant keys: {[k for k in value.keys() if 'reasoning' in k or 'model_kwargs' in k]}")
            elif hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool, list, tuple)):
                search_object(value, new_path, depth + 1, max_depth)

search_object(model, "model")
search_object(config, "config")

if not found_locations:
    print("   ✗ No 'reasoning' or 'model_kwargs' found in object tree")

# Test modifying config
print("\n7. Testing different modification approaches...")

# Approach 1: Create model_kwargs on model
print("\n   Approach 1: Create model.model_kwargs")
try:
    model.model_kwargs = model_config['model_kwargs'].copy()
    print(f"   ✓ Successfully created model.model_kwargs")
    print(f"   Content: {model.model_kwargs}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# Approach 2: Create model_kwargs on config
print("\n   Approach 2: Create config.model_kwargs")
try:
    config.model_kwargs = model_config['model_kwargs'].copy()
    print(f"   ✓ Successfully created config.model_kwargs")
    print(f"   Content: {config.model_kwargs}")
except Exception as e:
    print(f"   ✗ Failed: {e}")

# Approach 3: Check if config has other parameter storage
print("\n   Approach 3: Looking for alternative parameter storage in config")
for attr in ['api_params', 'completion_kwargs', 'request_kwargs', 'model_params', 'extra_params']:
    if hasattr(config, attr):
        print(f"   ✓ config.{attr} exists: {getattr(config, attr)}")

print("\n" + "="*80)
print("Enhanced Diagnostic complete!")
print("="*80)

