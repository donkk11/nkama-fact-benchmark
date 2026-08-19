#!/bin/bash
# Runs the real PyPI/GitHub stats snapshot for nkama-fact-benchmark.
# Invoked by ~/Library/LaunchAgents/com.donkk11.nkama-stats-snapshot.plist
cd "/Users/kknkama/Documents/openklaw/ai_control_layer/nkama-fact-benchmark-repo" || exit 1
/usr/bin/python3 tracking/snapshot_stats.py
