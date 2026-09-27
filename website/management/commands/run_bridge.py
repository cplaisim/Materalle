"""
manage.py run_bridge
====================

Opens an outbound WebSocket to the AWS API Gateway relay and dispatches
incoming request envelopes to the local Django ASGI application.

Environment variables required:
  BRIDGE_WS_ENDPOINT     wss://<api-id>.execute-api.<region>.amazonaws.com/prod
  BRIDGE_BACKEND_SECRET  shared secret matching the Terraform var

Usage:
  python manage.py run_bridge
"""
import asyncio
import logging

from django.core.management.base import BaseCommand

from materalleapp.bridge.client import client_from_env


class Command(BaseCommand):
    help = "Run the persistent WebSocket bridge to the AWS relay."

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        client = client_from_env()
        self.stdout.write(self.style.SUCCESS(f"Bridge endpoint: {client.endpoint}"))
        try:
            asyncio.run(client.run_forever())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Bridge stopped by user."))
