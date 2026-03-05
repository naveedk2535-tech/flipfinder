# FlipFinder Deployment Guide

## What You Need
- GitHub account (naveedk2535-tech)
- PythonAnywhere paid account at /home/zziai36
- Anthropic API key (console.anthropic.com)

## Step 1 — Push to GitHub (run once on your computer)
```bash
gh repo create flipfinder --public --source=. --remote=origin --push
chmod +x deploy.sh pythonanywhere_deploy.sh setup_pythonanywhere.sh
```

## Step 2 — First-time PythonAnywhere Setup
Open Bash console on PythonAnywhere and run:
```bash
bash <(curl -s https://raw.githubusercontent.com/naveedk2535-tech/flipfinder/main/setup_pythonanywhere.sh)
```

WSGI file contents (paste exactly):
```python
import sys
sys.path.insert(0, '/home/zziai36/flipfinder')
from app import create_app
application = create_app()
```

Environment variables to add in Web tab:
```
ANTHROPIC_API_KEY = sk-ant-...
SECRET_KEY        = a-very-long-random-secret-string
DATABASE_URL      = sqlite:////home/zziai36/flipfinder/flipfinder.db
```

## Step 3 — Make Yourself Admin
In PythonAnywhere Bash console:
```python
cd ~/flipfinder && source venv/bin/activate && python3
>>> from app import create_app, db; from models.user import User
>>> app = create_app()
>>> with app.app_context():
...     u = User.query.filter_by(email='YOUR_EMAIL').first()
...     u.is_admin = True
...     db.session.commit()
```

## Every Future Update
On your computer:   `./deploy.sh`
On PythonAnywhere:  `cd ~/flipfinder && ./pythonanywhere_deploy.sh`
Then click Reload in Web tab.

## Site URLs
- Live site:   https://zziai36.pythonanywhere.com
- Admin panel: https://zziai36.pythonanywhere.com/admin
- Pricing:     https://zziai36.pythonanywhere.com/billing/pricing
