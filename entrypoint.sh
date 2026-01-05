#!/bin/bash
# -----------------------------
# entrypoint.sh
# -----------------------------

# 1️⃣ Check for Key
if [ -z "$FIELD_ENCRYPTION_KEY" ]; then
  echo "ERROR: FIELD_ENCRYPTION_KEY is missing in .env!"
  exit 1
fi

# 2️⃣ Wait for MySQL
echo "Waiting for MySQL..."
until mysqladmin ping -h "$MYSQL_HOST" --silent; do
  sleep 2
done
echo "MySQL is up!"

# 3️⃣ A - GENERATE MIGRATIONS (The Fix)
# This creates '0002_citizenprofile.py' automatically if it's missing
echo "Generating missing migration files..."
python manage.py makemigrations

# 3️⃣ B - APPLY MIGRATIONS
# This builds the actual database tables
echo "Applying migrations..."
python manage.py migrate --noinput

# 4️⃣ Ensure groups and admin user exist
python manage.py shell -c "
from django.contrib.auth.models import Group, User
import os

for r in ['Citizen','GovernmentWorker']:
    Group.objects.get_or_create(name=r)

admin_username = os.getenv('ADMIN_USER')
admin_password = os.getenv('ADMIN_PASS')
if not User.objects.filter(username=admin_username).exists():
    User.objects.create_superuser(username=admin_username, email='admin@example.com', password=admin_password)
"

# 5️⃣ Start the main command
exec "$@"