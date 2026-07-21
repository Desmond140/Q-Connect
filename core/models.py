from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User # Or your custom User model if you use one

RESIDENCE_CHOICES = [
    ('qwetu_chiromo', 'Qwetu Chiromo'),
    ('qejani_chiromo', 'Qejani Chiromo'),
    ('qwetu_jogoo', 'Qwetu Jogoo Road'),
    ('qwetu_ruaraka', 'Qwetu Ruaraka'),
    ('qwetu_parklands', 'Qwetu Parklands'),
    ('qwetu_hurlingham', 'Qwetu Hurlingham'),
    ('qejani_hurlingham', 'Qejani Hurlingham'),
    ('qwetu_karen', 'Qwetu Karen'),
    ('qejani_karen', 'Qejani Karen'),
]

GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
]

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    has_paid_chat_fee = models.BooleanField(default=False)
    bio = models.TextField(max_length=500, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    interested_in = models.CharField(max_length=1, choices=GENDER_CHOICES)
    residence = models.CharField(max_length=30, choices=RESIDENCE_CHOICES)
    university = models.CharField(max_length=100, help_text="e.g. UoN, Strathmore, JKUAT")
    profile_pic = models.ImageField(upload_to='profile_pics/', default='default.jpg')
    instagram_handle = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Match(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_likes')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_likes')
    is_liked = models.BooleanField(default=True) # True = like, False = dislike/skip
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Use getattr to prevent errors if a profile somehow wasn't created
    if hasattr(instance, 'profile'):
        instance.profile.save()

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender.username} to {self.receiver.username}: {self.content[:20]}"


class MpesaTransaction(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mpesa_transactions')
    checkout_request_id = models.CharField(max_length=100, unique=True, db_index=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, null=True) # Populated on success callback
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.checkout_request_id} ({self.status})"