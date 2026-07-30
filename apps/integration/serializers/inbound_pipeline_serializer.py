from rest_framework import serializers


class InboundPipelineSerializer(serializers.Serializer):
    pipeline_step = serializers.CharField(
        max_length=255,
        help_text="Pipeline step name as it exists in ConnectJob (e.g. 'Screening', 'Interview').",
    )
    pipeline_step_order = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Step order for disambiguation when multiple steps share the same name.",
    )
    pipeline_status = serializers.CharField(
        max_length=255,
        help_text="Pipeline status name (e.g. 'Scheduled', 'Passed').",
    )
    pipeline_status_order = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Status order for disambiguation.",
    )
