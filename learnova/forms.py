from django import forms
from django.contrib.auth.models import User
from .models import Profile
from .models import StudyMaterial


class RegistrationForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data


class ProfileForm(forms.ModelForm):

    class Meta:
        model = Profile
        fields = ['phone', 'age', 'gender']



class StudyMaterialForm(forms.ModelForm):

    class Meta:
        model = StudyMaterial
        fields = [
            "title",
            "subject",
            "topic",
            "description",
            "pdf_file",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Enter material title"
            }),
            "subject": forms.TextInput(attrs={
                "placeholder": "Enter any subject"
            }),
            "topic": forms.TextInput(attrs={
                "placeholder": "Enter topic"
            }),
            "description": forms.Textarea(attrs={
                "placeholder": "Write a short description",
                "rows": 3
            }),
            "pdf_file": forms.ClearableFileInput(),
        }

    def clean_pdf_file(self):
        pdf = self.cleaned_data.get("pdf_file")

        if pdf:
            if not pdf.name.lower().endswith(".pdf"):
                raise forms.ValidationError(
                    "Only PDF files are allowed."
                )

            if pdf.size > 10 * 1024 * 1024:
                raise forms.ValidationError(
                    "The PDF must be smaller than 10 MB."
                )

        return pdf