from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000)
    session_id = serializers.IntegerField(required=False, allow_null=True)


class ChatResponseSerializer(serializers.Serializer):
    agent = serializers.CharField()
    response = serializers.CharField()
    session_id = serializers.IntegerField()
    message_id = serializers.IntegerField()