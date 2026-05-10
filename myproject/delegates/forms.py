from django import forms

from .models import Delegate, DelegateDailyMetric, DelegateSettlementItem, DelegateTransaction


class DelegateForm(forms.ModelForm):
    class Meta:
        model = Delegate
        fields = ["name", "phone", "commission_rate", "fixed_deduction", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "commission_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "fixed_deduction": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class DelegateTransactionForm(forms.ModelForm):
    class Meta:
        model = DelegateTransaction
        fields = ["transaction_date", "tx_type", "direction", "amount", "notes"]
        widgets = {
            "transaction_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "tx_type": forms.Select(attrs={"class": "form-select"}),
            "direction": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "notes": forms.TextInput(attrs={"class": "form-control"}),
        }


class DelegateSettlementItemForm(forms.ModelForm):
    class Meta:
        model = DelegateSettlementItem
        fields = ["item_date", "title", "quantity", "unit_price", "kind"]
        widgets = {
            "item_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "kind": forms.Select(attrs={"class": "form-select"}),
        }


class DelegateDailyMetricForm(forms.ModelForm):
    class Meta:
        model = DelegateDailyMetric
        fields = ["advance_value", "total_value", "work_value", "cash_value", "net_value"]
        widgets = {
            "advance_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "total_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "work_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cash_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "net_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

