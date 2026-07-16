from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

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