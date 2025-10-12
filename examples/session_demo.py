#!/usr/bin/env python
"""
Demonstration of CLI session-based variable tracking.

Sessions allow persistent variable tracking across multiple CLI commands,
making it easier to build models iteratively without having to remember
or copy-paste complex IDs.

Example workflow:
1. Add individuals with meaningful variable names
2. Variables are automatically saved to the session
3. Use variable names in subsequent commands
4. Variables persist across CLI invocations
"""

print("""
Session-Based Variable Tracking Demo
====================================

This demo shows how to use sessions for persistent variable tracking
across multiple CLI commands. Sessions store variables in .noctua/*.yaml
files that persist between commands.

Example Commands:
----------------

# Create a new model and start a session called "demo"
noctua-py barista create-model --title "Session Demo" --session demo

# Add individuals and assign them to variables
noctua-py barista add-individual \\
    --model gomodel:123 \\
    --class GO:0003924 \\
    --assign ras \\
    --session demo

noctua-py barista add-individual \\
    --model gomodel:123 \\
    --class GO:0004674 \\
    --assign raf \\
    --session demo

# Now use the variable names instead of complex IDs!
noctua-py barista add-fact \\
    --model gomodel:123 \\
    --subject ras \\
    --object raf \\
    --predicate RO:0002413 \\
    --session demo

# Add evidence using variables
noctua-py barista add-fact-evidence \\
    --model gomodel:123 \\
    --subject ras \\
    --object raf \\
    --predicate RO:0002413 \\
    --eco ECO:0000314 \\
    --source PMID:12345 \\
    --session demo

Session Management Commands:
----------------------------

# List all sessions
noctua-py session list

# Show variables in a session
noctua-py session show demo

# Show variables for a specific model
noctua-py session show demo --model gomodel:123

# Clear variables in a session (keep session)
noctua-py session clear demo

# Delete a session completely
noctua-py session delete demo

Benefits:
---------

1. **No ID Management**: Use meaningful names like 'ras', 'raf' instead of
   'gomodel:123/individual-456789'

2. **Persistence**: Variables survive between CLI invocations, perfect for
   iterative model building

3. **Model Scoping**: Variables are scoped to models, so 'ras' can mean
   different things in different models

4. **Easy Collaboration**: Share session files with colleagues to transfer
   variable mappings

Session Files:
--------------

Sessions are stored in .noctua/ directory (in current directory or home).
Each session is a YAML file containing:
- Session name
- Model ID (optional default)
- Variable mappings (model:variable -> actual_id)
- Metadata

Example .noctua/demo.yaml:
```yaml
name: demo
model_id: gomodel:123
variables:
  'gomodel:123:ras': 'gomodel:123/individual-001'
  'gomodel:123:raf': 'gomodel:123/individual-002'
metadata: {}
```

Tips:
-----

- Use descriptive session names for different projects
- Sessions can span multiple models
- Variable names should be simple (alphanumeric + underscore)
- CURIEs (with ':') are never treated as variables
- Mix variables and CURIEs freely in commands
""")

if __name__ == "__main__":
    print("\nTo try this demo, run the commands above with a valid BARISTA_TOKEN.")
    print("Start with 'export BARISTA_TOKEN=your-token-here'")