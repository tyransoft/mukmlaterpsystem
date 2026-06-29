from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import *



class LoginForm(forms.Form):
    username = forms.CharField(
        label='اسم المستخدم',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'أدخل اسم المستخدم', 'autofocus': True})
    )
    password = forms.CharField(
        label='كلمة المرور',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'أدخل كلمة المرور'})
    )


class UserCreateForm(UserCreationForm):
    role = forms.ChoiceField(label='الدور', choices=Role.choices, widget=forms.Select(attrs={'class': 'form-select'}))
    branch = forms.ModelChoiceField(
        label='الفرع', queryset=Branch.objects.filter(is_active=True),
        required=False, empty_label='-- اختر الفرع --',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'role', 'branch', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['password1'].label = 'كلمة المرور'
        self.fields['password2'].label = 'تأكيد كلمة المرور'


class UserEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [ 'role', 'branch', 'is_active']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'role': 'الدور',
            'branch': 'الفرع',
            'is_active': 'نشط',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['branch'].queryset = Branch.objects.filter(is_active=True)
        self.fields['branch'].required = False
        self.fields['branch'].empty_label = '-- لا فرع --'


class BranchInventoryForm(forms.ModelForm):
    class Meta:
        model = BranchInventory
        fields = ['branch', 'product', 'quantity', 'min_quantity']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
        labels = {
            'branch': 'الفرع', 'product': 'المنتج',
            'quantity': 'الكمية', 'min_quantity': 'الحد الأدنى للتنبيه',
        }


class InventoryAdjustForm(forms.Form):
    quantity = forms.IntegerField(
        label='الكمية الجديدة',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0'})
    )
    notes = forms.CharField(
        label='ملاحظات',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'address', 'phone', 'commission_percentage', 'is_main', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'commission_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'is_main': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'اسم الفرع',
            'address': 'العنوان',
            'phone': 'الهاتف',
            'commission_percentage': 'نسبة العمولة (%)',
            'is_main': 'الفرع الرئيسي',
            'is_active': 'نشط',
        }


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['customer_id','full_name', 'phone', 'address', 'is_active']
        widgets = {
            'customer_id': forms.TextInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'customer_id':'رقم العضوية',
            'full_name': 'الاسم الكامل',
            'phone': 'رقم الهاتف',
            'address': 'العنوان',
            'is_active': 'نشط',
        }

        
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name',  'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {'name': 'اسم الفئة', 'is_active': 'نشطة'}


class ProductForm(forms.ModelForm):

    class Meta:
        model = Product
        fields = ['name',  'barcode', 'category', 'cost_price', 'selling_price',
                 , 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'selling_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'اسم المنتج', 'code': 'الكود', 'barcode': 'الباركود',
            'category': 'الفئة', 'cost_price': 'سعر التكلفة', 'selling_price': 'سعر البيع',
            'is_active': 'نشط',
        }




class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name','is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),          
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'اسم المورد',
            'is_active': 'نشط',
        }


class PaymentMethodForm(forms.ModelForm):
    class Meta:
        model = PaymentMethod
        fields = ['name', 'increase_percentage', 'is_active', 'is_default']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: بطاقة ائتمان'}),
            'increase_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'اسم طريقة الدفع',
            'increase_percentage': 'نسبة الزيادة %',
            'is_active': 'نشط',
            'is_default': 'الطريقة الافتراضية',
        }        