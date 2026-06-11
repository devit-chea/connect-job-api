from apps.auth_oauth.constants.auth_constants import PermissionOptions, UserState
from apps.auth_oauth.services.permission_service import PermissionService
from apps.core.exceptions.base_exceptions import (
    PermissionDeniedException,
)

ALLOWED_ROLES = {"recruiter", "admin_recruiter"}
COMPANY_APPROVED = "approved"
COMPANY_REJECTED = "rejected"
UCP_COMPLETE = "complete_setup_profile"
PROFILE_APPROVED = "approved"
VALID_PROFILE_STATUSES = ("approved", "complete")
EXCLUDED_ROLES = {"applicant", "super_admin"}


def ensure_applicant_profile_complete(request, skip: bool = False) -> None:
    if skip:
        return
    if not getattr(request, "auth", None):
        return
    payload = request.auth.payload
    if payload.get("type") != "applicant":
        return
    from apps.auth_oauth.services.user_company_profile_service import UserCompanyProfileService
    ucp_id = payload.get("user_company_profile_id")
    if not ucp_id:
        return
    ucp = UserCompanyProfileService.get_by_id(ucp_id)
    if getattr(ucp, "state", None) == UserState.PENDING_SETUP_PROFILE:
        raise PermissionDeniedException("Please complete your profile setup first.")

def ensure_completed_profile(request) -> None:
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return
    user_type = request.auth.payload.get("type", None)
    if user_type in EXCLUDED_ROLES:
        return

    company_status = request.auth.payload.get("company_status", None)
    ucp_state = request.auth.payload.get("user_company_profile_state", None)
    profile_status = request.auth.payload.get("profile_status", None)

    if company_status == COMPANY_REJECTED:
        raise PermissionDeniedException("Your company is REJECTED.")
    if company_status != COMPANY_APPROVED:
        raise PermissionDeniedException("Your company is PENDING.")
    if ucp_state != UCP_COMPLETE:
        raise PermissionDeniedException("Your company profile setup is not complete.")
    if profile_status not in VALID_PROFILE_STATUSES:
        raise PermissionDeniedException("Your personal profile is not complete.")


class PermissionMixin:
    """use to check user permission
    ex: class UserView(PermissionMixin)"""

    permission_codename = None  # Must be set in the view

    def get_permission_type(self):

        codename_to_check = self.permission_codename

        # Skip check if not set
        if not codename_to_check:
            return None

        permissions = PermissionService.fetch_permissions(self.request)
        return PermissionService().check_permission(permissions, codename_to_check)

    def get_action_or_method(self):
        """
        Return the DRF action (if available), or fallback to HTTP method.
        """
        if hasattr(self, "action"):
            return self.action.lower()  # list, retrieve, create, etc.
        return self.request.method.upper()  # GET, POST, PUT, etc.

    def initial(self, request, *args, **kwargs):
        """
        Override DRF's `initial` to check permission before proceeding.
        """
        super().initial(request, *args, **kwargs)

        ensure_applicant_profile_complete(
            request, skip=getattr(self, "allow_pending_profile", False)
        )
        permission_type = (
            self.get_permission_type()
            if bool(request.user and request.user.is_authenticated)
            else None
        )

        # Skip enforcement if permission_codename is None
        if not permission_type:
            return super().initial(request, *args, **kwargs)

        action_or_method = self.get_action_or_method()

        if permission_type == PermissionOptions.DENIED:
            raise PermissionDeniedException("Access denied.")

        if permission_type == PermissionOptions.VIEW_ONLY and action_or_method not in [
            "list",
            "retrieve",
            "GET",
            "HEAD",
            "OPTIONS",
        ]:
            raise PermissionDeniedException("Read-only access.")


class PermissionWithUserTypeMixin(PermissionMixin):
    """
    Extends PermissionMixin to add a check for required user types.
    
    Defaults to restricting access to only 'operator' and 'super_admin' 
    unless explicitly overridden in the consuming View.
    """
    # DEFAULT STRICT ACCESS LIST
    allowed_user_types = ('operator', 'super_admin') 

    def _check_user_type(self, request):
        """
        Internal method to check if the user's type is in the allowed list.
        """
        # Note: Since allowed_user_types now has a default, this check is 
        # always performed unless a view sets allowed_user_types = None.
        if not self.allowed_user_types:
            return True 

        user = request.user
        
        # Deny access if a restriction is set but the user is not authenticated or lacks the user_type attribute
        if not (user and user.is_authenticated and hasattr(request, 'user_type')):
            return False 

        # Check if the user's type is explicitly allowed
        if request.user_type in self.allowed_user_types:
            return True
            
        return False

    def initial(self, request, *args, **kwargs):
        """
        Overrides the parent's initial method to insert the user type check
        before running the original permission logic.
        """
        
        # 1. --- USER TYPE CHECK ---
        # The check now runs by default because allowed_user_types is not None.
        if not self._check_user_type(request):
            raise PermissionDeniedException("Access denied. Incorrect user type for this resource.")
        # ---------------------------

        # 2. Call the parent's initial, which contains the original 
        #    permission_codename check and the call to super().initial().
        return super().initial(request, *args, **kwargs)
