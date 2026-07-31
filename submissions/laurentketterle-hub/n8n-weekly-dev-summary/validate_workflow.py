#!/usr/bin/env python3
"""
Validate n8n workflow JSON structure.
Checks: node count, connections, required node types, Claude API configuration,
bilingual support, delivery channels, and error handling.
"""
import json
import sys
import os

WORKFLOW_PATH = os.path.join(os.path.dirname(__file__), 'workflow.json')

def validate_workflow(path):
    """Run all validation checks on the workflow file."""
    errors = []
    warnings = []

    with open(path) as f:
        wf = json.load(f)

    name = wf.get('name', 'unnamed')
    nodes = wf.get('nodes', [])
    connections = wf.get('connections', {})

    # 1. Basic structure
    if not nodes:
        errors.append('No nodes found in workflow')
    if not connections:
        errors.append('No connections found in workflow')

    # 2. Node count (should have at least 10 for a complete workflow)
    if len(nodes) < 10:
        warnings.append(f'Only {len(nodes)} nodes — expected >=10 for full pipeline')

    # 3. Required node types
    node_types = {n.get('type', '') for n in nodes}
    node_names = {n.get('name', '') for n in nodes}

    required_types = {
        'n8n-nodes-base.scheduleTrigger': 'Cron trigger',
        'n8n-nodes-base.httpRequest': 'HTTP request (GitHub/Claude API)',
        'n8n-nodes-base.code': 'Code/transformation node',
    }

    for req_type, desc in required_types.items():
        if req_type not in node_types:
            errors.append(f'Missing required node type: {desc} ({req_type})')

    # 4. Specific required nodes by name
    required_names = [
        'Weekly Cron',
        'Fetch Commits',
        'Fetch Closed Issues',
        'Fetch Merged PRs',
        'Aggregate',
        'Claude API',
        'Format Output',
    ]
    for req_name in required_names:
        matches = [n for n in nodes if req_name.lower() in n.get('name', '').lower()]
        if not matches:
            warnings.append(f'Missing recommended node: "{req_name}"')

    # 5. Claude API node check
    claude_nodes = [n for n in nodes if 'claude' in n.get('name', '').lower() or 'anthropic' in str(n.get('parameters', {})).lower()]
    if not claude_nodes:
        errors.append('No Claude/Anthropic API node found')

    # 6. Check for required API URLs
    all_params = json.dumps([n.get('parameters', {}) for n in nodes])
    if 'api.github.com' not in all_params:
        errors.append('No GitHub API endpoint found in any node')
    if 'api.anthropic.com' not in all_params:
        errors.append('No Anthropic API endpoint found in any node')

    # 7. Delivery channels
    delivery_channels = []
    if 'discord' in all_params.lower():
        delivery_channels.append('Discord')
    if 'slack' in all_params.lower():
        delivery_channels.append('Slack')
    if 'email' in all_params.lower() or 'smtp' in all_params.lower():
        delivery_channels.append('Email')

    if not delivery_channels:
        warnings.append('No delivery channel detected (Discord/Slack/Email)')
    else:
        print(f'   Delivery channels: {", ".join(delivery_channels)}')

    # 8. Connection validity
    for src, targets in connections.items():
        if src not in node_names:
            # Fuzzy match
            close = [n for n in node_names if src.lower() in n.lower() or n.lower() in src.lower()]
            if close:
                warnings.append(f'Connection source "{src}" not exact match — closest: {close[0]}')
            else:
                errors.append(f'Connection source "{src}" not found in nodes')

        for target_list in targets.get('main', []):
            for target in target_list:
                tgt_name = target.get('node', '')
                if tgt_name and tgt_name not in node_names:
                    errors.append(f'Connection target "{tgt_name}" not found in nodes')

    # 9. Bilingual support check
    has_fr = 'FR' in all_params or 'français' in all_params.lower() or 'french' in all_params.lower()
    if has_fr:
        print('   ✅ Bilingual support (EN/FR) detected')
    else:
        warnings.append('No French/FR language support detected')

    # 10. Error handling
    continue_on_fail = sum(1 for n in nodes if n.get('continueOnFail'))
    if continue_on_fail > 0:
        print(f'   Error handling: {continue_on_fail} nodes with continueOnFail')
    else:
        warnings.append('No nodes have continueOnFail — pipeline may halt on API errors')

    # 11. Architecture checks
    cron_nodes = [n for n in nodes if 'scheduleTrigger' in n.get('type', '')]
    if cron_nodes:
        for cn in cron_nodes:
            interval = cn.get('parameters', {}).get('rule', {}).get('interval', [{}])
            hours = interval[0].get('hoursInterval', 0) if interval else 0
            if hours == 168:
                print(f'   ✅ Cron interval: {hours}h (weekly)')
            else:
                print(f'   Cron interval: {hours}h')

    # 12. Model check
    if 'claude-sonnet-4-20250514' in all_params:
        print('   ✅ Model: claude-sonnet-4-20250514')
    elif 'claude' in all_params.lower():
        warnings.append('Claude model version not explicitly set to claude-sonnet-4-20250514')

    # Report
    print(f'\n{"="*60}')
    print(f'Workflow: "{name}"')
    print(f'Nodes: {len(nodes)} | Connections: {len(connections)}')
    print(f'Errors: {len(errors)} | Warnings: {len(warnings)}')

    if errors:
        print(f'\n❌ ERRORS ({len(errors)}):')
        for e in errors:
            print(f'   • {e}')

    if warnings:
        print(f'\n⚠️  WARNINGS ({len(warnings)}):')
        for w in warnings:
            print(f'   • {w}')

    if not errors:
        print(f'\n✅ VALID — Workflow passes all critical checks')
        return 0
    else:
        print(f'\n❌ INVALID — {len(errors)} critical error(s) found')
        return 1


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else WORKFLOW_PATH
    sys.exit(validate_workflow(path))
