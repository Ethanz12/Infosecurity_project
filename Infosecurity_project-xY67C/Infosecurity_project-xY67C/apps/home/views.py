from django.http import HttpResponse

def index(request):
    return HttpResponse("<h1>Welcome to SecureGov Web App!</h1>")
