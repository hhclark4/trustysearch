from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField

#Model representing the profile of a user
class Searcher(models.Model):
	first_name = models.CharField(max_length=30)
	last_name = models.CharField(max_length=30)
	preferences = JSONField(default={})

	user = models.OneToOneField(
		User,
		on_delete=models.CASCADE,
		primary_key=True
	)

class Source(models.Model):
	display_name = models.CharField(max_length=250)
	website = models.URLField(max_length=250)
	rating_count = models.IntegerField()
	avg_rating = models.FloatField()