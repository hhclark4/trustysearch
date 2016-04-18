from django.db import models
from django.forms import ModelForm
from django import forms
from .models import Searcher

#Choices for rating
CHOICES = [(0, ""), (1,1), (2,2), (3,3), (4,4), (5,5),
			(6,6), (7,7), (8,8), (9,9), (10,10)]

#Form to get user login data
class UserForm(forms.Form):
    username = forms.CharField(label="Username", help_text="30 characters or fewer. Letters, digits and @/./+/-/_  only.")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)
    confirm_password = forms.CharField(label="Confirm Password", widget=forms.PasswordInput, help_text="Enter the same password as before, for verification.")

#Form to get initial user data
class SearcherForm(ModelForm):
	class Meta:
		model = Searcher
		fields = ['first_name', 'last_name']
		labels = {
		  'first_name': 'First Name',
		  'last_name': 'Last Name',
		}

#Form to get initial user ratings
class InitialRatingsForm(forms.Form):
	def __init__(self, *args, **kwargs):
		sources = kwargs.pop('sources')
		super(InitialRatingsForm, self).__init__(*args, **kwargs)
		counter = 1
		for s in sources:
			self.fields[str(counter)] = forms.ChoiceField(initial=0,
				choices=CHOICES, required=False, label=s)
			counter += 1

#Form to get updated ratings from user
class UpdateRatingsForm(forms.Form):
	def __init__(self, *args, **kwargs):
		sources = kwargs.pop('sources')
		ratings = kwargs.pop('ratings')
		super(UpdateRatingsForm, self).__init__(*args, **kwargs)
		for i in range(0, len(sources)):
			self.fields[str(i+1)] = forms.ChoiceField(choices=CHOICES,
				required=False, label=sources[i])
			self.initial[str(i+1)] = ratings[i]

#Form to make and rate a new source
class NewSourceForm(forms.Form):
	name = forms.CharField(label='Source Name', max_length=250)
	site = forms.URLField(label="URL", max_length=250)
	rating = forms.ChoiceField(initial=0,
		choices=CHOICES, required=False, label="Rating")

#Form to get search terms
class SearchForm(forms.Form):
	search = forms.CharField(label='Search', max_length=1000)

