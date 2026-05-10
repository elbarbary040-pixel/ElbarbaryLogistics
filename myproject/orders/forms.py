from django import forms

from core.models import Branch

from .models import Order


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            "order_date",
            "waybill_number",
            "external_waybill",
            "branch",
            "merchant",
            "delegate",
            "customer_name",
            "customer_phone",
            "customer_address",
            "shipping_price",
            "product_price",
            "status",
            "notes",
        ]
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "waybill_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "BRB12345"}),
            "external_waybill": forms.TextInput(attrs={"class": "form-control"}),
            "branch": forms.Select(attrs={"class": "form-select"}),
            "merchant": forms.Select(attrs={"class": "form-select js-search-select"}),
            "delegate": forms.Select(attrs={"class": "form-select js-search-select"}),
            "customer_name": forms.TextInput(attrs={"class": "form-control"}),
            "customer_phone": forms.TextInput(attrs={"class": "form-control"}),
            "customer_address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "shipping_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "product_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
        labels = {
            "order_date": "تاريخ الشحنة",
            "waybill_number": "رقم البوليصة (داخلي)",
            "external_waybill": "رقم بوليصة الوكيل",
            "branch": "الفرع (اختياري)",
            "merchant": "التاجر",
            "delegate": "المندوب",
            "customer_name": "اسم العميل",
            "customer_phone": "رقم العميل",
            "customer_address": "العنوان",
            "shipping_price": "سعر الشحن",
            "product_price": "سعر المنتج",
            "status": "الحالة",
            "notes": "ملاحظات",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["branch"].required = False
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True).order_by("name")

        self.fields["merchant"].required = True
        self.fields["delegate"].required = True


class OrderImportUploadForm(forms.Form):
    file = forms.FileField(
        label="ملف Excel (.xlsx)",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx", "class": "form-control"}),
    )


class OrderImportMappingForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)

    sheet_name = forms.ChoiceField(label="Sheet", choices=())

    waybill_number_col = forms.ChoiceField(label="رقم البوليصة", choices=())
    order_date_col = forms.ChoiceField(label="التاريخ", choices=())

    merchant_name_col = forms.ChoiceField(label="اسم التاجر", choices=())
    merchant_phone_col = forms.ChoiceField(label="رقم التاجر", choices=(), required=False)

    delegate_name_col = forms.ChoiceField(label="اسم المندوب", choices=())
    delegate_phone_col = forms.ChoiceField(label="رقم المندوب", choices=(), required=False)

    customer_name_col = forms.ChoiceField(label="اسم العميل", choices=())
    customer_phone_col = forms.ChoiceField(label="رقم العميل", choices=(), required=False)
    customer_address_col = forms.ChoiceField(label="العنوان", choices=(), required=False)

    shipping_price_col = forms.ChoiceField(label="سعر الشحن", choices=())
    product_price_col = forms.ChoiceField(label="سعر المنتج", choices=())

    notes_col = forms.ChoiceField(label="ملاحظات", choices=(), required=False)

    def __init__(self, *args, sheet_choices=(), column_choices=(), **kwargs):
        super().__init__(*args, **kwargs)

        sheet_field = self.fields["sheet_name"]
        if isinstance(sheet_field, forms.ChoiceField):
            sheet_field.choices = sheet_choices

        for field_name in self.fields:
            if field_name != "token" and field_name != "sheet_name":
                col_field = self.fields[field_name]
                if isinstance(col_field, forms.ChoiceField):
                    col_field.choices = column_choices

        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"