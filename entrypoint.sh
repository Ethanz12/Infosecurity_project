#!/bin/bash
# -----------------------------
# entrypoint.sh
# -----------------------------
set -e

# 1️⃣ Check for FIELD_ENCRYPTION_KEY
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

echo "--- Checking spaCy NLP model ---"
python - <<'PYTHON'
try:
    import spacy
    spacy.load("en_core_web_sm")
    print("✅ spaCy model found")
except Exception as e:
    print(f"⚠️ spaCy model not available, NLP redaction disabled: {e}")
PYTHON

# 3️⃣ Migrations
echo "Generating missing migration files..."
# Ensure both apps get migrations
python manage.py makemigrations home
python manage.py makemigrations chat
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

# 3. Ensure Staff Accounts
try:
    StaffProfile = apps.get_model('home', 'StaffProfile')
except LookupError as e:
    print(f'❌ CRITICAL ERROR: Could not find StaffProfile model. Error: {e}')
    exit(1)

config = [
    ('HEALTH_USER', 'HEALTH_PASS', 'HEALTH', 1),
    ('FINANCE_USER', 'FINANCE_PASS', 'FINANCE', 2),
    ('GENERAL_USER', 'GENERAL_PASS', 'GENERAL', 1),
    ('HEALTH_USER1', 'HEALTH_PASS1', 'HEALTH', 2),
    ('HEALTH_USER2', 'HEALTH_PASS2', 'HEALTH', 2)
]

gov_group = Group.objects.get(name='GovernmentWorker')

print('--- Configuring Staff Accounts ---')
for u_var, p_var, dept, lvl in config:
    username = os.getenv(u_var)
    password = os.getenv(p_var)

    if not username or not password:
        print(f'⚠️  Skipping {dept}: {u_var} or {p_var} missing in .env')
        continue

    user, created = User.objects.get_or_create(username=username)
    user.set_password(password)
    user.email = f'{username}@gov.sg'
    user.is_staff = True
    user.groups.add(gov_group)
    user.save()

    StaffProfile.objects.update_or_create(
        user=user,
        defaults={'department': dept, 'security_level': lvl}
    )

    status = 'Created' if created else 'Updated'
    print(f'✅ {status}: {username} -> {dept} (Lvl {lvl})')

# 5️⃣ Test Chat Models (Create → Verify → Cleanup)
try:
    Conversation = apps.get_model('chat', 'Conversation')
    Message = apps.get_model('chat', 'Message')

    print('--- Running chat model self-test ---')

    # Create test users (marked clearly)
    test_user1, _ = User.objects.get_or_create(username='__testuser1__')
    test_user2, _ = User.objects.get_or_create(username='__testuser2__')

    # Create conversation
    conv = Conversation.objects.create()
    conv.participants.add(test_user1, test_user2)
    conv.save()

    # Create test message
    msg = Message(conversation=conv, sender=test_user1)
    msg.set_content('Hello World')
    msg.set_redacted_content('Hello [REDACTED]')
    msg.save()

    print('✅ Chat models test successful!')

    # -------------------------
    # CLEANUP (IMPORTANT PART)
    # -------------------------
    msg.delete()
    conv.delete()
    test_user1.delete()
    test_user2.delete()

    print('🧹 Chat test data cleaned up successfully.')

except Exception as e:
    print(f'❌ Chat models test failed: {e}')

"

echo "--- SETUP COMPLETE ---"

# 🆕 START CLAMAV DAEMON
echo "--- STARTING CLAMAV ---"
echo "Starting ClamAV daemon..."

# Start clamd as background process
/usr/sbin/clamd &

# Give it time to start
sleep 3

echo "--- CLAMAV READY ---"

echo "Starting Server..."
exec "$@"
