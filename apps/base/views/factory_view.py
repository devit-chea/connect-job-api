import json
from pathlib import Path

from django.db import transaction
from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response

from apps.auth_oauth.models.permission_model import Permission
from apps.base.models.country_model import Country
from apps.base.models.currency_model import Currency
from apps.base.models.geo_area_model import GeoArea
from apps.base.models.institution_model import Institution
from apps.base.models.language_model import Language
from apps.base.serializers.country_serializer import CountrySerializer
from apps.base.serializers.currency_serializer import CurrencySerializer
from apps.base.serializers.geo_area_serializer import GeoAreaSerializer
from apps.base.serializers.institution_serializer import InstitutionSerializer
from apps.base.serializers.language_serializer import LanguageSerializer
from apps.base.services.institution_service import create_institutions_from_json


# TODO: remove permission_classes = ()


class GeoAreasView(generics.CreateAPIView):
    queryset = GeoArea.objects.all()
    serializer_class = GeoAreaSerializer
    permission_classes = ()

    def create(self, *args, **kwargs):
        with open("apps/base/data/geoareas.json", encoding="utf8") as file:
            contents = json.load(file)

            for content in contents:
                serializer = self.get_serializer(data=content)
                serializer.is_valid(raise_exception=True)
                serializer.save(create_uid=self.request.user.id)
        return Response(status=status.HTTP_201_CREATED)


class CountriesView(generics.CreateAPIView):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = ()

    def create(self, *args, **kwargs):
        with open("apps/base/data/countries.json", encoding="utf8") as file:
            contents = json.load(file)
            for content in contents:
                serializer = self.get_serializer(data=content)
                serializer.is_valid(raise_exception=True)
                serializer.save(create_uid=self.request.user.id)
        return Response(status=status.HTTP_201_CREATED)


class ResLanguageView(generics.CreateAPIView):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    permission_classes = ()

    def create(self, *args, **kwargs):
        with open("apps/base/data/res_language.json", encoding="utf8") as file:
            contents = json.load(file)

            for content in contents:
                serializer = self.get_serializer(data=content)
                serializer.is_valid(raise_exception=True)
                serializer.save(create_uid=self.request.user.id)
        return Response(status=status.HTTP_201_CREATED)


class CurrencyFactoryView(generics.CreateAPIView):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = ()

    def create(self, *args, **kwargs):
        with open("apps/base/data/currencies.json", encoding="utf8") as file:
            contents = json.load(file)

            for content in contents.items():
                serializer = self.get_serializer(data=content[1])
                serializer.is_valid(raise_exception=True)
                serializer.save(create_uid=self.request.user.id)

        return Response(status=status.HTTP_201_CREATED)


class InstitutionsView(generics.CreateAPIView):
    queryset = Institution.objects.all()
    serializer_class = InstitutionSerializer
    permission_classes = ()

    def create(self, *args, **kwargs):
        # Define the file path
        file_path = "apps/base/data/institutions.json"
        
        # Determine the user ID to associate with the created records
        create_uid = self.request.user.id if self.request.user.is_authenticated else None

        # Call the service function to handle the business logic
        result = create_institutions_from_json(
            file_path=file_path,
            serializer_class=self.get_serializer_class(),
            create_uid=create_uid
        )
        return Response(
            data={"message": result.get("message"), "details": result.get("details")}, 
            status=result.get("status", status.HTTP_500_INTERNAL_SERVER_ERROR)
        )


class PermissionView(generics.CreateAPIView):
    queryset = Permission.objects.all()
    serializer_class = None
    permission_classes = ()

    DATA_DIR = Path("apps/base/data")
    FILES = [
        "operator_permission.json",
        "admin_recruiter_permission.json",
        "applicant_permission.json",
        "recruiter_permission.json",
    ]

    def _load_trees(self):
        for fname in self.FILES:
            with open(self.DATA_DIR / fname, encoding="utf8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    yield data
                else:
                    for parent in data:
                        yield parent

    @transaction.atomic
    def create(self, *args, **kwargs):
        parents = []
        children = []
        all_codes = set()

        for parent in self._load_trees():
            parents.append(parent)
            all_codes.add(parent["codename"])
            for ch in parent.get("children") or []:
                children.append((parent["codename"], ch))
                all_codes.add(ch["codename"])

        if not all_codes:
            return Response({"detail": "No permissions in JSON."}, status=status.HTTP_400_BAD_REQUEST)

        existing = {p.codename: p for p in Permission.objects.filter(codename__in=all_codes)}

        parents_to_create = []
        parents_to_update = []
        for p in parents:
            code = p["codename"]
            fields = {
                "name": p.get("name") or code,
                "description": p.get("description") or "",
                "type": p.get("type") or "permission",
                "group": p.get("group") or "",
                "custom_type": p.get("custom_type", []),
                "parent": None,
            }
            if code in existing:
                obj = existing[code]
                for k, v in fields.items():
                    setattr(obj, k, v)
                parents_to_update.append(obj)
            else:
                obj = Permission(codename=code, **fields)
                parents_to_create.append(obj)

        if parents_to_create:
            Permission.objects.bulk_create(parents_to_create, batch_size=1000)
            created_codes = [o.codename for o in parents_to_create]
            existing.update({p.codename: p for p in Permission.objects.filter(codename__in=created_codes)})

        if parents_to_update:
            Permission.objects.bulk_update(
                parents_to_update,
                fields=["name", "description", "type", "group", "custom_type", "parent"],
                batch_size=1000,
            )

        children_to_create = []
        children_to_update = []
        for parent_code, ch in children:
            parent_obj = existing[parent_code]
            code = ch["codename"]
            fields = {
                "name": ch.get("name") or code,
                "description": ch.get("description") or "",
                "type": ch.get("type") or "permission",
                "group": ch.get("group") or "",
                "custom_type": ch.get("custom_type", []),
                "parent": parent_obj,
            }
            if code in existing:
                obj = existing[code]
                for k, v in fields.items():
                    setattr(obj, k, v)
                children_to_update.append(obj)
            else:
                obj = Permission(codename=code, **fields)
                children_to_create.append(obj)

        if children_to_create:
            Permission.objects.bulk_create(children_to_create, batch_size=1000)

        if children_to_update:
            Permission.objects.bulk_update(
                children_to_update,
                fields=["name", "description", "type", "group", "custom_type", "parent"],
                batch_size=1000,
            )

        return Response(
            {
                "created": {
                    "parents": len(parents_to_create),
                    "children": len(children_to_create),
                    "total": len(parents_to_create) + len(children_to_create),
                },
                "updated": {
                    "parents": len(parents_to_update),
                    "children": len(children_to_update),
                    "total": len(parents_to_update) + len(children_to_update),
                },
                "seen": len(all_codes),
            },
            status=status.HTTP_201_CREATED,
        )
