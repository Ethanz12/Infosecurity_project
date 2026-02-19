# apps/home/s3_user_backup.py

import boto3
import json
import logging
from django.conf import settings
from django.utils import timezone
from botocore.exceptions import ClientError
from .models import CitizenProfile
from security.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)


class UserDataBackup:
    """
    Backup and restore user account information to/from S3
    """
    
    def __init__(self):
        """Initialize S3 client"""
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME
    
    def backup_user_profile(self, user):
        """
        Backup a single user's profile to S3
        
        Args:
            user: Django User object
            
        Returns:
            dict: {'success': bool, 's3_key': str, 'message': str}
        """
        try:
            profile = CitizenProfile.objects.get(user=user)
            
            # Prepare user data (keep encrypted fields encrypted)
            user_data = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                
                # Profile data (encrypted fields stay encrypted)
                'profile': {
                    'encrypted_nric': profile.encrypted_nric,
                    'encrypted_address': profile.encrypted_address,
                    'encrypted_phone': profile.encrypted_phone,
                    'blood_type': profile.blood_type,
                    'dental_stuff': profile.dental_stuff,
                    'two_factor_enabled': profile.two_factor_enabled,
                    'created_at': profile.created_at.isoformat(),
                    'updated_at': profile.updated_at.isoformat(),
                },
                
                # Metadata
                'backup_timestamp': timezone.now().isoformat(),
                'backup_version': '1.0'
            }
            
            # Convert to JSON
            json_data = json.dumps(user_data, indent=2)
            
            # S3 key structure: user-backups/{username}/{timestamp}.json
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            s3_key = f"user-backups/{user.username}/{timestamp}.json"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=json_data.encode('utf-8'),
                ContentType='application/json',
                Metadata={
                    'user-id': str(user.id),
                    'username': user.username,
                    'backup-date': timezone.now().isoformat()
                }
            )
            
            logger.info(f"✅ User profile backed up to S3: {s3_key}")
            
            return {
                'success': True,
                's3_key': s3_key,
                'message': f'Profile backed up successfully to {s3_key}'
            }
            
        except CitizenProfile.DoesNotExist:
            logger.error(f"No profile found for user {user.username}")
            return {
                'success': False,
                's3_key': None,
                'message': 'User profile not found'
            }
            
        except ClientError as e:
            logger.error(f"S3 upload error for user {user.username}: {e}")
            return {
                'success': False,
                's3_key': None,
                'message': f'S3 upload failed: {str(e)}'
            }
            
        except Exception as e:
            logger.error(f"Backup error for user {user.username}: {e}")
            return {
                'success': False,
                's3_key': None,
                'message': f'Backup failed: {str(e)}'
            }
    
    def restore_user_profile(self, s3_key):
        """
        Restore a user profile from S3 backup
        
        Args:
            s3_key: S3 key path to the backup file
            
        Returns:
            dict: {'success': bool, 'user': User object or None, 'message': str}
        """
        try:
            # Download from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=s3_key
            )
            
            backup_data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Import here to avoid circular imports
            from django.contrib.auth.models import User
            
            # Get or create user
            user, created = User.objects.get_or_create(
                username=backup_data['username'],
                defaults={
                    'email': backup_data['email'],
                    'first_name': backup_data['first_name'],
                    'last_name': backup_data['last_name'],
                    'is_staff': backup_data['is_staff'],
                    'is_active': backup_data['is_active'],
                }
            )
            
            # Update user if it already exists
            if not created:
                user.email = backup_data['email']
                user.first_name = backup_data['first_name']
                user.last_name = backup_data['last_name']
                user.is_staff = backup_data['is_staff']
                user.is_active = backup_data['is_active']
                user.save()
            
            # Get or create profile
            profile, _ = CitizenProfile.objects.get_or_create(user=user)
            
            # Restore profile data (encrypted fields remain encrypted)
            profile_data = backup_data['profile']
            profile.encrypted_nric = profile_data['encrypted_nric']
            profile.encrypted_address = profile_data['encrypted_address']
            profile.encrypted_phone = profile_data['encrypted_phone']
            profile.blood_type = profile_data.get('blood_type')
            profile.dental_stuff = profile_data.get('dental_stuff')
            profile.two_factor_enabled = profile_data.get('two_factor_enabled', False)
            profile.save()
            
            action = "Created" if created else "Restored"
            logger.info(f"✅ {action} user profile from S3 backup: {user.username}")
            
            return {
                'success': True,
                'user': user,
                'message': f'{action} user {user.username} from backup'
            }
            
        except ClientError as e:
            logger.error(f"S3 download error: {e}")
            return {
                'success': False,
                'user': None,
                'message': f'S3 download failed: {str(e)}'
            }
            
        except Exception as e:
            logger.error(f"Restore error: {e}")
            return {
                'success': False,
                'user': None,
                'message': f'Restore failed: {str(e)}'
            }
    
    def list_user_backups(self, username):
        """
        List all backup files for a specific user
        
        Args:
            username: str username
            
        Returns:
            list: List of backup metadata dicts
        """
        try:
            prefix = f"user-backups/{username}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            
            backups = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    backups.append({
                        's3_key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                    })
            
            return backups
            
        except ClientError as e:
            logger.error(f"Error listing backups for {username}: {e}")
            return []
    
    def backup_all_users(self):
        """
        Backup all user profiles to S3
        
        Returns:
            dict: {'success': int, 'failed': int, 'results': list}
        """
        from django.contrib.auth.models import User
        
        results = {
            'success': 0,
            'failed': 0,
            'results': []
        }
        
        users = User.objects.all()
        
        for user in users:
            result = self.backup_user_profile(user)
            
            if result['success']:
                results['success'] += 1
            else:
                results['failed'] += 1
            
            results['results'].append({
                'username': user.username,
                'success': result['success'],
                'message': result['message']
            })
        
        logger.info(f"Bulk backup completed: {results['success']} successful, {results['failed']} failed")
        
        return results
    
    def delete_old_backups(self, username, keep_last_n=5):
        """
        Delete old backups, keeping only the most recent N backups
        
        Args:
            username: str username
            keep_last_n: int number of backups to keep
            
        Returns:
            dict: {'deleted': int, 'kept': int}
        """
        try:
            backups = self.list_user_backups(username)
            
            if len(backups) <= keep_last_n:
                return {'deleted': 0, 'kept': len(backups)}
            
            # Sort by last modified (oldest first)
            backups.sort(key=lambda x: x['last_modified'])
            
            # Delete oldest backups
            to_delete = backups[:-keep_last_n]
            deleted = 0
            
            for backup in to_delete:
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket,
                        Key=backup['s3_key']
                    )
                    deleted += 1
                    logger.info(f"Deleted old backup: {backup['s3_key']}")
                except Exception as e:
                    logger.error(f"Failed to delete {backup['s3_key']}: {e}")
            
            return {'deleted': deleted, 'kept': keep_last_n}
            
        except Exception as e:
            logger.error(f"Error cleaning up backups for {username}: {e}")
            return {'deleted': 0, 'kept': 0}


# Convenience functions
def backup_user(user):
    """Backup a single user's profile"""
    backup_service = UserDataBackup()
    return backup_service.backup_user_profile(user)


def restore_user(s3_key):
    """Restore a user from S3 backup"""
    backup_service = UserDataBackup()
    return backup_service.restore_user_profile(s3_key)


def list_backups(username):
    """List all backups for a user"""
    backup_service = UserDataBackup()
    return backup_service.list_user_backups(username)