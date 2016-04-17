from django.conf.urls import url
from django.contrib.auth.views import login, logout, password_change, password_change_done

from . import views

urlpatterns = [
	#Start Page
    url(r'^$', views.start, name='start'),
    #Login
    url(r'^login/$', login, 
    	{'template_name': 'registration/login.html', 'extra_context':
    	{'next': '/account/home'}}, name='login'),
    # Logout
	url(r'^logout/$', logout,
		{'template_name': 'registration/logout.html', 'extra_context': {}}, name='logout'),
	# Password change page
	url(r'^password_change/$', password_change,
		{'template_name': 'registration/password_change.html',
		'post_change_redirect': 'search:password_change_done', 'extra_context': {}},
		name='password_change'),
	url(r'^password_change/done/$', password_change_done,
		{'template_name': 'registration/password_change_done.html', 'extra_context': {}},
		name='password_change_done'),
    #Get New User Info
    url(r'^registration/info/$', views.get_new_user_info, name='new_user_info'),
    #Get new user's initial preferences
    url(r'^registration/ratings/$', views.initial_ratings, name='initial_ratings'),
    #User Home/Profile
    url(r'^account/home/$', views.user_home, name='user_home'),
    #Edit user profile
    url(r'^account/update/$', views.update_account, name='update_account'),
    #Set or change rating preferences
    url(r'^account/update/ratings/$', views.update_ratings, name='ratings'),
    #Search
    url(r'^search/$', views.search, name='search')
]