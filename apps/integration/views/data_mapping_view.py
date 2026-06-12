from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.core.exceptions.base_exceptions import BadRequestException, NotFoundException
from apps.integration.utils.mapping_utils import seed_default_field_mappings
from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import (
    IntegrationFieldMapping,
    IntegrationPartner,
    IntegrationValueMapping,
    MappingType,
)
from apps.integration.serializers.data_mapping_serializer import (
    IntegrationFieldMappingSerializer,
    IntegrationFieldMappingWriteSerializer,
    IntegrationValueMappingBulkSerializer,
    IntegrationValueMappingSerializer,
)


def _get_active_partner(company_id: str) -> IntegrationPartner:
    partner = IntegrationPartner.objects.filter(
        organization_id=company_id,
        status=ConnectorStatus.ACTIVE,
    ).first()
    if not partner:
        raise NotFoundException("No active integration found for this company.")
    return partner


def _get_field_mapping(pk, company_id: str) -> IntegrationFieldMapping:
    mapping = IntegrationFieldMapping.objects.filter(
        id=pk,
        partner__organization_id=company_id,
    ).first()
    if not mapping:
        raise NotFoundException("Field mapping not found.")
    return mapping


class DataMappingListView(CustomJWTRequestMixin, APIView):
    """
    GET  /api/v1/integration/data-mapping   — list all field mappings
    POST /api/v1/integration/data-mapping   — create a new field mapping
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = str(request.company_id)
        partner = _get_active_partner(company_id)
        mappings = (
            partner.field_mappings
            .prefetch_related("value_mappings")
            .order_by("source_field")
        )
        serializer = IntegrationFieldMappingSerializer(mappings, many=True)
        return Response({"data": serializer.data})

    def post(self, request):
        company_id = str(request.company_id)
        partner = _get_active_partner(company_id)
        serializer = IntegrationFieldMappingWriteSerializer(
            data=request.data,
            context={"partner": partner},
        )
        serializer.is_valid(raise_exception=True)
        mapping = serializer.save(partner=partner)
        return Response(
            IntegrationFieldMappingSerializer(mapping).data,
            status=status.HTTP_201_CREATED,
        )


class DataMappingDetailView(CustomJWTRequestMixin, APIView):
    """
    PATCH  /api/v1/integration/data-mapping/<id>  — update a field mapping
    DELETE /api/v1/integration/data-mapping/<id>  — remove a field mapping
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        company_id = str(request.company_id)
        mapping = _get_field_mapping(pk, company_id)
        serializer = IntegrationFieldMappingWriteSerializer(
            mapping,
            data=request.data,
            partial=True,
            context={"partner": mapping.partner},
        )
        serializer.is_valid(raise_exception=True)
        mapping = serializer.save()
        return Response(IntegrationFieldMappingSerializer(mapping).data)

    def delete(self, request, pk):
        company_id = str(request.company_id)
        mapping = _get_field_mapping(pk, company_id)
        mapping.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ValueMappingListView(CustomJWTRequestMixin, APIView):
    """
    GET  /api/v1/integration/data-mapping/<field_mapping_id>/values
         List all value mappings for a field.

    POST /api/v1/integration/data-mapping/<field_mapping_id>/values
         Single:  { "source_value": "Accounting", "target_value": "Finance" }
         Bulk:    { "source_value": "Accounting",
                    "target_values": ["Finance", "Accounting", "Tax", "Auditor"] }

    The constraint is unique(field_mapping, target_value): each ERP value maps
    to exactly one ConnectJob value, but MANY ERP values may share the same
    ConnectJob value (many-to-one).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, field_mapping_id):
        company_id = str(request.company_id)
        field_mapping = _get_field_mapping(field_mapping_id, company_id)
        serializer = IntegrationValueMappingSerializer(
            field_mapping.value_mappings.order_by("source_value", "target_value"),
            many=True,
        )
        return Response({"data": serializer.data})

    def post(self, request, field_mapping_id):
        company_id = str(request.company_id)
        field_mapping = _get_field_mapping(field_mapping_id, company_id)

        # ── Detect bulk vs single from request body ───────────────────────────
        is_bulk = "target_values" in request.data

        if is_bulk:
            return self._create_bulk(request, field_mapping)
        return self._create_single(request, field_mapping)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _create_single(self, request, field_mapping):
        serializer = IntegrationValueMappingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_value = serializer.validated_data["target_value"]
        if field_mapping.value_mappings.filter(target_value=target_value).exists():
            raise BadRequestException(
                f"ERP value '{target_value}' is already mapped for this field."
            )

        with transaction.atomic():
            vm = serializer.save(field_mapping=field_mapping)
            self._promote_if_free(field_mapping)

        return Response(
            IntegrationValueMappingSerializer(vm).data,
            status=status.HTTP_201_CREATED,
        )

    def _create_bulk(self, request, field_mapping):
        """
        Accepts { source_value: "Accounting",
                  target_values: ["Finance", "Tax", "Auditor"] }
        and creates one row per target_value, all pointing to the same
        ConnectJob source_value. Skips duplicates silently (idempotent).
        """
        serializer = IntegrationValueMappingBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        source_value = serializer.validated_data["source_value"]
        target_values = serializer.validated_data["target_values"]

        existing = set(
            field_mapping.value_mappings
            .filter(target_value__in=target_values)
            .values_list("target_value", flat=True)
        )
        new_target_values = [tv for tv in target_values if tv not in existing]

        created = []
        with transaction.atomic():
            for target_value in new_target_values:
                vm = IntegrationValueMapping.objects.create(
                    field_mapping=field_mapping,
                    source_value=source_value,
                    target_value=target_value,
                )
                created.append(vm)
            self._promote_if_free(field_mapping)

        return Response(
            {
                "created": IntegrationValueMappingSerializer(created, many=True).data,
                "skipped": list(existing),
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _promote_if_free(field_mapping):
        if field_mapping.mapping_type == MappingType.FREE:
            field_mapping.mapping_type = MappingType.MAPPED
            field_mapping.save(update_fields=["mapping_type", "updated_at"])


class RestoreDefaultMappingsView(CustomJWTRequestMixin, APIView):
    """
    POST /api/v1/integration/data-mapping/restore-defaults

    Re-applies the pre-defined DEFAULT_FIELD_MAPPINGS for the company's active
    integration. Already-configured source_fields are left untouched so any
    customisations the admin has made are never overwritten.

    Returns the list of newly added mappings. If nothing was missing, returns
    an empty list.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        company_id = str(request.company_id)
        partner = _get_active_partner(company_id)
        created = seed_default_field_mappings(partner)
        return Response(
            {
                "added": IntegrationFieldMappingSerializer(created, many=True).data,
                "message": (
                    f"{len(created)} default mapping(s) restored."
                    if created
                    else "All default mappings are already configured."
                ),
            },
            status=status.HTTP_200_OK,
        )


