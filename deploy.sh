#!/bin/bash
echo "Deploying FlipFinder to GitHub..."
git add .
git commit -m "Deploy: $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main
echo ""
echo "Code pushed to GitHub!"
echo ""
echo "Now on PythonAnywhere Bash console run:"
echo "  cd ~/flipfinder && git pull && source venv/bin/activate && pip install -r requirements.txt"
echo "Then click Reload in the Web tab."
