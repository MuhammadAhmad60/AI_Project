from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
from pytube import YouTube
from pytube.exceptions import PytubeError
import os
import assemblyai as aai
import openai
from .models import BlogPost
import re
import os
# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data.get('link') # type: ignore
            if not yt_link:
                return JsonResponse({'error': 'No Youtube link provided'}, status=400)
            print(f"Recived Youtube link: {yt_link}")
        except (KeyError, json.JSONDecodeError) as e:
            print(f"Error parsing JSON: {e}") # Log the error
            return JsonResponse({'error': 'Invalid data sent'}, status=400)
        
        # get yt tiltle
        try:
            title = yt_title(yt_link)
        except PytubeError as e:
            print(f"Error fetching Youtube title: {e}")
        if title == "Unknown Title":
            return JsonResponse({'error': 'Failed to fetch YouTube title'}, status=500)


        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': "Faild to get transcript"}, status=500)

        # use openAI to generate the blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error': "Faild to generate blog article"}, status=500)

        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        response_data = {'content': blog_content}
        print(f"Response data: {response_data}")

        # return blog article as a response
        return JsonResponse({'content': blog_content})
        
        
    else:
        return JsonResponse({'error': 'Invalid request method '}, status=405)
    
def is_valid_youtube_url(url):
    regex = r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.*(?:v|e(?:mbed)?)\/([A-Za-z0-9_-]+)"
    return bool(re.match(regex, url))

def yt_title(link):
    if not is_valid_youtube_url(link):
        return "Invalid Youtube URL"
    try: 
        yt = YouTube(link)
        title = yt.title
        return title
    except PytubeError as e:
        #Log the error to the console for debugging
        print(f"Error fetching YouTube title for {link}: {e}")
        return "Unknown Title" # You can return a default title or an error message
    



def download_audio(link):
    try:
        yt = YouTube(link)
        video = yt.streams.filter(only_audio=True).first()
        if video is None:
            raise Exception("No audio stream found.")
        out_file = video.download(output_path=settings.MEDIA_ROOT)
        base, ext = os.path.splitext(out_file)
        new_file = base + '.mp3'
        os.rename(out_file, new_file)
        file_size = os.path.getsize(new_file)
        print(f"File size: {file_size / (1024 * 1024):.2f} MB")
        if file_size > 100 * 1024 * 1024:
            raise Exception("Audio file exceeds size limit.")
        return new_file
    except PytubeError as e:
        print(f"Error downloading audio from YouTube: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error while downloading audio: {e}")
        return None



def get_transcription(link):
    # audio_file
    audio_file = download_audio(link)
    if not audio_file:
        print(f"Failed to download audio for video: {link}")
    aai.settings.api_key = "your api "

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    return transcript.text

def generate_blog_from_transcription(transcription):
    openai.api_key ="your api key "

    prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article:\n\n{transcription}\n\nArticle:"

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt = prompt,
        max_tokens=1000
    )

    generated_content = response.choices[0].text.strip()

    return generated_content

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')
    

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']


        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_massage = "Invalid username or password"
            return render(request, 'login.html', {'error_massage': error_massage})



    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email =request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_massage = 'Error creating account'

        else:
            error_massage = 'Password do not match'
            return render(request, 'signup.html', {'error_massage':error_massage})
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')