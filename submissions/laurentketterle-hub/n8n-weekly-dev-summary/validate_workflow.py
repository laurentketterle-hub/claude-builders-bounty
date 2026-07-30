#!/usr/bin/env python3
"""Validate n8n workflow JSON structure."""
import json, sys

with open('workflow.json') as f:
    wf = json.load(f)

assert 'nodes' in wf, 'Missing nodes'
assert 'connections' in wf, 'Missing connections'
assert len(wf['nodes']) >= 5, f'Expected >=5 nodes, got {len(wf["nodes"])}'

# Check required nodes exist
node_types = {n['type'] for n in wf['nodes']}
required = {'n8n-nodes-base.scheduleTrigger', 'n8n-nodes-base.httpRequest'}
assert required.intersection(node_types), f'Missing required node types'

# Check connections reference valid nodes
node_names = {n['name'] for n in wf['nodes']}
for src, targets in wf['connections'].items():
    assert src in node_names, f'Connection source "{src}" not in nodes'

print(f'✅ Valid workflow: {len(wf["nodes"])} nodes, {len(wf["connections"])} connections')
