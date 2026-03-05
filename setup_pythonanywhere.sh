#!/bin/bash
echo "First-time FlipFinder setup on PythonAnywhere (zziai36)..."
cd ~
git clone https://github.com/naveedk2535-tech/flipfinder.git
cd flipfinder
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
echo ""
echo "Setup complete! Now do these steps in PythonAnywhere dashboard:"
echo ""
echo "1. Web tab > Add new web app > Manual config > Python 3.13"
echo "2. Source code:    /home/zziai36/flipfinder"
echo "3. Virtualenv:     /home/zziai36/flipfinder/venv"
echo ""
echo "4. Edit WSGI file — replace ALL contents with:"
echo "   import sys"
echo "   sys.path.insert(0, '/home/zziai36/flipfinder')"
echo "   from app import create_app"
echo "   application = create_app()"
echo ""
echo "5. Web tab > Environment variables, add:"
echo "   ANTHROPIC_API_KEY = your-key-here"
echo "   SECRET_KEY        = your-32-char-random-string"
echo "   DATABASE_URL      = sqlite:////home/zziai36/flipfinder/flipfinder.db"
echo ""
echo "6. Click Reload"
echo "   Your site: https://zziai36.pythonanywhere.com"
echo ""
echo "7. Make yourself admin — open PythonAnywhere Bash console:"
echo "   cd ~/flipfinder && source venv/bin/activate && python3"
echo "   >>> from app import create_app, db; from models.user import User"
echo "   >>> app = create_app()"
echo "   >>> with app.app_context():"
echo "   ...     u = User.query.filter_by(email='YOUR_EMAIL').first()"
echo "   ...     u.is_admin = True"
echo "   ...     db.session.commit()"
