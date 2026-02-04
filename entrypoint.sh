#!/bin/bash
# -----------------------------
# entrypoint.sh
# -----------------------------
set -e # Exit immediately if a command exits with a non-zero status

# 1️⃣ Check for Key
if [ -z "$FIELD_ENCRYPTION_KEY" ]; then
  echo "ERROR: FIELD_ENCRYPTION_KEY is missing in .env!"
  exit 1
fi

# 2️⃣ Wait for MySQL
# We use 'mysqladmin ping' to check if the DB server is actually ready to accept connections
echo "Waiting for MySQL..."
until mysqladmin ping -h "$MYSQL_HOST" --silent; do
  echo "MySQL is unavailable - sleeping..."
  sleep 2
done
echo "MySQL is up!"

# 3️⃣ A - GENERATE MIGRATIONS (The Fix)
# This creates the migration file (e.g., 0002_ticket.py) if it doesn't exist yet
echo "Generating missing migration files..."
python manage.py makemigrations

# 3️⃣ B - APPLY MIGRATIONS
# This builds the actual database tables based on the migration files
echo "Applying migrations..."
python manage.py migrate --noinput

# 4️⃣ Ensure groups and admin user exist
# This runs a small python script to seed your DB with required roles and admin
python manage.py shell -c "
from django.contrib.auth.models import Group, User
import os

# Create Roles
for r in ['Citizen', 'GovernmentWorker']:
    Group.objects.get_or_create(name=r)
    print(f'Role ensured: {r}')

# Create Admin
admin_username = os.getenv('ADMIN_USER', 'admin')
admin_password = os.getenv('ADMIN_PASS', 'adminpass')
email = 'admin@example.com'

if not User.objects.filter(username=admin_username).exists():
    User.objects.create_superuser(username=admin_username, email=email, password=admin_password)
    print(f'Admin user created: {admin_username}')
else:
    print('Admin user already exists')
"

# 5️⃣ Start the main command (Gunicorn or Runserver)
echo "Starting Server..."
exec "$@"