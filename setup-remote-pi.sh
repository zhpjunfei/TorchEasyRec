#!/bin/bash
set -e

cd /Users/zhangjunfei/mmb/TorchEasyRec
echo "Setting up remote-pi in $(pwd)..."

# Create the project-local remote-pi config and skills directory
mkdir -p .pi/remote/skills

# Copy agent-network skill locally (project-scoped)
cp -r /Users/zhangjunfei/.local/node-v22.14.0-darwin-arm64/lib/node_modules/remote-pi/skills/agent-network .pi/remote/skills/

echo "Done: agent-network skill installed to .pi/remote/skills/"
echo "Next: run '/remote-pi' within a pi session to start the interactive setup wizard."
