from rest_framework import serializers
from website.models import LearningSession, Interaction


class InteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interaction
        fields = ["id", "action", "details", "timestamp"]


class SessionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningSession
        fields = ["id", "start_time", "end_time"]


class SessionDetailSerializer(serializers.ModelSerializer):
    interactions = serializers.SerializerMethodField()

    class Meta:
        model = LearningSession
        fields = ["id", "start_time", "end_time", "interactions"]

    def get_interactions(self, obj):
        interactions = Interaction.objects.filter(
            user=obj.user, timestamp__gte=obj.start_time
        )
        if obj.end_time:
            interactions = interactions.filter(timestamp__lte=obj.end_time)
        return InteractionSerializer(interactions, many=True).data