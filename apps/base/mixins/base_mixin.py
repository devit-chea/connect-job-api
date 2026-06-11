class BaseMixin:

    def _perform_create(self, serializer):
        serializer.validated_data["create_uid"] = self.request.user.id
        serializer.validated_data["create_ucp_id"] = self.get_user_company_profile_id()
        serializer.save()

    def _perform_update(self, serializer):
        if serializer.is_valid():
            serializer.validated_data["write_uid"] = self.request.user.id
            serializer.validated_data["write_ucp_id"] = (
                self.get_user_company_profile_id()
            )
            serializer.save()

    def get_user_company_profile_id(self):
        user_company_profile_id = None
        if getattr(self.request, "user_company_profile_id", None):
            user_company_profile_id = self.request.user_company_profile_id
        elif bool(self.request.user and self.request.user.is_authenticated):
            user_company_profile_id = self.request.auth.payload.get(
                "user_company_profile_id", None
            )
        return user_company_profile_id
