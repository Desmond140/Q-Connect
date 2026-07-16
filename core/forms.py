from django import forms
from django.contrib.auth.models import User
from .models import Profile, RESIDENCE_CHOICES, GENDER_CHOICES

# 1. STUDENT REGISTRATION FORM
class StudentRegistrationForm(forms.ModelForm):
    # User fields
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500',
        'placeholder': 'Choose a unique username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500',
        'placeholder': 'Enter a strong password'
    }))
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500',
        'placeholder': 'Your first name'
    }))

    # Profile fields
    gender = forms.ChoiceField(choices=GENDER_CHOICES, widget=forms.Select(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'
    }))
    interested_in = forms.ChoiceField(choices=GENDER_CHOICES, label="Interested In", widget=forms.Select(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'
    }))
    residence = forms.ChoiceField(choices=RESIDENCE_CHOICES, widget=forms.Select(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'
    }))
    university = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500',
        'placeholder': 'e.g. UoN, Strathmore, JKUAT'
    }))
    bio = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 rows-3',
        'placeholder': 'Tell us a bit about yourself...',
        'rows': 3
    }))
    profile_pic = forms.ImageField(required=False, widget=forms.FileInput(attrs={
        'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-red-50 file:text-red-700 hover:file:bg-red-100'
    }))

    class Meta:
        model = User
        fields = ['username', 'password', 'first_name']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            profile = user.profile
            profile.gender = self.cleaned_data['gender']
            profile.interested_in = self.cleaned_data['interested_in']
            profile.residence = self.cleaned_data['residence']
            profile.university = self.cleaned_data['university']
            profile.bio = self.cleaned_data['bio']
            if self.cleaned_data['profile_pic']:
                profile.profile_pic = self.cleaned_data['profile_pic']
            profile.save()
        return user


# 2. PROFILE EDIT FORM
class ProfileEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500',
    }))
    instagram_handle = forms.CharField(required=False, max_length=30, widget=forms.TextInput(attrs={
        'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500',
        'placeholder': 'Your Instagram username (without @)'
    }))

    class Meta:
        model = Profile
        fields = ['gender', 'interested_in', 'residence', 'university', 'bio', 'profile_pic', 'instagram_handle']
        widgets = {
            'gender': forms.Select(attrs={'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'}),
            'interested_in': forms.Select(attrs={'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'}),
            'residence': forms.Select(attrs={'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'}),
            'university': forms.TextInput(attrs={'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'}),
            'bio': forms.Textarea(attrs={'class': 'w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500', 'rows': 3}),
            'profile_pic': forms.FileInput(attrs={'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-red-50 file:text-red-700 hover:file:bg-red-100'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.save()
            user = profile.user
            user.first_name = self.cleaned_data['first_name']
            user.save()
        return profile