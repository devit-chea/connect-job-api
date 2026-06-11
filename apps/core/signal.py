import json
from pathlib import Path

from django.apps import apps as django_apps
from django.db import transaction

DEFAULT_COMPANY_COUNT = 0
DEFAULT_PERMISSION_COUNT = 0
DEFAULT_ROLE_COUNT = 0


def create_default_company(**kwargs):
    global DEFAULT_COMPANY_COUNT
    DEFAULT_COMPANY_COUNT += 1
    if DEFAULT_COMPANY_COUNT > 1:
        return
    import json
    from apps.base.models.company_model import Company

    company_file = "apps/base/data/base_company.json"
    with open(company_file, encoding="utf8") as file:
        company_data = json.load(file)
        company_query = Company.objects.filter(code=company_data.get("code", "DEFAULT"))
        if company_query.exists():
            return
        Company.objects.create(**company_data)


def _norm_list(v):
    return v or []  # normalize None → []


def _needs_update(obj, fields: dict) -> bool:
    for k, v in fields.items():
        if k == "custom_type":
            if (getattr(obj, k) or []) != (v or []):
                return True
        elif k == "parent":
            if (getattr(obj, "parent_id", None) or None) != (getattr(v, "id", None) if v else None):
                return True
        else:
            if getattr(obj, k) != v:
                return True
    return False


@transaction.atomic
def create_permissions(sender, **kwargs):
    """
    Idempotent seeding after migrations. Creates/updates parents first, then children.
    Uses a single prefetch by codename and bulk create/update (no per-item get_or_create).
    """
    Permission = django_apps.get_model("auth_oauth", "Permission")

    data_dir = Path("apps/base/data")
    files = [
        "operator_permission.json",
        "admin_recruiter_permission.json",
        "applicant_permission.json",
        "recruiter_permission.json",
    ]

    parents, children, all_codes = [], [], set()
    for fname in files:
        fp = data_dir / fname
        if not fp.exists():
            continue
        with open(fp, encoding="utf8") as f:
            payload = json.load(f)
        nodes = payload if isinstance(payload, list) else [payload]
        for parent in nodes:
            parents.append(parent)
            all_codes.add(parent["codename"])
            for ch in parent.get("children") or []:
                children.append((parent["codename"], ch))
                all_codes.add(ch["codename"])

    if not all_codes:
        print("[post_migrate] create_permissions: no permissions found in JSON.")
        return

    existing = {p.codename: p for p in Permission.objects.filter(codename__in=all_codes)}

    # ---- Pass A: upsert parents (top-level) ----
    parents_to_create, parents_to_update = [], []
    for p in parents:
        code = p["codename"]
        fields = {
            "name": p.get("name") or code,
            "description": p.get("description") or "",
            "type": p.get("type") or "menu",
            "group": p.get("group") or "",
            "custom_type": _norm_list(p.get("custom_type")),
            "parent": None,
        }
        obj = existing.get(code)
        if obj is None:
            parents_to_create.append(Permission(codename=code, **fields))
        else:
            if _needs_update(obj, fields):
                for k, v in fields.items():
                    setattr(obj, k, v)
                parents_to_update.append(obj)

    if parents_to_create:
        Permission.objects.bulk_create(parents_to_create, batch_size=1000)
        # refresh created parents so we have their IDs for children
        created_codes = [o.codename for o in parents_to_create]
        for obj in Permission.objects.filter(codename__in=created_codes):
            existing[obj.codename] = obj

    if parents_to_update:
        Permission.objects.bulk_update(
            parents_to_update,
            fields=["name", "description", "type", "group", "custom_type", "parent"],
            batch_size=1000,
        )

    # ---- Pass B: upsert children (attach to parent) ----
    children_to_create, children_to_update = [], []
    for parent_code, ch in children:
        parent_obj = existing.get(parent_code)
        if not parent_obj:
            # parent missing in JSON load (skip to avoid FK issues)
            continue
        code = ch["codename"]
        fields = {
            "name": ch.get("name") or code,
            "description": ch.get("description") or "",
            "type": ch.get("type") or "permission",
            "group": ch.get("group") or "",
            "custom_type": _norm_list(ch.get("custom_type")),
            "parent": parent_obj,
        }
        obj = existing.get(code)
        if obj is None:
            children_to_create.append(Permission(codename=code, **fields))
        else:
            if _needs_update(obj, fields):
                for k, v in fields.items():
                    setattr(obj, k, v)
                children_to_update.append(obj)

    if children_to_create:
        Permission.objects.bulk_create(children_to_create, batch_size=1000)

    if children_to_update:
        Permission.objects.bulk_update(
            children_to_update,
            fields=["name", "description", "type", "group", "custom_type", "parent"],
            batch_size=1000,
        )


