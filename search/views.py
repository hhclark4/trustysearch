import pprint
import json
from operator import itemgetter

from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from googleapiclient.discovery import build

from .forms import UserForm, SearcherForm, InitialRatingsForm, UpdateRatingsForm, NewSourceForm, SearchForm
from .models import Searcher, Source

# Number of top sites to display for initial ratings
TOP_SITES_COUNT = 15
# Number of ratings needed to qualify as a top rating
RATINGS_THRESHOLD = 10
# Number of Google CSE queries to run for a given search
NUM_QUERIES = 2

# Application Start Page
def start(request):
	return render(request, 'search/start.html', {})

# New User Information page
def get_new_user_info(request):
  error = 0

  if request.method == 'POST':
    form = SearcherForm(request.POST)
    if form.is_valid():
      first_name = form.cleaned_data['first_name']
      last_name = form.cleaned_data['last_name']
    else:
      error = "Be sure to fill in all of the fields!"

    form = UserForm(request.POST)
    if form.is_valid() and error == 0:
      username = form.cleaned_data['username']
      password = form.cleaned_data['password']

      if User.objects.filter(username=username).count() != 0:
        error = "The username you selected is already in use. Please choose a new one"
      elif password != form.cleaned_data['confirm_password']:
        error = "The passwords entered do not match"
      else:
        new_user = User.objects.create_user(username, email=None, password=password, first_name=first_name, 
          last_name=last_name)
        new_user.save()
        searcher = Searcher.objects.create(first_name=first_name, 
          last_name=last_name, user=new_user)
        searcher.save()
        user = authenticate(username=username, password=password)
        if user is not None:
          if user.is_active:
            login(request, user)
            return HttpResponseRedirect('/registration/ratings/')
          else:
            error = "An account for this user already exists, but it is deactivated"
        else:
          error = "There was a problem creating your account. Please try again"

    else:
      error = "Be sure to fill in all of the fields!"

  form = SearcherForm()
  form2 = UserForm()
  context = {
	'form': form,
	'form2': form2,
	'error': error,
  }
  return render(request, 'registration/info.html', context)

# Get user's initial ratings
def initial_ratings(request):
	if not request.user.is_authenticated():
		return HttpResponseRedirect('/login/')

	top_sources = Source.objects.filter(
		rating_count__gt=RATINGS_THRESHOLD).order_by('-rating_count')[:TOP_SITES_COUNT]
	sources = []
	for s in top_sources:
		sources.append(s.display_name)

	if request.method == 'POST':
		form = InitialRatingsForm(request.POST, sources=sources)
		if form.is_valid():
			initial_preferences = {}
			for field in form:
				source_name = field.label
				value = int(form.cleaned_data[field.name])
				source = Source.objects.get(display_name=source_name)
				total = source.avg_rating * source.rating_count + value
				source.rating_count += 1
				avg = total / source.rating_count
				source.avg_rating = avg
				source.save()
				initial_preferences[source_name] = value

			searcher = Searcher.objects.get(user=request.user)
			searcher.preferences = json.dumps(initial_preferences)
			searcher.save()
			return HttpResponseRedirect('/account/home/')

	form = InitialRatingsForm(request.POST, sources=sources)
	context = {
		'form': form,
	}
	return render(request, 'registration/ratings.html', context)

# User Home Page
def user_home(request):
	if not request.user.is_authenticated():
		return HttpResponseRedirect('/login/')

	context = {}
	return render(request, 'account/home.html', context)

# Edit user profile
def update_account(request):
	if not request.user.is_authenticated():
		return HttpResponseRedirect('/login/')

	return render(request, 'account/update_account.html', {})

# Set or change ratings preferences for a user
def update_ratings(request):
	if not request.user.is_authenticated():
		return HttpResponseRedirect('/login/')

	searcher = Searcher.objects.get(user=request.user)
	preferences = json.loads(searcher.preferences)
	sources = []
	ratings = []
	for i in preferences:
		sources.append(i)
		ratings.append(preferences[i])

	if request.method == 'POST':
		if 'update' in request.POST:
			print "UPDATING"
			form = UpdateRatingsForm(request.POST, sources=sources, ratings=ratings)
			if form.is_valid():
				new_preferences = {}
				for field in form:
					source_name = sources[int(field.name)-1]
					new_rating = form.cleaned_data[field.name]
					new_preferences[source_name] = new_rating
					source = Source.objects.get(display_name=source_name)
					total = source.rating_count * source.avg_rating
					total = total - int(ratings[int(field.name)-1]) + int(new_rating)
					source.avg_rating = total / source.rating_count
					source.save()

			searcher.preferences = json.dumps(new_preferences)
			searcher.save()

		elif 'new' in request.POST:
			form = NewSourceForm(request.POST)
			if form.is_valid():
				source_name = form.cleaned_data['name']
				source_url = form.cleaned_data['site']
				rating = int(form.cleaned_data['rating'])
				source = Source.objects.filter(display_name=source_name)
				if source.count() == 0:
					source = Source.objects.create(display_name=source_name,
						rating_count=1, avg_rating=rating, website=source_url)
					source.save()
				else:
					source = source[0]
					avg = float(source.avg_rating)
					count = int(source.rating_count)
					total = avg * count
					count += 1
					new_avg = (total + rating) / count
					source.avg_rating = new_avg
					source.rating_count = count
					source.save()

	form = NewSourceForm()
	form2 = UpdateRatingsForm(request.POST, sources=sources, ratings=ratings)
	context = {
		'form': form,
		'form2': form2,
	}
	return render(request, 'account/update/update_ratings.html', context)

# Search page
def search(request):
	if not request.user.is_authenticated():
		return HttpResponseRedirect('/login/')

	if request.method == 'POST':
		form = SearchForm(request.POST)
		if form.is_valid():
			return search_results(request)

	form = SearchForm()
	context = {
		'form': form,
	}
	return render(request, 'search/search.html', context)

# Perform the user's search
def process_search(request, search):
	service = build("customsearch", "v1",
        developerKey="AIzaSyB2skVifJVjjK3gmr5eIhp_GplvE35ZfNk")

	searcher = Searcher.objects.get(user=request.user)
	preferences = json.loads(searcher.preferences)
	sites = []
	for j in range(0, NUM_QUERIES):
  		res = service.cse().list(
      		q=search,
      		cx='003367144003658503028:zwa1v0ptuge',
      		num=10,
      		start=j*10+1,
    		).execute()
  		#pprint.pprint(res)

  		for i in res['items']:
  			try:
  				site_name = i['pagemap']['metatags'][0]['og:site_name']
  				title = i['title']
  				description = i['snippet']
  				url = i['link']
  				source = Source.objects.filter(display_name=site_name)
  				if source.count() == 0:
  					"no rating for this source"
  					rating = 0.0
  				else:
  					try:
  						user_rating = int(preferences[site_name])
  						rating = (source[0].avg_rating + user_rating) / 2
  					except KeyError:
  						print "No user rating for this site"
  						rating = source[0].avg_rating

  				sites.append((title, description, url, rating))
  			except KeyError:
  				print "No site name element for this site"

  	sites.sort(key=lambda site: site[3], reverse=True)
  	return sites


# Show the search results
def search_results(request):
	if not request.user.is_authenticated():
		return HttpResponseRedirect('/login/')

	form = SearchForm(request.POST)
	if form.is_valid():
		search = form.cleaned_data['search']
		results = process_search(request, search)
		return render(request, 'search/search_results.html', {'search_results': results,})

	form = SearchForm()
	context = {
		'form': form,
	}
	return render(request, 'search/search.html', context)
