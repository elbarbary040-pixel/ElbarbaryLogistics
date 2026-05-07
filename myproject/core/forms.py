from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm

from .models import OrderRequest, SiteAppearance, UserProfile, UserRole


User = get_user_model()


class SiteAppearanceForm(forms.ModelForm):
    class Meta:
        model = SiteAppearance
        fields = ["logo", "primary_color", "accent_color", "sidebar_color"]
        widgets = {
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "primary_color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
            "accent_color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
            "sidebar_color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
        }


class UserProfileRoleForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["role", "phone", "notes"]
        widgets = {
            "role": forms.Select(attrs={"class": "form-select"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class UserCreateForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    role = forms.ChoiceField(
        choices=UserRole.choices,
        initial=UserRole.USER,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_staff = forms.BooleanField(required=False, initial=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    is_active = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    def clean(self):
        cleaned = super().clean() or {}
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "كلمتا المرور غير متطابقتين.")
        return cleaned

    def save(self):
        create_user = getattr(User.objects, "create_user")
        user = create_user(username=self.cleaned_data["username"], password=self.cleaned_data["password1"])
        user.first_name = (self.cleaned_data.get("first_name") or "").strip()
        user.last_name = (self.cleaned_data.get("last_name") or "").strip()
        user.email = (self.cleaned_data.get("email") or "").strip()
        user.is_staff = bool(self.cleaned_data.get("is_staff"))
        user.is_active = bool(self.cleaned_data.get("is_active"))
        user.save(update_fields=["first_name", "last_name", "email", "is_staff", "is_active"])
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "is_staff", "is_active"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "is_staff": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class UserSuperuserForm(forms.ModelForm):
    """سوبر أدمن فقط — لتجنب قفل النظام بالخطأ."""

    class Meta:
        model = User
        fields = ["is_superuser"]
        widgets = {
            "is_superuser": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AdminSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
        }


class ProfilePasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class OrderRequestEditForm(forms.ModelForm):
    class Meta:
        model = OrderRequest
        fields = [
            "merchant",
            "customer_name",
            "customer_phone",
            "customer_address",
            "product_price",
            "shipping_price",
            "notes",
        ]
        widgets = {
            "merchant": forms.Select(attrs={"class": "form-select"}),
            "customer_name": forms.TextInput(attrs={"class": "form-control"}),
            "customer_phone": forms.TextInput(attrs={"class": "form-control"}),
            "customer_address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "product_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "shipping_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

