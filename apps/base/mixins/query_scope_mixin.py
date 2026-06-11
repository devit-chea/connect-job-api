from django.db.models import Q


class ScopedQuerysetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return self.scope_queryset(qs)

    def scope_queryset(self, qs):
        return qs  # default (no-op)


class AdminQuerysetMixin(ScopedQuerysetMixin):
    def get_queryset(self):
        return super().get_queryset()


class RecruiterQuerysetMixin(ScopedQuerysetMixin):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(company=self.request.company_id)


class AdminRecruiterQuerysetMixin(ScopedQuerysetMixin):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(Q(company=self.request.company_id) | Q(is_public=True))


class ApplicantQuerysetMixin(ScopedQuerysetMixin):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(is_active=True)


class RecruiterOrAdminQuerysetMixin(ScopedQuerysetMixin):
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        ucp_id = getattr(self.request, "user_company_profile_id", None)

        if user.type == "admin_recruiter":
            # admin sees all in company
            return qs.filter(company_id=self.request.company_id)

        elif user.type == "recruiter":
            # recruiter sees only assigned / owned
            return qs.filter(company_id=self.request.company_id, create_ucp_id=ucp_id)

        return qs.none()
