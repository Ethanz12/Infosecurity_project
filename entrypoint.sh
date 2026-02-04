#!/bin/bash
# -----------------------------
# entrypoint.sh
# -----------------------------
set -e

# 1️⃣ Check for Key
if [ -z "$FIELD_ENCRYPTION_KEY" ]; then
  echo "ERROR: FIELD_ENCRYPTION_KEY is missing in .env!"
  exit 1
fi

# 2️⃣ Wait for MySQL
echo "Waiting for MySQL..."
until mysqladmin ping -h "$MYSQL_HOST" --silent; do
  echo "MySQL is unavailable - sleeping..."
  sleep 2
done
echo "MySQL is up!"

# 3️⃣ Migrations
echo "Generating missing migration files..."
python manage.py makemigrations
echo "Applying migrations..."
python manage.py migrate --noinput

# 4️⃣ Auto-Setup: Roles, Admin, and Staff
echo "--- STARTING AUTO-SETUP ---"
python manage.py shell -c "
import os
from django.contrib.auth.models import Group, User
from django.apps import apps

# 1. Ensure Roles
for r in ['Citizen', 'GovernmentWorker']:
    Group.objects.get_or_create(name=r)
    print(f'Role ensured: {r}')

# 2. Ensure Super Admin
admin_user = os.getenv('ADMIN_USER', 'admin')
admin_pass = os.getenv('ADMIN_PASS', 'adminpass')
if not User.objects.filter(username=admin_user).exists():
    User.objects.create_superuser(username=admin_user, email='admin@example.com', password=admin_pass)
    print(f'✅ Superuser created: {admin_user}')

# 3. Ensure Staff Accounts (The Critical Part)
try:
    # We use get_model because it is safer than direct imports
    StaffProfile = apps.get_model('home', 'StaffProfile')
except LookupError as e:
    print(f'❌ CRITICAL ERROR: Could not find StaffProfile model. Error: {e}')
    exit(1)

# Config: (EnvUser, EnvPass, Department, Level)
config = [
    ('HEALTH_USER', 'HEALTH_PASS', 'HEALTH', 2),
    ('FINANCE_USER', 'FINANCE_PASS', 'FINANCE', 2),
    ('GENERAL_USER', 'GENERAL_PASS', 'GENERAL', 1),
]

gov_group = Group.objects.get(name='GovernmentWorker')

print('--- Configuring Staff Accounts ---')
for u_var, p_var, dept, lvl in config:
    username = os.getenv(u_var)
    password = os.getenv(p_var)

    if not username or not password:
        print(f'⚠️  Skipping {dept}: {u_var} or {p_var} missing in .env')
        continue

    # Create/Update User
    user, created = User.objects.get_or_create(username=username)
    user.set_password(password) # Force password sync
    user.email = f'{username}@gov.sg'
    user.is_staff = True
    user.groups.add(gov_group)
    user.save()

    # Create/Update Profile
    StaffProfile.objects.update_or_create(
        user=user,
        defaults={'department': dept, 'security_level': lvl}
    )
    
    status = 'Created' if created else 'Updated'
    print(f'✅ {status}: {username} -> {dept} (Lvl {lvl})')
"

echo "--- SETUP COMPLETE ---"
echo "Starting Server..."
exec "$@"