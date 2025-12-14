#!/bin/bash
# Wait for MySQL
echo "Waiting for MySQL..."
until mysqladmin ping -h "$MYSQL_HOST" --silent; do
  sleep 2
done

echo "MySQL is up! Running migrations..."
python manage.py migrate --noinput

# Create groups and admin (optional, handled in views too)
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

exec "$@"
