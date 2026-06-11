from .models import AuthSettingModel
from rest_framework import generics, status
from rest_framework.response import Response
from .serializers import (ToggleAuthSettingSerializers, BulkToggleAuthSettingSerializers)

class Toggle2StepVerificationView(generics.CreateAPIView):
    serializer_class = ToggleAuthSettingSerializers

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        is_enable = serializer.validated_data["is_enable"]
        app_name = serializer.validated_data["app_name"]
        toggle = "enabled" if is_enable else "disabled"
        
        try:
            AuthSettingModel.objects.update_or_create(
                user_id=user_id,
                app_name=app_name,
                company=request.user.base_company,
                defaults={"is_enable": is_enable}
            )
        except Exception:
            return Response({
            "is_enable": is_enable,
            "message": f"invalid user for {toggle} 2-Step Verification."
        }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "is_enable": is_enable,
            "message": f"2-Step Verification {toggle} successfully." ,
        }, status=status.HTTP_200_OK)
    
class BulkToggle2StepVerificationView(generics.CreateAPIView):
    serializer_class = BulkToggleAuthSettingSerializers

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_enable = serializer.validated_data["is_enable"]
        bulk_user_set = set(serializer.validated_data["bulk_user_id"])

        count_success = 0
        for _ , item in enumerate(bulk_user_set):
            try:
                obj, _ = AuthSettingModel.objects.update_or_create(
                    user_id=item,
                    defaults={"is_enable": is_enable, "create_uid": request.user.id}
                )
                if obj:
                    count_success += 1
                    obj.user.is_two_step_verification = is_enable
                    obj.user.save(update_fields=('is_two_step_verification', ))

            except Exception as e:
                # The caught exception is printed for debugging purposes
                print(f"An error occurred for item {item}: {e}")
                continue

        toggle = "enabled" if is_enable else "disabled"
        entry = "entries have been" if count_success > 1 else "entry has been"
        return Response({
            "is_enable": is_enable,
            "message": f"{count_success} {entry} {toggle} 2-Step Verification successfully." ,
        }, status=status.HTTP_200_OK)




