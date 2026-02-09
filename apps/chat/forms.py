from django import forms

class SendMessageForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Type your message..."}),
        max_length=2000
    )
