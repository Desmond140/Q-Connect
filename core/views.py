import json
import re
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django_daraja.mpesa.core import MpesaClient

from .forms import ProfileEditForm, StudentRegistrationForm
from .models import Match, Message, MpesaTransaction, Profile


# ==========================================
# DISCOVERY / HOME VIEW
# ==========================================
@login_required
def home(request):
    user_profile = request.user.profile

    # 1. Who has the current user already swiped on?
    already_swiped = Match.objects.filter(sender=request.user).values_list('receiver_id', flat=True)

    # 2. Try matching based on preferences
    potential_matches = Profile.objects.filter(
        gender=user_profile.interested_in,
        interested_in=user_profile.gender
    ).exclude(
        user=request.user
    ).exclude(
        user_id__in=already_swiped
    )

    # Fallback: If no preference match found, show ANY profile not yet swiped on
    if not potential_matches.exists():
        potential_matches = Profile.objects.exclude(
            user=request.user
        ).exclude(
            user_id__in=already_swiped
        )

    # Grab the first match for the deck card
    active_profile = potential_matches.first()

    return render(request, 'core/home.html', {
        'profile': active_profile
    })


@login_required
def like_user(request, user_id):
    if request.method == "POST":
        receiver_user = get_object_or_404(User, id=user_id)
        Match.objects.get_or_create(sender=request.user, receiver=receiver_user, is_liked=True)

        is_mutual = Match.objects.filter(sender=receiver_user, receiver=request.user, is_liked=True).exists()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'match': is_mutual})

    return redirect('home')


@login_required
def skip_user(request, user_id):
    if request.method == "POST":
        receiver_user = get_object_or_404(User, id=user_id)
        Match.objects.get_or_create(sender=request.user, receiver=receiver_user, is_liked=False)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})

    return redirect('home')


# ==========================================
# AUTH & PROFILE VIEWS
# ==========================================
def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = StudentRegistrationForm()

    return render(request, 'core/register.html', {'form': form})


def landing(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'core/landing.html')


@login_required
def matches_list(request):
    likes_sent = Match.objects.filter(
        sender=request.user,
        is_liked=True
    ).values_list('receiver_id', flat=True)

    likes_received = Match.objects.filter(
        receiver=request.user,
        is_liked=True
    ).values_list('sender_id', flat=True)

    mutual_user_ids = set(likes_sent).intersection(set(likes_received))
    mutual_matches = Profile.objects.filter(user_id__in=mutual_user_ids)

    return render(request, 'core/matches.html', {'profiles': mutual_matches})


@login_required
def edit_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = ProfileEditForm(instance=profile)

    return render(request, 'core/edit_profile.html', {'form': form})


# ==========================================
# CHAT ROOM VIEWS
# ==========================================
@login_required
def chat_room(request, username):
    profile = request.user.profile

    # Lock chat behind KES 100 Paywall
    if not profile.has_paid_chat_fee:
        return redirect('paywall')

    other_user = get_object_or_404(User, username=username)

    liked_by_me = Match.objects.filter(sender=request.user, receiver=other_user, is_liked=True).exists()
    liked_me_back = Match.objects.filter(sender=other_user, receiver=request.user, is_liked=True).exists()

    if not (liked_by_me and liked_me_back):
        return redirect('home')

    messages_qs = Message.objects.filter(
        (Q(sender=request.user) & Q(receiver=other_user)) |
        (Q(sender=other_user) & Q(receiver=request.user))
    ).order_by('timestamp')

    return render(request, 'core/chat.html', {
        'other_user': other_user,
        'chat_messages': messages_qs
    })


@login_required
def send_message(request, username):
    if request.method == "POST":
        other_user = get_object_or_404(User, username=username)
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
    other_user = get_object_or_404(User, username=username)

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
        msg.is_read = True
        msg.save()

    return JsonResponse({'messages': data})