def get_role_payload(name, code, _type, description, permissions, perm_type="allowed"):
    return {
        "name": name,
        "code": code,
        "type": _type,
        "active": True,
        "description": description,
        "role_permissions": [
            {"permission": p.pk, "perm_type": perm_type} for p in permissions
        ],
    }


def save(group, name, code, _type, description, permission_codenames=None, perm_type="allowed"):
    from apps.auth_oauth.models.permission_model import Permission
    from apps.auth_oauth.serializers.role_serializer import DefaultRoleSerializer

    perms = (
        Permission.objects.filter(codename__in=permission_codenames)
        if permission_codenames
        else Permission.objects.filter(group=group)
    )
    payload = get_role_payload(
        name=name,
        code=code,
        _type=_type,
        description=description,
        permissions=perms,
        perm_type=perm_type,
    )
    serializer = DefaultRoleSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    serializer.save()


def create_default_role(*args, **kwargs):
    global DEFAULT_ROLE_COUNT
    DEFAULT_ROLE_COUNT += 1
    if DEFAULT_ROLE_COUNT > 1:
        return
    # default roles
    print("default roles start creating....")

    """
        Genreate Default role for operator, admin_recruiter, recuiter, applicant
    
    """
    from apps.auth_oauth.models.role_model import Role
    from apps.auth_oauth.constants.auth_constants import (
        GroupTypes,
        DefaultRole,
        UserTypes,
    )

    default_roles = [
        {
            "group": GroupTypes.OPERATOR,
            "name": "Operator Default Role",
            "code": DefaultRole.OPERATOR_DEFAULT_ROLE,
            "_type": UserTypes.OPERATOR,
            "description": "Default role for operator",
        },
        {
            "group": GroupTypes.ADMIN_RECRUITER,
            "name": "Admin Recruiter Default Role",
            "code": DefaultRole.ADMIN_RECRUITER_ROLE,
            "_type": UserTypes.ADMIN_RECRUITER,
            "description": "Default role for admin recruiter",
        },
        {
            "group": GroupTypes.RECRUITER,
            "name": "Recruiter Default Role",
            "code": DefaultRole.RECRUITER_ROLE,
            "_type": UserTypes.RECRUITER,
            "description": "Default role for recruiter",
        },
        {
            "group": GroupTypes.APPLICANT,
            "name": "Applicant Default Role",
            "code": DefaultRole.APPLICANT_ROLE,
            "_type": UserTypes.APPLICANT,
            "description": "Default role for applicant",
        },
        {
            "group": GroupTypes.ADMIN_RECRUITER,
            "name": "Pending Admin Recruiter Default Role",
            "code": DefaultRole.PENDING_ADMIN_RECRUITER_ROLE,
            "_type": UserTypes.PENDING_ADMIN_RECRUITER,
            "description": "Pending admin recruiter; can only read profile info",
            "permission_codenames": [
                "admin_recruiter_manage_profile",
                "recruiter_manage_profile",
                "applicant_manage_profile",
                "operator_manage_profile",
            ],
            "perm_type": "view_only",
        },
    ]

    for role in default_roles:
        if not Role.objects.filter(code=role["code"]).exists():
            save(**role)

    print("default roles finished.")
