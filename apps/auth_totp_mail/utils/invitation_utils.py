from apps.auth_totp_mail.constants.invite_type_contants import InvitationType

INVITATION_TYPE_DISPLAY_MAPPING = {
    InvitationType.INTERVIEW: "Interview",
    InvitationType.SIGN_CONTRACT: "Sign Contract",
    InvitationType.OFFER: "Offer",
    InvitationType.ASSESSMENT: "Assessment",
}


def get_invitation_type_display(invitation_type):
    return INVITATION_TYPE_DISPLAY_MAPPING.get(invitation_type)


INVITATION_NOT_FOUND = "Invitation not found."


RESCHEDULE = "Reschedule"