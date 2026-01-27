from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('dashboard.api_urls')),  # ✅ This must point to api_urls.py
    path('', include('dashboard.urls')),          # Dashboard pages
    
]
