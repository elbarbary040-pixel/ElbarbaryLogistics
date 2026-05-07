from django import forms

from .models import Merchant, MerchantPayment


class MerchantForm(forms.ModelForm):
    class Meta:
        model = Merchant
        fields = ["name", "phone", "address", "brand_name", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
            "brand_name": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class MerchantPaymentForm(forms.ModelForm):
    class Meta:
        model = MerchantPayment
        fields = ["payment_date", "direction", "amount", "notes"]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "direction": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "notes": forms.TextInput(attrs={"class": "form-control"}),
        }

