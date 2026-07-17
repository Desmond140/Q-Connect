from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import models
from django.views.decorators.csrf import csrf_exempt

from .models import Profile, Match
from .forms import ProfileEditForm
from django.contrib.auth import login
from .forms import StudentRegistrationForm
from django.http import JsonResponse
from django.db.models import Q
from .models import Message
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
import re
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django_daraja.mpesa.core import MpesaClient
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
import re
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django_daraja.mpesa.core import MpesaClient
from .models import MpesaTransaction
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from .models import MpesaTransaction


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


@login_required
def chat_view(request, room_id):  # Or whatever arguments your current chat view takes
    # Get the user's profile
    profile = request.user.profile

    # If they haven't paid, send them to the payment page
    if not profile.has_paid_chat_fee:
        return redirect('paywall')  # We will create this view next

    # If they paid, let them proceed to the chat template
    return render(request, 'core/chat.html', {'room_id': room_id})

@login_required
def paywall_view(request):
    return render(request, 'core/paywall.html')


@login_required
def initiate_payment(request):
    if request.method == "POST":
        raw_phone = request.POST.get("phone_number")

        # Clean and format phone number to 254XXXXXXXXX (M-Pesa requirement)
        phone_number = re.sub(r'\D', '', raw_phone)  # remove non-digits
        if phone_number.startswith("0"):
            phone_number = "254" + phone_number[1:]
        elif phone_number.startswith("+254"):
            phone_number = phone_number[1:]
        elif not phone_number.startswith("254") and len(phone_number) == 9:
            phone_number = "254" + phone_number

        if len(phone_number) != 12:
            messages.error(request, "Invalid Safaricom phone number format. Use 07XXXXXXXX or 2547XXXXXXXX.")
            return redirect('paywall')

        # Generate the absolute callback URL so Safaricom knows where to send the payment receipt
        # e.g., https://yourdomain.com/mpesa-callback/
        callback_url = request.build_absolute_uri(reverse('mpesa_callback'))

        # We pass the user's ID as the Account Reference so we can identify them in the callback
        account_reference = f"USER-{request.user.id}"
        transaction_desc = "Unlock Q-Connect Chat Fee"
        amount = 100  # 100 KES

        cl = MpesaClient()
        response = cl.stk_push(phone_number, amount, account_reference, transaction_desc, callback_url)

        # Response checks
        if response.response_code == "0":
            messages.success(request,
                             "An M-Pesa prompt has been sent to your phone. Enter your PIN to complete the payment.")
        else:
            messages.error(request, f"Failed to initiate payment: {response.response_description}")

        return redirect('paywall')

    return redirect('paywall')






@csrf_exempt
def mpesa_callback(request):
    if request.method == 'POST':
        try:
            # Load the incoming payload from Safaricom
            payload = json.loads(request.body)

            # Navigate Safaricom's nested JSON structure
            stk_callback = payload.get('Body', {}).get('stkCallback', {})
            result_code = stk_callback.get('ResultCode')

            # ResultCode 0 means SUCCESS
            if result_code == 0:
                # Extract the Account Reference we sent earlier (e.g., "USER-5")
                # This lives under the CheckoutRequestID or Reference context.
                # Since the simplest way to track who paid is through the CallbackMetadata,
                # let's look for our user identification:

                # Retrieve custom account reference or match by transaction mapping.
                # Alternatively, you can use the checkout request ID if you log transactions.
                # For this simple flow, we can parse the User ID we sent in MerchantRequestID/CheckoutRequestID mapping,
                # but an even cleaner way in Daraja is utilizing the Metadata.

                # Safaricom returns items like Amount, ReceiptNumber, TransactionDate, PhoneNumber, etc.
                # We can map the user by looking up who initiated the payment.

                # If we saved the CheckoutRequestID in the database when initiating, we can query it:
                # To keep it bulletproof, let's parse the transaction status payload:
                metadata_items = stk_callback.get('CallbackMetadata', {}).get('Item', [])

                # Find details if you want to store them:
                amount = None
                mpesa_receipt_number = None
                for item in metadata_items:
                    if item.get('Name') == 'Amount':
                        amount = item.get('Value')
                    elif item.get('Name') == 'MpesaReceiptNumber':
                        mpesa_receipt_number = item.get('Value')

                # Find the user by parsing the original reference string Safaricom echo back
                # Or query against an active transaction database table.
                # Assuming you map CheckoutRequestID to a Transaction table:
                # (For simple sandbox direct simulation, we look up the pending transaction):

                # Note: Safaricom passes the User ID or AccountRef back as part of the transaction detail.
                # In standard setups, you save CheckoutRequestID to a "Payment" model when initiating,
                # then query: payment = Payment.objects.get(checkout_id=checkout_id) -> user = payment.user

                # Assuming you log the checkout request or pull user context:
                # For illustration, let's say we match the CheckoutRequestID:
                checkout_request_id = stk_callback.get('CheckoutRequestID')

                # Let's find the profile that initiated this request and unlock their chat:
                # (Make sure to create a Simple Payment record or query user profiles matches)

                # Shortcut directly querying:
                # (Make sure to log checkout_request_id to your user's profile or a Transaction model)
                # e.g., profile = Profile.objects.get(active_checkout_id=checkout_request_id)

                # For this guide, let's look up the user using a helper/transaction link:
                # profile.has_paid_chat_fee = True
                # profile.save()

                # Return 0 status to acknowledge Safaricom (very important!)
                return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})

            else:
                # Transaction failed or was cancelled by the user
                reason = stk_callback.get('ResultDesc', 'Failed')
                return JsonResponse({"ResultCode": result_code, "ResultDesc": reason})

        except Exception as e:
            # Always return a 200/OK-ish payload to Safaricom even if local logging fails,
            # otherwise they will retry sending the callback repeatedly.
            return JsonResponse({"ResultCode": 1, "ResultDesc": f"System Error: {str(e)}"})

    return JsonResponse({"Error": "Method not allowed"}, status=405)


