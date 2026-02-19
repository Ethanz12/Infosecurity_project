# apps/home/management/commands/backup_users.py

from django.core.management.base import BaseCommand
from apps.home.s3_user_backup import UserDataBackup


class Command(BaseCommand):
    help = 'Backup all user profiles to S3'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Backup only a specific user (optional)',
        )
        
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up old backups, keeping only the last 5',
        )

    def handle(self, *args, **options):
        backup_service = UserDataBackup()
        
        username = options.get('username')
        cleanup = options.get('cleanup')
        
        if username:
            # Backup single user
            from django.contrib.auth.models import User
            
            try:
                user = User.objects.get(username=username)
                result = backup_service.backup_user_profile(user)
                
                if result['success']:
                    self.stdout.write(self.style.SUCCESS(f"✅ {result['message']}"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ {result['message']}"))
                    
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ User '{username}' not found"))
                
        else:
            # Backup all users
            self.stdout.write("Starting bulk user backup...")
            results = backup_service.backup_all_users()
            
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Backup completed: {results['success']} successful, {results['failed']} failed"
            ))
            
            # Show details
            for result in results['results']:
                status = "✅" if result['success'] else "❌"
                self.stdout.write(f"  {status} {result['username']}: {result['message']}")
        
        # Optional cleanup
        if cleanup:
            self.stdout.write("\nCleaning up old backups...")
            
            from django.contrib.auth.models import User
            users = User.objects.all() if not username else [User.objects.get(username=username)]
            
            total_deleted = 0
            for user in users:
                result = backup_service.delete_old_backups(user.username, keep_last_n=5)
                total_deleted += result['deleted']
                
                if result['deleted'] > 0:
                    self.stdout.write(
                        f"  🗑️  {user.username}: Deleted {result['deleted']} old backups"
                    )
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ Cleanup completed: {total_deleted} old backups deleted"))