class ValueMappingDetailView(CustomJWTRequestMixin, APIView):
    """
    PATCH  /api/v1/integration/data-mapping/<field_mapping_id>/values/<pk>
    DELETE /api/v1/integration/data-mapping/<field_mapping_id>/values/<pk>
    Deleting the last value mapping auto-demotes the field back to "free".
    """

    permission_classes = [IsAuthenticated]

    def _get_value_mapping(self, field_mapping_id, pk, company_id):
        vm = IntegrationValueMapping.objects.filter(
            id=pk,
            field_mapping__id=field_mapping_id,
            field_mapping__partner__organization_id=company_id,
        ).select_related("field_mapping").first()
        if not vm:
            raise NotFoundException("Value mapping not found.")
        return vm

    def patch(self, request, field_mapping_id, pk):
        company_id = str(request.company_id)
        vm = self._get_value_mapping(field_mapping_id, pk, company_id)
        serializer = IntegrationValueMappingSerializer(vm, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        new_target = serializer.validated_data.get("target_value")
        if new_target and new_target != vm.target_value:
            if vm.field_mapping.value_mappings.filter(target_value=new_target).exists():
                raise BadRequestException(
                    f"ERP value '{new_target}' is already mapped for this field."
                )

        vm = serializer.save()
        return Response(IntegrationValueMappingSerializer(vm).data)

    def delete(self, request, field_mapping_id, pk):
        company_id = str(request.company_id)
        vm = self._get_value_mapping(field_mapping_id, pk, company_id)
        field_mapping = vm.field_mapping

        with transaction.atomic():
            vm.delete()
            # Auto-demote to "free" if no value mappings remain
            if not field_mapping.value_mappings.exists():
                field_mapping.mapping_type = MappingType.FREE
                field_mapping.save(update_fields=["mapping_type", "updated_at"])

        return Response(status=status.HTTP_204_NO_CONTENT)
