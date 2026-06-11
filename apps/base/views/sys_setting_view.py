from apps.base.views.base_views import BaseModelViewSet, BaseCreateAPIView
from apps.base.models.sys_setting_model import SysSetting
from apps.base.serializers.sys_setting_serializer import SysSettingSerializer

from config.settings import base


class SysSettingView(BaseModelViewSet):
    model = SysSetting
    queryset = SysSetting.objects.all()
    serializer_class = SysSettingSerializer

    def list(self, request):
        data = SysSetting.objects.filter(
            company=self.request.user.base_company.id
        ).all()
        data = self.filter_queryset(data)
        page = self.paginate_queryset(data)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)


class SysSettingViewByName(BaseCreateAPIView):
    def get_setting(self, name: str, company=None, user=None):
        base_company = company
        try:
            if not self.request.user.id and not base_company:
                base_company = None
            else:
                base_company = self.request.user.base_company
            sys_name = SysSetting.objects.get(name=name, company=base_company).value
        except Exception:
            try:
                if user:
                    base_company = user.base_company
                sys_name = SysSetting.objects.get(name=name, company=base_company).value
            except SysSetting.DoesNotExist:
                sys_name = getattr(base, name)
        return sys_name

    def create_company_sys_setting(self, company_id):
        sys_setting = SysSetting.objects.filter(company_id__isnull=True)
        if sys_setting:
            sys_setting.update(company_id=company_id, first_value=True)
        else:
            sys_setting = SysSetting.objects.filter(first_value=True)
            for data in sys_setting:
                data.id = None
                data.first_value = False
                data.company_id = company_id
                data.save()
