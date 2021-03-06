import pprint
import json
import urllib2
import urllib
from urlparse import urlparse
from operator import itemgetter

from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from googleapiclient.discovery import build

from .forms import *
from .models import Searcher, Source

# Number of top sites to display for initial ratings
TOP_SITES_COUNT = 15
# Number of ratings needed to qualify as a top rating
RATINGS_THRESHOLD = 10
# Number of results per page
RESULTS_PER_PAGE = 3

# Application Start Page
def start(request):
	return render(request, 'search/start.html', {})

# Application About Page
def about(request):
	return render(request, 'search/about.html', {})

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
			if '_web' in request.POST:
				searchType = 'web'
			else:
				searchType = 'news'
			return search_results(request, searchType)

	form = SearchForm()
	context = {
		'form': form,
	}
	return render(request, 'search/search.html', context)

# Perform the user's search
def process_search(request, search, searchType):
	searcher = Searcher.objects.get(user=request.user)
	preferences = json.loads(searcher.preferences)

	keyBing = 'mqIg+kglN9vuB1eIoOp0AHSIQlm+K09P9u6E/fWdD74'
	credentialBing = 'Basic ' + (':%s' % keyBing).encode('base64')[:-1]
	query = "'{0}'".format(search)
	query = urllib.quote_plus(query)
	top = RESULTS_PER_PAGE
	offset = 0
	'''
	if searchType == 'web':
		url = 'https://api.datamarket.azure.com/Bing/Search/Web?' + \
		'Query=%s&$top=%d&$skip=%d&$format=json' % (query, top, offset)
	else:
		url = 'https://api.datamarket.azure.com/Bing/Search/News?' + \
		'Query=%s&$top=%d&$skip=%d&$format=json' % (query, top, offset)

	request = urllib2.Request(url)
	request.add_header('Authorization', credentialBing)
	requestOpener = urllib2.build_opener()
	response = requestOpener.open(request) 

	results = json.load(response)
	'''
	results = {u'd': {u'results': [{u'Description': u'On a break during a business trip to Washington last year, David Panton hailed a cab to take him to the Capitol. He told the driver he was going to see the Texas senator and presidential candidate Ted Cruz. \u201cHe\u2019s racist,\u201d the cabdriver replied ...', u'Title': u'In College Roommate David Panton, Ted Cruz Finds Unwavering Support', u'Url': u'http://www.nytimes.com/2016/04/24/us/politics/ted-cruz-college-roommate.html', u'__metadata': {u'type': u'NewsResult', u'uri': u"https://api.datamarket.azure.com/Data.ashx/Bing/Search/News?Query='ted cruz'&$skip=0&$top=1"}, u'Source': u'New York Times', u'Date': u'2016-04-23T22:18:02Z', u'ID': u'4190bb6c-d831-40a7-97e5-db6545d5bf26'}, {u'Description': u'AUSTIN, Texas (AP) \u2013 When Ted Cruz kicked off his White House bid at Liberty University, he told the crowd "y\'all can probably relate" to the $100,000-plus in student loan debt he ran up in college and paid off only a few years ago. Since then he\'s ...', u'Title': u"Student loan issues could be thorn in Ted Cruz's appeal to young voters", u'Url': u'http://latino.foxnews.com/latino/politics/2016/04/24/student-loan-issues-could-be-thorn-in-ted-cruz-appeal-to-young-voters/', u'__metadata': {u'type': u'NewsResult', u'uri': u"https://api.datamarket.azure.com/Data.ashx/Bing/Search/News?Query='ted cruz'&$skip=1&$top=1"}, u'Source': u'Latino  FOX News', u'Date': u'2016-04-24T17:16:12Z', u'ID': u'11442505-f9c7-4607-8581-7738a8f3d2af'}, {u'Description': u'Republican presidential candidate Ted Cruz is intensifying his attacks on chief rival Donald Trump, calling him a phony and liar who is betraying conservative voters. Over the course of Saturday at campaign stops in both Pennsylvania and Indiana, Cruz ...', u'Title': u"Ted Cruz: Trump Is \u2018Betraying Americans\u2019 Before He's Even Elected", u'Url': u'http://abcnews.go.com/Politics/ted-cruz-trump-betraying-americans-elected/story?id=38624204', u'__metadata': {u'type': u'NewsResult', u'uri': u"https://api.datamarket.azure.com/Data.ashx/Bing/Search/News?Query='ted cruz'&$skip=2&$top=1"}, u'Source': u'ABC News', u'Date': u'2016-04-23T08:13:21Z', u'ID': u'491e5b89-b1ad-4033-b1b9-aca6a958e502'}], u'__next': u"https://api.datamarket.azure.com/Data.ashx/Bing/Search/News?Query='ted%20cruz'&$skip=3&$top=3"}}
	sites = []
	for i in results['d']['results']:
		try:
			title = i['Title']
		except KeyError:
			title = "[No Title]"
		try:
			description = i['Description']
		except KeyError:
			description = "[No Description]"
		try:
			url = i['Url']
			display_url = i['Url'][:62] + "..."
		except KeyError:
			url = "[No Url]"

		domain = urlparse(url).netloc
		source = Source.objects.filter(website='http://' + domain)
		if source.count() == 0:
			rating = 0.0
		else:
			try:
				user_rating = int(preferences[source[0].display_name])
				rating = (source[0].avg_rating + user_rating) / 2
			except KeyError:
				rating = source[0].avg_rating

		sites.append((title, description, url, display_url, rating))

	sites.sort(key=lambda site: site[3], reverse=True)
  	return sites

'''
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
'''


# Show the search results
def search_results(request, searchType):
	if not request.user.is_authenticated():
		return HttpResponseRedirect('/login/')

	form = SearchForm(request.POST)
	if form.is_valid():
		search = form.cleaned_data['search']
		results = process_search(request, search, searchType)
		return render(request, 'search/search_results.html', 
			{'search_results': results,})

	form = SearchForm()
	context = {
		'form': form,
	}
	return render(request, 'search/search.html', context)
