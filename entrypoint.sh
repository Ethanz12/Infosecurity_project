#!/bin/bash
# Wait for MySQL to be ready
echo "Waiting for MySQL..."
until mysqladmin ping -h "$MYSQL_HOST" --silent; do
  sleep 2
done

echo "MySQL is up! Running migrations..."
python manage.py migrate --noinput

# Execute the CMD from Dockerfile (Gunicorn)
exec "$@"
