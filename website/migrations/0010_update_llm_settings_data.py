# Generated migration to update existing LLMSettings data

from django.db import migrations


def update_llm_settings(apps, schema_editor):
    LLMSettings = apps.get_model('website', 'LLMSettings')
    settings = LLMSettings.objects.first()
    if settings:
        # Update to correct Ollama URL and model
        if settings.ollama_base_url == 'http://localhost:11434':
            settings.ollama_base_url = 'http://ollama:12434'
        if settings.ollama_model == 'llama3':
            settings.ollama_model = 'llama3.2:1b'
        settings.save()


def reverse_llm_settings(apps, schema_editor):
    # Reverse migration - restore old values
    LLMSettings = apps.get_model('website', 'LLMSettings')
    settings = LLMSettings.objects.first()
    if settings:
        if settings.ollama_base_url == 'http://ollama:12434':
            settings.ollama_base_url = 'http://localhost:11434'
        if settings.ollama_model == 'llama3.2:1b':
            settings.ollama_model = 'llama3'
        settings.save()


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0009_update_llm_settings_defaults'),
    ]

    operations = [
        migrations.RunPython(update_llm_settings, reverse_llm_settings),
    ]
