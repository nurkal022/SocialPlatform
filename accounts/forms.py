from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class SignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=80, required=True, label="Аты")
    last_name = forms.CharField(max_length=80, required=True, label="Тегі")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "password1", "password2")


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Логин")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "first_name", "last_name", "avatar", "bio",
            "university", "region", "specialty", "year_of_study",
            "locale", "is_profile_public",
        )
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }
