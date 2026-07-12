from .models import Notification

class NotificationService:
    @staticmethod
    def notify_user(user, title, description, category, icon=None, reference_id=None):
        """
        Creates a notification in the database.
        Prepares integration hooks for future FCM or push notification mechanisms.
        """
        notification = Notification.objects.create(
            user=user,
            title=title,
            description=description,
            category=category,
            icon=icon,
            reference_id=reference_id
        )
        
        # TODO: Trigger FCM push notification here in the future
        
        return notification

notification_service = NotificationService()
