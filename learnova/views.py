from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login,authenticate
from django.contrib import messages
from .forms import RegistrationForm, ProfileForm
from .models import Profile


def register(request):

    if request.method == 'POST':
        form = RegistrationForm(request.POST)

        if form.is_valid():

            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            Profile.objects.create(user=user)

            return redirect('home')

    else:
        form = RegistrationForm()

    return render(request, 'register.html', {
        'form': form
    })



def user_login(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            return redirect('home')

        else:

            messages.error(
                request,
                'Invalid username or password.'
            )

    return render(request, 'login.html')

def home(request):
    return render(request, 'home.html')


from django.contrib.auth.decorators import login_required


@login_required
def profile(request):

    profile = request.user.profile

    return render(request, 'profile.html', {
        'profile': profile
    })


# Edit Profile
@login_required
def edit_profile(request):

    profile = request.user.profile

    if request.method == 'POST':

        form = ProfileForm(
            request.POST,
            instance=profile
        )

        if form.is_valid():
            form.save()
            return redirect('profile')

    else:

        form = ProfileForm(
            instance=profile
        )

    return render(request, 'edit_profile.html', {
        'form': form
    })