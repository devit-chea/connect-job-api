from apps.base.serializers.company_serializer import CompanySerializer
from apps.base.models.company_model import Company
from apps.base.constants.base_constants import Status
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.constants.auth_constants import ProfileStatus
from datetime import datetime


class CompanyService:

    def __init__(self, context=None):
        self.context = context

    def create_if_not_existed(self, data):
        is_existed, company_instance = self.is_existed(data)
        if is_existed:
            return company_instance
        company_serializer = CompanySerializer(data=data)
        company_serializer.is_valid(raise_exception=True)
        company_instance = company_serializer.save()
        return company_instance

    def create(self, data):
        is_existed, _ = self.is_existed(data)
        if is_existed:
            data["is_existed"] = True
        company_serializer = CompanySerializer(data=data)
        company_serializer.is_valid(raise_exception=True)
        company_instance = company_serializer.save()
        return company_instance

    def is_existed(self, data):
        name = data.get("name", None)
        company_query = Company.objects.filter(name__iexact=name, is_active=True)
        company_instance = company_query.first()
        if company_query.exists():
            return True, company_instance
        return False, None

    def update_approved_company(self, company_id, status):
        request = self.context.get("request")
        user_id = request.user.id
        
        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            # Handle error if company not found
            return
        
        company.status = status
        company.is_active = True if status == Status.APPROVED else False
        company.write_date = datetime.now()
        company.write_uid = user_id
        
        company.save()
        
        if status == Status.REJECTED:
            UserCompanyProfile.objects.filter(
                user_id=user_id, company_id=company_id
            ).update(status=ProfileStatus.INACTIVE)

    def create_as_profile(self, data):
        #  todo will remove if no requirement
        # is_existed, existed_company = self.is_existed(data)
        # if is_existed:
        #     data["is_existed"] = True
        #     data["existed_company"] = existed_company
        company_instance = Company.objects.create(**data)
        return company_instance