# ==========================================
# M-PESA PAYWALL & CALLBACK VIEWS
# ==========================================
@login_required
def paywall_view(request):
    return render(request, 'core/paywall.html')


def format_phone_number(phone):
    cleaned = re.sub(r'\D', '', phone)
    if cleaned.startswith('0'):
        return '254' + cleaned[1:]
    elif cleaned.startswith('254'):
        return cleaned
    elif cleaned.startswith('+254'):
        return cleaned[1:]
    return cleaned


@login_required
def initiate_payment(request):
    if request.method == 'POST':
        raw_phone = request.POST.get('phone_number')

        if not raw_phone:
            messages.error(request, "Phone number is required.")
            return redirect('paywall')

        phone_number = format_phone_number(raw_phone)

        if len(phone_number) != 12:
            messages.error(request, "Invalid phone number format. Use 07XXXXXXXX or 2547XXXXXXXX.")
            return redirect('paywall')

        amount = 100
        account_reference = f"User_{request.user.username}"
        transaction_desc = "Unlock Q-Connect Chat Fee"

        callback_url = request.build_absolute_uri(reverse('mpesa_callback')).replace('http://', 'https://')
        cl = MpesaClient()

        try:
            response = cl.stk_push(
                phone_number=phone_number,
                amount=amount,
                account_reference=account_reference,
                transaction_desc=transaction_desc,
                callback_url=callback_url
            )

            response_code = getattr(response, 'response_code', None)
            checkout_request_id = getattr(response, 'checkout_request_id', None)
            merchant_request_id = getattr(response, 'merchant_request_id', None)

            if response_code == "0" and checkout_request_id:
                MpesaTransaction.objects.create(
                    user=request.user,
                    checkout_request_id=checkout_request_id,
                    merchant_request_id=merchant_request_id,
                    phone_number=phone_number,
                    amount=amount,
                    status='PENDING'
                )

                messages.success(request, "STK push sent! Enter your M-Pesa PIN on your phone.")
                return redirect('payment_processing', checkout_id=checkout_request_id)
            else:
                error_message = getattr(response, 'response_description', "Failed to trigger M-Pesa prompt.")
                messages.error(request, f"M-Pesa Error: {error_message}")

        except Exception as e:
            messages.error(request, f"System error: {str(e)}")

    return redirect('paywall')


@csrf_exempt
def mpesa_callback(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            stk_callback = payload.get('Body', {}).get('stkCallback', {})
            result_code = stk_callback.get('ResultCode')
            checkout_request_id = stk_callback.get('CheckoutRequestID')

            try:
                transaction = MpesaTransaction.objects.get(checkout_request_id=checkout_request_id)
            except MpesaTransaction.DoesNotExist:
                return JsonResponse({"ResultCode": 1, "ResultDesc": "Transaction record not found"})

            if result_code == 0:
                # 1. Update Transaction
                transaction.status = 'SUCCESS'

                # Extract M-Pesa Receipt
                metadata_items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                for item in metadata_items:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        transaction.mpesa_receipt_number = item.get('Value')

                transaction.save()

                # 2. Unlock User Chat
                profile = transaction.user.profile
                profile.has_paid_chat_fee = True
                profile.save()

                return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
            else:
                transaction.status = 'FAILED'
                transaction.save()
                return JsonResponse({"ResultCode": result_code, "ResultDesc": stk_callback.get('ResultDesc', 'Failed')})

        except Exception as e:
            return JsonResponse({"ResultCode": 1, "ResultDesc": f"System Error: {str(e)}"})

    return JsonResponse({"Error": "Method not allowed"}, status=405)


@login_required
def payment_processing(request, checkout_id):
    transaction = get_object_or_404(MpesaTransaction, checkout_request_id=checkout_id, user=request.user)

    if request.user.profile.has_paid_chat_fee:
        return redirect('matches')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': transaction.status,
            'has_paid': request.user.profile.has_paid_chat_fee
        })

    return render(request, 'core/processing.html', {'transaction': transaction})