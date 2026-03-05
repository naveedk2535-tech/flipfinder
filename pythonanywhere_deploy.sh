#!/bin/bash
echo "Pulling latest FlipFinder update..."
cd ~/flipfinder
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
echo "Done! Go click Reload in PythonAnywhere Web tab."
