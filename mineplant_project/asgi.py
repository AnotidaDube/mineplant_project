#(project root)
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
import dashboard.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mineplant_project.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(
        dashboard.routing.websocket_urlpatterns
    ),
})
