#!/bin/bash
set -e

echo "=========================================="
echo "Git Push - Excluding Workflow Files"
echo "=========================================="

cd /mnt/d/workspace/auggie-agentic_sdlc_workflow/workspace/ChatApplication/project-code

echo ""
echo "Step 1: Reset last commit (keep changes staged)"
git reset --soft HEAD~1
echo "✓ Commit reset"

echo ""
echo "Step 2: Unstage workflow files"
git reset HEAD .github/workflows/ 2>/dev/null || echo "Workflow files already unstaged"
echo "✓ Workflow files unstaged"

echo ""
echo "Step 3: Show current status"
git status

echo ""
echo "Step 4: Commit without workflows"
git commit -m "[AI-Generated] Create Production Deployment Configuration and Documentation (excluding workflows)"
echo "✓ Changes committed without workflows"

echo ""
echo "Step 5: Push to remote"
git push origin main
echo "✓ Changes pushed successfully"

echo ""
echo "=========================================="
echo "✅ Push completed!"
echo "=========================================="
echo ""
echo "Note: Workflow files (.github/workflows/) were excluded from this push."
echo "They will need to be added separately after updating the GitHub PAT with 'workflow' scope."