def format_phone_number(phone):
    """
    Formats the user's phone input to Safaricom's required format: 2547XXXXXXXX
    """
    # Remove any non-numeric characters
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

        # Quick validation check for formatted number length
        if len(phone_number) != 12:
            messages.error(request, "Invalid Safaricom phone number format. Please use 07XXXXXXXX or 2547XXXXXXXX.")
            return redirect('paywall')

        amount = 100  # Matching the 100 KES badge on your HTML
        account_reference = f"User_{request.user.username}"
        transaction_desc = "Premium Dating Site Subscription"

        # Safaricom requires a secure HTTPS callback URL to return transaction status
        # In production, this uses your domain. For local development, you'll want to use ngrok.
        callback_url = request.build_absolute_uri(reverse('mpesa_callback')).replace('http://', 'https://')

        # Initialize the django-daraja client
        cl = MpesaClient()

        try:
            # Trigger the STK push
            response = cl.stk_push(
                phone_number=phone_number,
                amount=amount,
                account_reference=account_reference,
                transaction_desc=transaction_desc,
                callback_url=callback_url
            )

            # Read response details returned from Daraja API
            response_code = getattr(response, 'response_code', None)
            checkout_request_id = getattr(response, 'checkout_request_id', None)
            merchant_request_id = getattr(response, 'merchant_request_id', None)

            # ResponseCode "0" means Safaricom accepted the request and sent the STK push
            if response_code == "0" and checkout_request_id:
                # Save the mapping immediately
                MpesaTransaction.objects.create(
                    user=request.user,
                    checkout_request_id=checkout_request_id,
                    merchant_request_id=merchant_request_id,
                    phone_number=phone_number,
                    amount=amount,
                    status='PENDING'
                )

                messages.success(request, "STK push sent! Please check your phone to enter your M-Pesa PIN.")
                # Redirect user to a "waiting" or processing page
                return redirect('payment_processing', checkout_id=checkout_request_id)
            else:
                error_message = getattr(response, 'response_description',
                                        "Failed to trigger M-Pesa prompt. Please try again.")
                messages.error(request, f"M-Pesa Error: {error_message}")

        except Exception as e:
            messages.error(request, f"An unexpected system error occurred: {str(e)}")

    return redirect('paywall')


# core/views.py



@login_required
def payment_processing(request, checkout_id):
    transaction = get_object_or_404(MpesaTransaction, checkout_request_id=checkout_id, user=request.user)

    # If they hit this page but are already unlocked, take them to matches/chat
    if request.user.profile.has_paid_chat_fee:
        return redirect('matches')  # Or your chat URL name

    # If it's an AJAX request, check the current status and return JSON
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': transaction.status,
            'has_paid': request.user.profile.has_paid_chat_fee
        })

    return render(request, 'core/processing.html', {'transaction': transaction})