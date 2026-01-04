#!/bin/bash
# -----------------------------
# entrypoint.sh
# -----------------------------

# 1️⃣ Generate FIELD_ENCRYPTION_KEY if missing
if [ -z "$FIELD_ENCRYPTION_KEY" ]; then
  export FIELD_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  echo "Generated new FIELD_ENCRYPTION_KEY: $FIELD_ENCRYPTION_KEY"
else
  echo "Using existing FIELD_ENCRYPTION_KEY"
fi

# 2️⃣ Wait for MySQL
echo "Waiting for MySQL..."
until mysqladmin ping -h "$MYSQL_HOST" --silent; do
  sleep 2
done
echo "MySQL is up! Running migrations..."

# 3️⃣ Run Django migrations
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

# 5️⃣ Start the main command (e.g., gunicorn)
exec "$@"
