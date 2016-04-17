from django.contrib import admin

from .models import Searcher
from .models import Source

admin.site.register(Searcher)
admin.site.register(Source)