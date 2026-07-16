from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import models
from .models import Profile, Match
from django.db.models import Q
from .forms import ProfileEditForm
from django.contrib.auth import login
from .forms import StudentRegistrationForm
from django.http import JsonResponse
from django.http import JsonResponse
from django.db.models import Q
from .models import Message


@login_required
def home(request):
    user_profile = request.user.profile

    # 1. Find who this user has already swiped on (liked or skipped)
    already_swiped = Match.objects.filter(sender=request.user).values_list('receiver_id', flat=True)

    # 2. Query potential matches matching preferences who haven't been swiped on yet
    potential_matches = Profile.objects.filter(
        gender=user_profile.interested_in,
        interested_in=user_profile.gender
    ).exclude(
        user=request.user
    ).exclude(
        user_id__in=already_swiped
    )

    # 3. Grab ONLY the first match to show on the deck
    active_profile = potential_matches.first()

    # 4. Pass it to the template as 'profile'
    return render(request, 'core/home.html', {
        'profile': active_profile  # <-- MUST match the singular variable in your HTML!
    })

@login_required
def like_user(request, user_id):
    if request.method == "POST":
        receiver_user = User.objects.get(id=user_id)
        Match.objects.get_or_create(sender=request.user, receiver=receiver_user, is_liked=True)

        # Check for immediate mutual match back
        is_mutual = Match.objects.filter(sender=receiver_user, receiver=request.user, is_liked=True).exists()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'match': is_mutual})

    return redirect('home')


@login_required
def skip_user(request, user_id):
    if request.method == "POST":
        receiver_user = User.objects.get(id=user_id)
        Match.objects.get_or_create(sender=request.user, receiver=receiver_user, is_liked=False)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})

    return redirect('home')


def register(request):
    if request.user.is_authenticated:
        return redirect('home')  # Already logged in? Redirect home.

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Automatically log in the new student
            return redirect('home')
    else:
        form = StudentRegistrationForm()

    return render(request, 'core/register.html', {'form': form})

def landing(request):
    if request.user.is_authenticated:
        return redirect('home')  # Already logged in? Jump straight to swiping!
    return render(request, 'core/landing.html')


@login_required
def matches_list(request):
    # 1. Get IDs of profiles you liked
    likes_sent = Match.objects.filter(
        sender=request.user,
        is_liked=True
    ).values_list('receiver_id', flat=True)

    # 2. Get IDs of profiles who liked you back
    likes_received = Match.objects.filter(
        receiver=request.user,
        is_liked=True
    ).values_list('sender_id', flat=True)

    # 3. Find the overlap (mutual matches!)
    mutual_user_ids = set(likes_sent).intersection(set(likes_received))

    # 4. Fetch the Profiles of those mutual matches
    mutual_matches = Profile.objects.filter(user_id__in=mutual_user_ids)

    return render(request, 'core/matches.html', {'profiles': mutual_matches})





@login_required
def edit_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('home')  # Send them back to swiping with their fresh profile
    else:
        form = ProfileEditForm(instance=profile)

    return render(request, 'core/edit_profile.html', {'form': form})





@login_required
def chat_room(request, username):
    other_user = User.objects.get(username=username)

    # Verify that these two users are actually a mutual match before letting them chat
    liked_by_me = Match.objects.filter(sender=request.user, receiver=other_user, is_liked=True).exists()
    liked_me_back = Match.objects.filter(sender=other_user, receiver=request.user, is_liked=True).exists()

    if not (liked_by_me and liked_me_back):
        return redirect('home')  # Not a match? Kicked back to discover!

    # Fetch existing conversation history
    messages = Message.objects.filter(
        (Q(sender=request.user) & Q(receiver=other_user)) |
        (Q(sender=other_user) & Q(receiver=request.user))
    ).order_by('timestamp')

    return render(request, 'core/chat.html', {
        'other_user': other_user,
        'chat_messages': messages
    })


@login_required
def send_message(request, username):
    if request.method == "POST":
        other_user = User.objects.get(username=username)
        content = request.POST.get('content', '').strip()

        if content:
            msg = Message.objects.create(
                sender=request.user,
                receiver=other_user,
                content=content
            )
            return JsonResponse({
                'status': 'success',
                'content': msg.content,
                'timestamp': msg.timestamp.strftime('%H:%M')
            })

    return JsonResponse({'status': 'error'}, status=400)


@login_required
def get_messages(request, username):
    other_user = User.objects.get(username=username)

    # Grab any messages from the other user that are still unread
    unread_messages = Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False
    )

    data = []
    for msg in unread_messages:
        data.append({
            'id': msg.id,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%H:%M')
        })
        # Mark them as read now that we are delivering them
        msg.is_read = True
        msg.save()

    return JsonResponse({'messages': data})